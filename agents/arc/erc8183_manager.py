"""ERC-8183 Agentic Commerce — job lifecycle on Arc Testnet."""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta, timezone
import structlog
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .arc_client import ArcClient

log = structlog.get_logger()

# Circle Tool: ERC-8183 Agentic Commerce on Arc Testnet
AGENTIC_COMMERCE = "0x0747EEf0706327138c69792bF28Cd525089e4583"
USDC_ADDRESS = "0x3600000000000000000000000000000000000000"

AGENTIC_COMMERCE_ABI = [
    {
        "inputs": [
            {"name": "description", "type": "string"},
            {"name": "budgetUsdc", "type": "uint256"},
            {"name": "deadlineTimestamp", "type": "uint256"},
        ],
        "name": "createJob",
        "outputs": [{"name": "jobId", "type": "bytes32"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "jobId", "type": "bytes32"},
            {"name": "deliverableHash", "type": "bytes32"},
            {"name": "deliverableCid", "type": "string"},
        ],
        "name": "submitDeliverable",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "jobId", "type": "bytes32"}],
        "name": "completeJob",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [
            {"name": "jobId", "type": "bytes32"},
            {"name": "reason", "type": "string"},
        ],
        "name": "failJob",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "jobId", "type": "bytes32"}],
        "name": "getJob",
        "outputs": [
            {
                "components": [
                    {"name": "jobId", "type": "bytes32"},
                    {"name": "client", "type": "address"},
                    {"name": "assignedAgent", "type": "address"},
                    {"name": "description", "type": "string"},
                    {"name": "budgetUsdc", "type": "uint256"},
                    {"name": "deadline", "type": "uint256"},
                    {"name": "status", "type": "uint8"},
                    {"name": "deliverableHash", "type": "bytes32"},
                    {"name": "deliverableCid", "type": "string"},
                    {"name": "createdAt", "type": "uint256"},
                    {"name": "completedAt", "type": "uint256"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "anonymous": False,
        "inputs": [
            {"indexed": True, "name": "jobId", "type": "bytes32"},
            {"indexed": True, "name": "client", "type": "address"},
            {"indexed": False, "name": "budget", "type": "uint256"},
            {"indexed": False, "name": "deadline", "type": "uint256"},
        ],
        "name": "JobCreated",
        "type": "event",
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

JOB_STATUS_MAP = {0: "CREATED", 1: "FUNDED", 2: "AGENT_ASSIGNED", 3: "DELIVERABLE_SUBMITTED", 4: "COMPLETED", 5: "FAILED"}


async def create_verification_job(
    arc_client: "ArcClient",
    market_id: str,
    market_question: str,
    budget_usdc: float,
    deadline_hours: int = 24,
    client_address: str = "",
) -> dict:
    """
    Creates an ERC-8183 job on Arc with USDC escrow.
    Circle Tool: Arc Testnet Agentic Commerce — escrow + payment.
    """
    try:
        budget_raw = int(budget_usdc * 1e6)
        deadline_ts = int((datetime.now(timezone.utc) + timedelta(hours=deadline_hours)).timestamp())
        description = f"Oracle Sentinel verification: {market_question[:200]} (market_id: {market_id})"

        # Step 1: Approve USDC to AgenticCommerce
        approve_tx = await arc_client.call_contract_write(
            USDC_ADDRESS, ERC20_ABI, "approve",
            [arc_client.w3.to_checksum_address(AGENTIC_COMMERCE), budget_raw]
        )
        await arc_client.wait_for_receipt(approve_tx)

        # Step 2: Create job
        tx_hash = await arc_client.call_contract_write(
            AGENTIC_COMMERCE, AGENTIC_COMMERCE_ABI, "createJob",
            [description, budget_raw, deadline_ts]
        )
        receipt = await arc_client.wait_for_receipt(tx_hash)

        # Extract job ID from logs
        job_id = "0x" + receipt.get("transactionHash", tx_hash).hex()[-64:] if hasattr(receipt.get("transactionHash", ""), "hex") else tx_hash

        result = {
            "job_id": job_id,
            "tx_hash": tx_hash,
            "arc_scan_url": arc_client.arc_scan_url(tx_hash),
            "escrow_amount": budget_usdc,
            "market_id": market_id,
        }
        log.info("erc8183_job_created", **result)
        return result

    except Exception as e:
        log.error("erc8183_job_create_failed", market_id=market_id, error=str(e))
        return {"error": str(e)}


async def submit_deliverable(
    arc_client: "ArcClient",
    job_id: str,
    deliverable_hash: bytes,
    ipfs_cid: str,
    agent_address: str,
) -> str:
    """Submits deliverable hash to ERC-8183 contract."""
    try:
        job_id_bytes = bytes.fromhex(job_id.lstrip("0x")).ljust(32, b"\x00")[:32]
        hash_bytes = deliverable_hash[:32] if len(deliverable_hash) >= 32 else deliverable_hash.ljust(32, b"\x00")
        tx_hash = await arc_client.call_contract_write(
            AGENTIC_COMMERCE, AGENTIC_COMMERCE_ABI, "submitDeliverable",
            [job_id_bytes, hash_bytes, ipfs_cid]
        )
        log.info("erc8183_deliverable_submitted", job_id=job_id, tx_hash=tx_hash)
        return tx_hash
    except Exception as e:
        log.error("erc8183_submit_failed", job_id=job_id, error=str(e))
        return ""


async def complete_job_and_release_payment(arc_client: "ArcClient", job_id: str) -> dict:
    """Releases USDC escrow to agent upon job completion."""
    try:
        job_id_bytes = bytes.fromhex(job_id.lstrip("0x")).ljust(32, b"\x00")[:32]
        tx_hash = await arc_client.call_contract_write(
            AGENTIC_COMMERCE, AGENTIC_COMMERCE_ABI, "completeJob", [job_id_bytes]
        )
        receipt = await arc_client.wait_for_receipt(tx_hash)
        return {
            "tx_hash": tx_hash,
            "arc_scan_url": arc_client.arc_scan_url(tx_hash),
            "job_id": job_id,
        }
    except Exception as e:
        log.error("erc8183_complete_failed", job_id=job_id, error=str(e))
        return {"error": str(e)}


async def get_job_status(arc_client: "ArcClient", job_id: str) -> str:
    """Returns job status string."""
    try:
        job_id_bytes = bytes.fromhex(job_id.lstrip("0x")).ljust(32, b"\x00")[:32]
        job = await arc_client.call_contract_read(
            AGENTIC_COMMERCE, AGENTIC_COMMERCE_ABI, "getJob", [job_id_bytes]
        )
        status_int = job[6] if isinstance(job, (list, tuple)) else 0
        return JOB_STATUS_MAP.get(status_int, "UNKNOWN")
    except Exception as e:
        log.debug("job_status_failed", job_id=job_id, error=str(e))
        return "UNKNOWN"
