"""Arc Testnet Web3 client — Circle Tool: Arc Testnet USDC-native gas"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

import structlog
from eth_account import Account
from eth_account.signers.local import LocalAccount
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

log = structlog.get_logger()

ERC20_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "transfer",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "transferFrom",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function",
    },
]


class ArcClient:
    """Async client for Arc Testnet (chainId 5042002) — Circle EVM sidechain."""

    USDC_ADDRESS = "0x3600000000000000000000000000000000000000"
    CHAIN_ID = 5042002
    BLOCK_EXPLORER = "https://testnet.arcscan.app"

    def __init__(self, rpc_url: str, private_key: str) -> None:
        self.w3 = AsyncWeb3(
            AsyncHTTPProvider(rpc_url, request_kwargs={"timeout": 30})
        )
        self.account: LocalAccount = Account.from_key(private_key)
        self.address: str = self.account.address

    # ------------------------------------------------------------------
    # Connectivity
    # ------------------------------------------------------------------

    async def verify_connection(self) -> bool:
        """Assert we are connected to the correct chain and log balances."""
        chain_id = await self.w3.eth.chain_id
        if chain_id != self.CHAIN_ID:
            raise RuntimeError(f"Wrong chain: {chain_id}, expected {self.CHAIN_ID}")
        balance = await self.w3.eth.get_balance(self.address)
        log.info(
            "arc_connected",
            chain_id=chain_id,
            address=self.address,
            eth_balance_wei=balance,
        )
        return True

    # ------------------------------------------------------------------
    # USDC helpers
    # ------------------------------------------------------------------

    async def get_usdc_balance(self, address: str) -> float:
        """Return USDC balance of *address* as a human-readable float (6 decimals)."""
        contract = self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(self.USDC_ADDRESS),
            abi=ERC20_ABI,
        )
        raw: int = await contract.functions.balanceOf(
            AsyncWeb3.to_checksum_address(address)
        ).call()
        return raw / 1e6

    async def approve_usdc(self, spender: str, amount_usdc: float) -> str:
        """Approve *spender* to spend *amount_usdc* USDC. Returns tx hash."""
        amount_raw = int(amount_usdc * 1e6)
        return await self.call_contract_write(
            self.USDC_ADDRESS,
            ERC20_ABI,
            "approve",
            [AsyncWeb3.to_checksum_address(spender), amount_raw],
        )

    async def send_usdc(self, to: str, amount_usdc: float) -> str:
        """Transfer *amount_usdc* USDC to *to*. Returns tx hash."""
        amount_raw = int(amount_usdc * 1e6)
        return await self.call_contract_write(
            self.USDC_ADDRESS,
            ERC20_ABI,
            "transfer",
            [AsyncWeb3.to_checksum_address(to), amount_raw],
        )

    # ------------------------------------------------------------------
    # Generic contract interaction
    # ------------------------------------------------------------------

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def call_contract_write(
        self,
        contract_address: str,
        abi: list,
        function_name: str,
        args: list,
    ) -> str:
        """
        Build, sign, and broadcast a state-changing contract call.

        Retries up to 3 times with exponential back-off on any exception.
        Returns the transaction hash as a hex string.
        """
        contract = self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(contract_address),
            abi=abi,
        )
        fn = getattr(contract.functions, function_name)(*args)
        nonce = await self.w3.eth.get_transaction_count(self.address, "pending")
        gas_estimate = await fn.estimate_gas({"from": self.address})
        gas_limit = int(gas_estimate * 1.2)
        gas_price = await self.w3.eth.gas_price

        tx = await fn.build_transaction(
            {
                "from": self.address,
                "nonce": nonce,
                "gas": gas_limit,
                "gasPrice": gas_price,
                "chainId": self.CHAIN_ID,
            }
        )
        signed = self.account.sign_transaction(tx)
        tx_hash = await self.w3.eth.send_raw_transaction(signed.raw_transaction)
        tx_hash_hex: str = tx_hash.hex()

        log.info(
            "arc_tx_sent",
            function=function_name,
            contract=contract_address,
            tx_hash=tx_hash_hex,
            arc_scan_url=self.arc_scan_url(tx_hash_hex),
        )
        return tx_hash_hex

    async def call_contract_read(
        self,
        contract_address: str,
        abi: list,
        function_name: str,
        args: list,
    ) -> Any:
        """Execute a read-only (view/pure) contract call and return its result."""
        contract = self.w3.eth.contract(
            address=AsyncWeb3.to_checksum_address(contract_address),
            abi=abi,
        )
        fn = getattr(contract.functions, function_name)(*args)
        return await fn.call()

    @retry(
        stop=stop_after_attempt(20),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
        retry=retry_if_exception_type(Exception),
        reraise=True,
    )
    async def wait_for_receipt(self, tx_hash: str, timeout: int = 10) -> dict:
        """
        Poll for a transaction receipt, retrying up to 20 times.

        Raises if no receipt is found after all retries.
        """
        receipt = await self.w3.eth.get_transaction_receipt(tx_hash)
        if receipt is None:
            raise Exception(f"No receipt yet for {tx_hash}")
        log.info(
            "arc_tx_confirmed",
            tx_hash=tx_hash,
            block_number=receipt["blockNumber"],
            gas_used=receipt["gasUsed"],
            status=receipt["status"],
            arc_scan_url=self.arc_scan_url(tx_hash),
        )
        return dict(receipt)

    # ------------------------------------------------------------------
    # URL helpers
    # ------------------------------------------------------------------

    def arc_scan_url(self, tx_hash: str) -> str:
        """Return the ArcScan transaction explorer URL for *tx_hash*."""
        return f"{self.BLOCK_EXPLORER}/tx/{tx_hash}"

    def arc_scan_address_url(self, address: str) -> str:
        """Return the ArcScan address explorer URL for *address*."""
        return f"{self.BLOCK_EXPLORER}/address/{address}"
