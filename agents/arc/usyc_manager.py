"""USYC tokenized money market fund — idle USDC yield management on Arc Testnet."""
from __future__ import annotations
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .arc_client import ArcClient

log = structlog.get_logger()

# Circle Tool: USYC tokenized money market fund on Arc Testnet
USYC_TELLER = "0x9fdF14c5B14173D74C08Af27AebFf39240dC105A"
USYC_TOKEN = "0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C"
USYC_ENTITLEMENTS = "0xcc205224862c7641930c87679e98999d23c26113"
USDC_ADDRESS = "0x3600000000000000000000000000000000000000"

USYC_TELLER_ABI = [
    {
        "inputs": [{"name": "usdcAmount", "type": "uint256"}],
        "name": "deposit",
        "outputs": [{"name": "usycReceived", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "usycAmount", "type": "uint256"}],
        "name": "redeem",
        "outputs": [{"name": "usdcReceived", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "exchangeRate",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "isEligible",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]

USYC_TOKEN_ABI = [
    {
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
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


async def deploy_idle_usdc_to_usyc(
    arc_client: "ArcClient",
    amount_usdc: float,
    wallet_address: str,
) -> dict | None:
    """
    Deploys idle USDC to USYC tokenized money market fund.
    Circle Tool: USYC on Arc Testnet — zero-idle capital yield.
    Gracefully handles allowlist/eligibility errors — returns None if ineligible.
    """
    amount_raw = int(amount_usdc * 1e6)
    if amount_raw <= 0:
        return None

    # Check eligibility first
    try:
        eligible = await arc_client.call_contract_read(
            USYC_TELLER, USYC_TELLER_ABI, "isEligible",
            [arc_client.w3.to_checksum_address(wallet_address)]
        )
        if not eligible:
            log.warning(
                "usyc_not_eligible",
                wallet=wallet_address,
                note="Add wallet to USYC allowlist at usyc.circle.com",
            )
            return None
    except Exception as e:
        log.warning("usyc_eligibility_check_failed", error=str(e))
        return None

    try:
        # Approve USDC to teller
        await arc_client.call_contract_write(
            USDC_ADDRESS, ERC20_APPROVE_ABI, "approve",
            [arc_client.w3.to_checksum_address(USYC_TELLER), amount_raw]
        )

        # Deposit
        tx_hash = await arc_client.call_contract_write(
            USYC_TELLER, USYC_TELLER_ABI, "deposit", [amount_raw]
        )
        receipt = await arc_client.wait_for_receipt(tx_hash)

        result = {
            "usdc_deployed": amount_usdc,
            "usyc_received": None,  # would parse from receipt logs in full impl
            "tx_hash": tx_hash,
            "arc_scan_url": arc_client.arc_scan_url(tx_hash),
        }
        log.info("usyc_deployed", amount_usdc=amount_usdc, tx_hash=tx_hash)
        return result

    except Exception as e:
        log.error("usyc_deploy_failed", amount_usdc=amount_usdc, error=str(e))
        return None


async def redeem_usyc_for_usdc(
    arc_client: "ArcClient",
    usyc_amount_raw: int,
    wallet_address: str,
) -> dict:
    """Redeems USYC shares back to USDC."""
    try:
        # Approve USYC to teller
        await arc_client.call_contract_write(
            USYC_TOKEN, USYC_TOKEN_ABI, "approve",
            [arc_client.w3.to_checksum_address(USYC_TELLER), usyc_amount_raw]
        )
        tx_hash = await arc_client.call_contract_write(
            USYC_TELLER, USYC_TELLER_ABI, "redeem", [usyc_amount_raw]
        )
        receipt = await arc_client.wait_for_receipt(tx_hash)
        log.info("usyc_redeemed", usyc_amount=usyc_amount_raw, tx_hash=tx_hash)
        return {"tx_hash": tx_hash, "arc_scan_url": arc_client.arc_scan_url(tx_hash)}
    except Exception as e:
        log.error("usyc_redeem_failed", error=str(e))
        return {"error": str(e)}


async def auto_manage_idle_capital(arc_client: "ArcClient", wallet_address: str) -> None:
    """
    Called every 5 minutes. If USDC > threshold → deploy to USYC.
    Circle Tool: USYC automated yield on idle capital.
    """
    try:
        from config import settings
        idle_usdc = await arc_client.get_usdc_balance(wallet_address)

        if idle_usdc > settings.usyc_deploy_threshold_usdc:
            deploy_amount = idle_usdc - (settings.usyc_deploy_threshold_usdc / 2)
            result = await deploy_idle_usdc_to_usyc(arc_client, deploy_amount, wallet_address)
            if result:
                log.info("usyc_auto_deployed", amount=deploy_amount, arc_scan=result["arc_scan_url"])
    except Exception as e:
        log.warning("usyc_auto_manage_failed", error=str(e))
