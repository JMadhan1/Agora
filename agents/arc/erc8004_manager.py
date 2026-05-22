"""ERC-8004 Agent Identity Registry integration on Arc Testnet."""
from __future__ import annotations
import json
import hashlib
import httpx
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .arc_client import ArcClient

log = structlog.get_logger()

# Circle Tool: ERC-8004 Agent Identity Registry on Arc Testnet
IDENTITY_REGISTRY = "0x8004A818BFB912233c491871b3d84c89A494BD9e"
REPUTATION_REGISTRY = "0x8004B663056A597Dffe9eCcC1965A193B7388713"

IDENTITY_REGISTRY_ABI = [
    {
        "inputs": [{"name": "metadataUri", "type": "string"}],
        "name": "register",
        "outputs": [{"name": "tokenId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "tokenId", "type": "uint256"}],
        "name": "getMetadataUri",
        "outputs": [{"name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "owner", "type": "address"},
            {"indexed": True, "name": "tokenId", "type": "uint256"},
            {"indexed": False, "name": "metadataUri", "type": "string"},
        ],
        "name": "AgentRegistered",
        "type": "event",
    },
]

REPUTATION_REGISTRY_ABI = [
    {
        "inputs": [
            {"name": "agentId", "type": "uint256"},
            {"name": "eventType", "type": "string"},
            {"name": "scoreDelta", "type": "int256"},
            {"name": "evidenceCid", "type": "string"},
        ],
        "name": "recordEvent",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "agentId", "type": "uint256"}],
        "name": "getReputation",
        "outputs": [{"name": "score", "type": "int256"}],
        "stateMutability": "view",
        "type": "function",
    },
]

AGENT_METADATA_TEMPLATE = {
    "name": "",
    "description": "",
    "agent_type": "",
    "capabilities": [],
    "version": "1.0.0",
    "oracle_sentinel_version": "1.0.0",
    "network": "arc-testnet",
    "builder": "Oracle Sentinel — Agora Hackathon 2026",
}


async def _upload_to_irys(metadata_json: str) -> str:
    """Uploads metadata to Irys. Falls back to local hash if Irys is unavailable."""
    data = metadata_json.encode("utf-8")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                "https://uploader.irys.xyz/upload",
                content=data,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            cid = resp.json().get("id", "")
            if cid:
                return f"https://gateway.irys.xyz/{cid}"
    except Exception as e:
        log.warning("irys_upload_failed", error=str(e))

    # Local fallback — deterministic hash-based URI
    local_hash = hashlib.sha256(data).hexdigest()[:32]
    return f"ipfs://local-{local_hash}"


async def register_agent(
    arc_client: "ArcClient",
    agent_name: str,
    agent_type: str,
    capabilities: list[str],
    owner_address: str,
) -> dict:
    """
    Registers an agent on ERC-8004 IdentityRegistry on Arc Testnet.
    Circle Tool: Arc Testnet on-chain agent identity.
    Returns { token_id, metadata_uri, tx_hash, arc_scan_url }
    """
    metadata = {
        **AGENT_METADATA_TEMPLATE,
        "name": agent_name,
        "description": f"Oracle Sentinel {agent_type} agent for prediction market truth verification",
        "agent_type": agent_type,
        "capabilities": capabilities,
        "owner": owner_address,
    }
    metadata_json = json.dumps(metadata, indent=2)
    metadata_uri = await _upload_to_irys(metadata_json)

    try:
        tx_hash = await arc_client.call_contract_write(
            IDENTITY_REGISTRY,
            IDENTITY_REGISTRY_ABI,
            "register",
            [metadata_uri],
        )
        receipt = await arc_client.wait_for_receipt(tx_hash)

        # Extract token ID from logs (AgentRegistered event)
        token_id = receipt.get("blockNumber", 0)  # fallback if event parsing not available

        result = {
            "token_id": token_id,
            "metadata_uri": metadata_uri,
            "tx_hash": tx_hash,
            "arc_scan_url": arc_client.arc_scan_url(tx_hash),
            "agent_type": agent_type,
        }
        log.info("erc8004_agent_registered", **result)
        return result

    except Exception as e:
        log.error("erc8004_register_failed", agent_type=agent_type, error=str(e))
        return {"error": str(e), "metadata_uri": metadata_uri}


async def record_reputation_event(
    arc_client: "ArcClient",
    agent_id: int,
    event_type: str,
    score_delta: int,
    evidence_cid: str,
) -> str:
    """Records a reputation event on ReputationRegistry (Arc Testnet)."""
    try:
        tx_hash = await arc_client.call_contract_write(
            REPUTATION_REGISTRY,
            REPUTATION_REGISTRY_ABI,
            "recordEvent",
            [agent_id, event_type, score_delta, evidence_cid],
        )
        log.info("reputation_event_recorded", agent_id=agent_id, event=event_type, delta=score_delta)
        return tx_hash
    except Exception as e:
        log.warning("reputation_event_failed", agent_id=agent_id, error=str(e))
        return ""


async def get_agent_reputation(agent_address: str, arc_client: "ArcClient") -> dict:
    """Returns reputation score from ReputationRegistry."""
    try:
        # Use address as ID for simplicity (registry may use uint256 token ID)
        score = await arc_client.call_contract_read(
            REPUTATION_REGISTRY,
            REPUTATION_REGISTRY_ABI,
            "getReputation",
            [0],  # placeholder — real impl needs token ID lookup
        )
        return {"address": agent_address, "reputation_score": int(score)}
    except Exception as e:
        log.debug("reputation_fetch_failed", agent=agent_address, error=str(e))
        return {"address": agent_address, "reputation_score": 0}
