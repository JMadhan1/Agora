"""
IPFS / Irys publisher for Oracle Sentinel reasoning traces.

Attempts three upload strategies in order of preference:
  1. Irys (formerly Bundlr) permanent storage via uploader.irys.xyz
  2. NFT.Storage (IPFS pinning) as fallback
  3. Local content-addressed stub as last resort

The function never raises — callers can always proceed with a CID even if
persistent storage is temporarily unavailable.
"""
from __future__ import annotations

import hashlib

import httpx
import structlog

log = structlog.get_logger(__name__)

_IRYS_UPLOAD_URL = "https://uploader.irys.xyz/upload"
_IRYS_GATEWAY_URL = "https://gateway.irys.xyz/{cid}"
_NFT_STORAGE_URL = "https://api.nft.storage/upload"
_HTTP_TIMEOUT = 30


async def upload_to_irys(trace_json: str, private_key: str) -> str:
    """
    Upload *trace_json* to persistent storage and return a content identifier.

    Tries Irys → NFT.Storage → local stub. Never raises.

    Args:
        trace_json: The JSON-serialised reasoning trace string.
        private_key: Hex-encoded wallet private key (used for Irys auth
            if the endpoint requires it; sent as ``X-Private-Key`` header).

    Returns:
        A CID string: an Irys transaction ID, an IPFS v1 CID, or a local
        ``local-<hex>`` stub guaranteed never to be empty.
    """
    data = trace_json.encode("utf-8")

    # --- Strategy 1: Irys ---
    cid = await _try_irys(data, private_key)
    if cid:
        return cid

    # --- Strategy 2: NFT.Storage ---
    cid = await _try_nft_storage(data, private_key)
    if cid:
        return cid

    # --- Strategy 3: Local stub ---
    stub = _local_stub(data)
    log.warning("ipfs_publisher.using_local_stub", stub=stub)
    return stub


async def _try_irys(data: bytes, private_key: str) -> str | None:
    """Attempt upload to Irys. Returns transaction ID or None on failure."""
    headers = {
        "Content-Type": "application/json",
    }
    if private_key:
        headers["X-Private-Key"] = private_key

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(
                _IRYS_UPLOAD_URL,
                content=data,
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()
            tx_id: str = payload.get("id") or payload.get("txId") or ""
            if not tx_id:
                log.warning("ipfs_publisher.irys_no_id", payload=payload)
                return None

            # Verify the upload is retrievable.
            verify_url = _IRYS_GATEWAY_URL.format(cid=tx_id)
            verify_resp = await client.get(verify_url, timeout=15)
            if verify_resp.status_code not in (200, 206):
                log.warning(
                    "ipfs_publisher.irys_verify_failed",
                    tx_id=tx_id,
                    status=verify_resp.status_code,
                )
                # Return the ID anyway — Irys may take seconds to propagate.
                return tx_id

            log.info("ipfs_publisher.irys_success", tx_id=tx_id, verify_url=verify_url)
            return tx_id

    except httpx.HTTPStatusError as exc:
        log.warning(
            "ipfs_publisher.irys_http_error",
            status=exc.response.status_code,
            body=exc.response.text[:200],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("ipfs_publisher.irys_error", error=str(exc))

    return None


async def _try_nft_storage(data: bytes, api_key: str) -> str | None:
    """Attempt upload to NFT.Storage. Returns IPFS CID or None on failure."""
    headers = {
        "Content-Type": "application/json",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            resp = await client.post(
                _NFT_STORAGE_URL,
                content=data,
                headers=headers,
            )
            resp.raise_for_status()
            payload = resp.json()
            cid: str = (
                payload.get("value", {}).get("cid")
                or payload.get("cid")
                or ""
            )
            if not cid:
                log.warning("ipfs_publisher.nft_storage_no_cid", payload=payload)
                return None
            log.info("ipfs_publisher.nft_storage_success", cid=cid)
            return cid

    except httpx.HTTPStatusError as exc:
        log.warning(
            "ipfs_publisher.nft_storage_http_error",
            status=exc.response.status_code,
            body=exc.response.text[:200],
        )
    except Exception as exc:  # noqa: BLE001
        log.warning("ipfs_publisher.nft_storage_error", error=str(exc))

    return None


def _local_stub(data: bytes) -> str:
    """Return a deterministic local content-addressed stub identifier."""
    digest = hashlib.sha256(data).hexdigest()[:16]
    return f"local-{digest}"
