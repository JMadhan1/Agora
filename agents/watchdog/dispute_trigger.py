"""Triggers UMA disputes on Polygon when manipulation is detected."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import structlog
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider
from eth_account import Account

log = structlog.get_logger()

# UMA OO V3 ABI — just what we need
UMA_OO_ABI = [
    {
        "inputs": [
            {"name": "assertionId", "type": "bytes32"},
            {"name": "disputer", "type": "address"},
        ],
        "name": "disputeAssertion",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "assertionId", "type": "bytes32"}],
        "name": "getAssertion",
        "outputs": [
            {
                "components": [
                    {"name": "currency", "type": "address"},
                    {"name": "settled", "type": "bool"},
                    {"name": "assertionTruth", "type": "bool"},
                    {"name": "disputeId", "type": "bytes32"},
                    {"name": "bond", "type": "uint256"},
                    {"name": "assertionTime", "type": "uint64"},
                    {"name": "expirationTime", "type": "uint64"},
                    {"name": "asserter", "type": "address"},
                    {"name": "disputer", "type": "address"},
                    {"name": "callbackRecipient", "type": "address"},
                    {"name": "escalationManager", "type": "address"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
]

ERC20_APPROVE_ABI = [
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]

UMA_OO_V3_ADDRESS = "0x9923D42eF695B5dd9911D05Ac944d4cAca3c4EAC"


class DisputeTrigger:
    """Submits UMA disputes on Polygon when Watchdog detects manipulation."""

    POLYGON_CHAIN_ID = 137

    def __init__(self, polygon_rpc_url: str, private_key: str):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(polygon_rpc_url, request_kwargs={"timeout": 30}))
        self.account = Account.from_key(private_key)
        self.address = self.account.address

    async def trigger_uma_dispute(
        self,
        assertion_id_hex: str,
        bond_currency_address: str,
        bond_amount_wei: int,
    ) -> dict:
        """
        Approves bond currency and calls disputeAssertion on UMA OO V3 (Polygon).
        Returns { tx_hash, dispute_triggered, timestamp } or { dispute_triggered: False, error }.
        """
        try:
            assertion_id_bytes = bytes.fromhex(assertion_id_hex.lstrip("0x"))
            if len(assertion_id_bytes) != 32:
                assertion_id_bytes = assertion_id_bytes.ljust(32, b"\x00")

            # Step 1: Approve bond token to UMA contract
            if bond_amount_wei > 0 and bond_currency_address:
                currency_contract = self.w3.eth.contract(
                    address=AsyncWeb3.to_checksum_address(bond_currency_address),
                    abi=ERC20_APPROVE_ABI,
                )
                nonce = await self.w3.eth.get_transaction_count(self.address, "pending")
                gas_price = await self.w3.eth.gas_price

                approve_fn = currency_contract.functions.approve(
                    AsyncWeb3.to_checksum_address(UMA_OO_V3_ADDRESS),
                    bond_amount_wei,
                )
                approve_gas = await approve_fn.estimate_gas({"from": self.address})
                approve_tx = await approve_fn.build_transaction({
                    "from": self.address,
                    "nonce": nonce,
                    "gas": int(approve_gas * 1.2),
                    "gasPrice": gas_price,
                    "chainId": self.POLYGON_CHAIN_ID,
                })
                signed = self.account.sign_transaction(approve_tx)
                approve_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
                await self.w3.eth.wait_for_transaction_receipt(approve_hash, timeout=60)
                log.info("uma_bond_approved", tx_hash=approve_hash.hex())

            # Step 2: Call disputeAssertion
            uma_contract = self.w3.eth.contract(
                address=AsyncWeb3.to_checksum_address(UMA_OO_V3_ADDRESS),
                abi=UMA_OO_ABI,
            )
            nonce = await self.w3.eth.get_transaction_count(self.address, "pending")
            gas_price = await self.w3.eth.gas_price

            dispute_fn = uma_contract.functions.disputeAssertion(
                assertion_id_bytes,
                AsyncWeb3.to_checksum_address(self.address),
            )
            dispute_gas = await dispute_fn.estimate_gas({"from": self.address})
            dispute_tx = await dispute_fn.build_transaction({
                "from": self.address,
                "nonce": nonce,
                "gas": int(dispute_gas * 1.2),
                "gasPrice": gas_price,
                "chainId": self.POLYGON_CHAIN_ID,
            })
            signed = self.account.sign_transaction(dispute_tx)
            tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
            receipt = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            log.info(
                "uma_dispute_triggered",
                assertion_id=assertion_id_hex,
                tx_hash=tx_hash.hex(),
                gas_used=receipt["gasUsed"],
            )
            return {
                "tx_hash": tx_hash.hex(),
                "dispute_triggered": True,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "gas_used": receipt["gasUsed"],
            }

        except Exception as e:
            log.error("uma_dispute_failed", assertion_id=assertion_id_hex, error=str(e))
            return {
                "dispute_triggered": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
