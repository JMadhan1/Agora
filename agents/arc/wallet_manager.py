"""Circle Developer-Controlled Wallets for Oracle Sentinel agents."""
from __future__ import annotations
import asyncio
import json
from pathlib import Path
import httpx
import structlog

log = structlog.get_logger()

CIRCLE_BASE_URL = "https://api.circle.com/v1/w3s"
WALLETS_FILE = Path(".agent-wallets.json")


async def create_agent_wallets(circle_api_key: str, entity_secret: str) -> dict:
    """
    Creates three SCA wallets on ARC-TESTNET for Scout, Judge, Watchdog.
    Circle Tool: Developer-Controlled Wallets on Arc Testnet.
    Returns { scout: { address, walletId }, judge: {...}, watchdog: {...} }
    """
    headers = {
        "Authorization": f"Bearer {circle_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Step 1: Create wallet set
        ws_resp = await client.post(
            f"{CIRCLE_BASE_URL}/walletSets",
            headers=headers,
            json={
                "name": "Oracle Sentinel Agents",
                "entitySecretCiphertext": entity_secret,
            },
        )
        ws_resp.raise_for_status()
        wallet_set_id = ws_resp.json()["data"]["walletSet"]["id"]
        log.info("circle_wallet_set_created", wallet_set_id=wallet_set_id)

        # Step 2: Create 3 wallets
        agent_types = ["scout", "judge", "watchdog"]
        wallets = {}

        for agent_type in agent_types:
            w_resp = await client.post(
                f"{CIRCLE_BASE_URL}/wallets",
                headers=headers,
                json={
                    "blockchains": ["ARC-TESTNET"],
                    "accountType": "SCA",
                    "count": 1,
                    "walletSetId": wallet_set_id,
                    "metadata": [{"name": f"Oracle Sentinel {agent_type.capitalize()} Agent"}],
                    "entitySecretCiphertext": entity_secret,
                },
            )
            w_resp.raise_for_status()
            wallet_data = w_resp.json()["data"]["wallets"][0]
            wallets[agent_type] = {
                "walletId": wallet_data["id"],
                "address": wallet_data["address"],
                "blockchain": wallet_data.get("blockchain", "ARC-TESTNET"),
            }
            log.info(f"circle_wallet_created", agent=agent_type, address=wallet_data["address"])

        # Save to file
        WALLETS_FILE.write_text(json.dumps(wallets, indent=2))
        log.info("agent_wallets_saved", file=str(WALLETS_FILE))
        return wallets


async def load_or_create_wallets() -> dict:
    """Loads wallets from .agent-wallets.json if it exists, otherwise creates via Circle API."""
    if WALLETS_FILE.exists():
        try:
            data = json.loads(WALLETS_FILE.read_text())
            if all(k in data for k in ["scout", "judge", "watchdog"]):
                log.info("agent_wallets_loaded", file=str(WALLETS_FILE))
                return data
        except Exception as e:
            log.warning("wallet_file_corrupt", error=str(e))

    from config import settings
    if not settings.circle_api_key or not settings.circle_entity_secret:
        log.warning("circle_credentials_missing_using_deployer_wallet")
        deployer_wallet = {"address": "", "walletId": "deployer"}
        return {"scout": deployer_wallet, "judge": deployer_wallet, "watchdog": deployer_wallet}

    return await create_agent_wallets(settings.circle_api_key, settings.circle_entity_secret)


async def execute_contract_via_circle(
    wallet_id: str,
    circle_api_key: str,
    contract_address: str,
    abi_sig: str,
    params: list,
) -> str:
    """
    Executes a contract transaction via Circle's wallet API.
    Circle Tool: Developer-Controlled Wallets transaction execution.
    Returns tx hash.
    """
    headers = {
        "Authorization": f"Bearer {circle_api_key}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            f"{CIRCLE_BASE_URL}/transactions/contractExecution",
            headers=headers,
            json={
                "walletId": wallet_id,
                "contractAddress": contract_address,
                "abiFunctionSignature": abi_sig,
                "abiParameters": params,
                "fee": {"type": "level", "config": {"feeLevel": "MEDIUM"}},
            },
        )
        resp.raise_for_status()
        tx_id = resp.json()["data"]["id"]

        # Poll for completion (max 30s)
        for _ in range(15):
            await asyncio.sleep(2)
            status_resp = await client.get(
                f"{CIRCLE_BASE_URL}/transactions/{tx_id}",
                headers=headers,
            )
            status_resp.raise_for_status()
            tx_data = status_resp.json()["data"]["transaction"]
            state = tx_data.get("state", "")

            if state == "COMPLETE":
                tx_hash = tx_data.get("txHash", "")
                log.info("circle_tx_complete", tx_hash=tx_hash, abi_sig=abi_sig)
                return tx_hash
            elif state in ("FAILED", "CANCELLED", "DENIED"):
                raise RuntimeError(f"Circle transaction {state}: {tx_data.get('errorReason', '')}")

        raise TimeoutError(f"Circle transaction {tx_id} did not complete in 30s")
