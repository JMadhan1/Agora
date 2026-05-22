"""Bond management for Oracle Sentinel agents on Arc Testnet."""
from __future__ import annotations
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .arc_client import ArcClient

log = structlog.get_logger()

BOND_MANAGER_ABI = [
    {
        "inputs": [],
        "name": "depositBond",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "agent", "type": "address"}],
        "name": "getBond",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "agent", "type": "address"}],
        "name": "isBondSufficient",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "agent", "type": "address"}],
        "name": "slashCount",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

ERC20_ABI = [
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

USDC_ADDRESS = "0x3600000000000000000000000000000000000000"
MINIMUM_BOND_RAW = 10 * 1_000_000  # 10 USDC


class AgentBondManager:
    """Ensures agents maintain sufficient USDC bonds in the BondManager contract."""

    async def ensure_bond_deposited(
        self, arc_client: "ArcClient", bond_manager_address: str
    ) -> bool:
        """
        Checks bond status and deposits if insufficient.
        Circle Tool: Arc Testnet USDC bond for agent reputation.
        Returns True if bond is sufficient after check.
        """
        if not bond_manager_address:
            return False
        try:
            sufficient = await arc_client.call_contract_read(
                bond_manager_address, BOND_MANAGER_ABI, "isBondSufficient",
                [arc_client.w3.to_checksum_address(arc_client.address)]
            )
            if sufficient:
                log.info("bond_already_sufficient", address=arc_client.address)
                return True

            # Approve USDC first
            await arc_client.call_contract_write(
                USDC_ADDRESS, ERC20_ABI, "approve",
                [arc_client.w3.to_checksum_address(bond_manager_address), MINIMUM_BOND_RAW]
            )

            # Deposit bond
            tx_hash = await arc_client.call_contract_write(
                bond_manager_address, BOND_MANAGER_ABI, "depositBond", []
            )
            await arc_client.wait_for_receipt(tx_hash)
            log.info("bond_deposited", address=arc_client.address, tx_hash=tx_hash)
            return True

        except Exception as e:
            log.error("bond_deposit_failed", address=arc_client.address, error=str(e))
            return False

    async def get_bond_status(
        self, arc_client: "ArcClient", bond_manager_address: str
    ) -> dict:
        """Returns current bond status for the agent."""
        try:
            addr = arc_client.w3.to_checksum_address(arc_client.address)
            bond_raw = await arc_client.call_contract_read(
                bond_manager_address, BOND_MANAGER_ABI, "getBond", [addr]
            )
            sufficient = await arc_client.call_contract_read(
                bond_manager_address, BOND_MANAGER_ABI, "isBondSufficient", [addr]
            )
            slash_count = await arc_client.call_contract_read(
                bond_manager_address, BOND_MANAGER_ABI, "slashCount", [addr]
            )
            return {
                "bond_usdc": int(bond_raw) / 1e6,
                "is_sufficient": bool(sufficient),
                "slash_count": int(slash_count),
                "address": arc_client.address,
            }
        except Exception as e:
            log.warning("bond_status_failed", error=str(e))
            return {"bond_usdc": 0.0, "is_sufficient": False, "slash_count": 0}
