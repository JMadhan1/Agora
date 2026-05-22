"""
Arc Testnet attestation helper.

Commits Bayesian inference results as immutable on-chain records to the
AttestationVault contract deployed on Arc Testnet (chainId 5042002).

Flow
----
1. Compute keccak256 of the reasoning trace → trace_hash (bytes32).
2. Check whether that hash already exists on-chain (idempotency guard).
3. Call AttestationVault.commitAttestation(marketId, traceHash, ipfsCid, confidence).
4. Wait for receipt and return a structured AttestationResult.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import structlog

from .arc_client import ArcClient

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Minimal AttestationVault ABI — only the functions we need
# ---------------------------------------------------------------------------

ATTESTATION_VAULT_ABI = [
    # commitAttestation(string marketId, bytes32 traceHash, string ipfsCid, uint8 confidence)
    {
        "inputs": [
            {"internalType": "string", "name": "marketId", "type": "string"},
            {"internalType": "bytes32", "name": "traceHash", "type": "bytes32"},
            {"internalType": "string", "name": "ipfsCid", "type": "string"},
            {"internalType": "uint8", "name": "confidence", "type": "uint8"},
        ],
        "name": "commitAttestation",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    # hashExists(bytes32 traceHash) → bool
    {
        "inputs": [
            {"internalType": "bytes32", "name": "traceHash", "type": "bytes32"}
        ],
        "name": "hashExists",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
    # getAttestation(bytes32 traceHash) → (string marketId, string ipfsCid, uint8 confidence, address attester, uint256 timestamp)
    {
        "inputs": [
            {"internalType": "bytes32", "name": "traceHash", "type": "bytes32"}
        ],
        "name": "getAttestation",
        "outputs": [
            {"internalType": "string", "name": "marketId", "type": "string"},
            {"internalType": "string", "name": "ipfsCid", "type": "string"},
            {"internalType": "uint8", "name": "confidence", "type": "uint8"},
            {"internalType": "address", "name": "attester", "type": "address"},
            {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    # AttestationCommitted event
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "bytes32",
                "name": "traceHash",
                "type": "bytes32",
            },
            {
                "indexed": True,
                "internalType": "string",
                "name": "marketId",
                "type": "string",
            },
            {
                "indexed": False,
                "internalType": "string",
                "name": "ipfsCid",
                "type": "string",
            },
            {
                "indexed": False,
                "internalType": "uint8",
                "name": "confidence",
                "type": "uint8",
            },
            {
                "indexed": False,
                "internalType": "address",
                "name": "attester",
                "type": "address",
            },
        ],
        "name": "AttestationCommitted",
        "type": "event",
    },
]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class AttestationResult:
    """Structured result returned after a successful on-chain attestation."""

    tx_hash: str
    arc_scan_url: str
    block_number: Optional[int]
    timestamp: datetime
    market_id: str
    trace_hash: str          # hex string representation of the bytes32
    ipfs_cid: str
    confidence: int          # 0–100
    attester: str = field(default="")

    def __str__(self) -> str:
        return (
            f"AttestationResult("
            f"market={self.market_id!r}, "
            f"confidence={self.confidence}, "
            f"block={self.block_number}, "
            f"tx={self.tx_hash[:12]}…, "
            f"scan={self.arc_scan_url})"
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def commit_attestation(
    arc_client: ArcClient,
    market_id: str,
    trace_hash: bytes,
    ipfs_cid: str,
    confidence: int,
    vault_address: str,
) -> Optional[AttestationResult]:
    """
    Commit a Bayesian inference attestation to the AttestationVault on Arc Testnet.

    Parameters
    ----------
    arc_client:
        An initialised and connected ArcClient instance.
    market_id:
        The Polymarket condition/market identifier string.
    trace_hash:
        32-byte keccak256 digest of the agent's reasoning trace (bytes).
    ipfs_cid:
        IPFS CID of the full trace JSON pinned off-chain.
    confidence:
        Integer 0–100 representing the agent's calibrated confidence.
    vault_address:
        Deployed AttestationVault contract address on Arc Testnet.

    Returns
    -------
    AttestationResult on success, None if the hash already exists on-chain.
    """
    if not vault_address:
        log.error(
            "commit_attestation_skipped",
            reason="vault_address_empty",
            market_id=market_id,
        )
        return None

    # Clamp confidence to valid uint8 range
    confidence = max(0, min(100, confidence))

    # Represent trace_hash as a hex string for logging
    trace_hash_hex: str = trace_hash.hex() if isinstance(trace_hash, (bytes, bytearray)) else trace_hash

    log.info(
        "commit_attestation_start",
        market_id=market_id,
        trace_hash=trace_hash_hex,
        ipfs_cid=ipfs_cid,
        confidence=confidence,
        vault_address=vault_address,
    )

    # ------------------------------------------------------------------
    # 1. Idempotency check — skip if already committed
    # ------------------------------------------------------------------
    try:
        already_exists: bool = await arc_client.call_contract_read(
            vault_address,
            ATTESTATION_VAULT_ABI,
            "hashExists",
            [trace_hash if isinstance(trace_hash, bytes) else bytes.fromhex(trace_hash_hex)],
        )
    except Exception as e:
        log.warning(
            "hash_exists_check_failed",
            market_id=market_id,
            trace_hash=trace_hash_hex,
            error=str(e),
        )
        # Proceed conservatively — attempt the commit; the contract will revert on dup
        already_exists = False

    if already_exists:
        log.info(
            "attestation_already_exists",
            market_id=market_id,
            trace_hash=trace_hash_hex,
        )
        return None

    # ------------------------------------------------------------------
    # 2. Commit the attestation
    # ------------------------------------------------------------------
    trace_hash_bytes: bytes = (
        trace_hash
        if isinstance(trace_hash, (bytes, bytearray))
        else bytes.fromhex(trace_hash_hex)
    )

    try:
        tx_hash_hex = await arc_client.call_contract_write(
            vault_address,
            ATTESTATION_VAULT_ABI,
            "commitAttestation",
            [market_id, trace_hash_bytes, ipfs_cid, confidence],
        )
    except Exception as e:
        log.error(
            "commit_attestation_failed",
            market_id=market_id,
            trace_hash=trace_hash_hex,
            error=str(e),
        )
        raise

    # ------------------------------------------------------------------
    # 3. Wait for receipt
    # ------------------------------------------------------------------
    block_number: Optional[int] = None
    try:
        receipt = await arc_client.wait_for_receipt(tx_hash_hex)
        block_number = receipt.get("blockNumber")
        if receipt.get("status") == 0:
            log.error(
                "commit_attestation_reverted",
                market_id=market_id,
                tx_hash=tx_hash_hex,
                block_number=block_number,
            )
            raise RuntimeError(
                f"AttestationVault.commitAttestation reverted in tx {tx_hash_hex}"
            )
    except RuntimeError:
        raise
    except Exception as e:
        # Receipt polling timed out — tx may still confirm; log and continue
        log.warning(
            "receipt_wait_failed",
            market_id=market_id,
            tx_hash=tx_hash_hex,
            error=str(e),
        )

    arc_scan_url = arc_client.arc_scan_url(tx_hash_hex)

    result = AttestationResult(
        tx_hash=tx_hash_hex,
        arc_scan_url=arc_scan_url,
        block_number=block_number,
        timestamp=datetime.utcnow(),
        market_id=market_id,
        trace_hash=trace_hash_hex,
        ipfs_cid=ipfs_cid,
        confidence=confidence,
        attester=arc_client.address,
    )

    log.info(
        "commit_attestation_success",
        market_id=market_id,
        trace_hash=trace_hash_hex,
        tx_hash=tx_hash_hex,
        block_number=block_number,
        confidence=confidence,
        arc_scan_url=arc_scan_url,
    )
    return result
