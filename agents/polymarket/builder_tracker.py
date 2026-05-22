"""Tracks Polymarket V2 builder fees attributed to Oracle Sentinel."""
from __future__ import annotations
import httpx
import structlog

log = structlog.get_logger()


class BuilderTracker:
    """Tracks builder fee attribution from Polymarket V2."""

    def __init__(self, gamma_api: str = "https://gamma-api.polymarket.com"):
        self.gamma_api = gamma_api.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": "OracleSentinel/1.0"},
        )

    async def get_builder_fees(self, builder_code: str) -> dict:
        """Fetch total builder fees earned for this builder code."""
        if not builder_code:
            return {"total_usdc_earned": 0.0, "trades_attributed": 0, "last_updated": ""}
        try:
            url = f"{self.gamma_api}/builders/{builder_code}/fees"
            resp = await self._client.get(url)
            if resp.status_code == 404:
                return {"total_usdc_earned": 0.0, "trades_attributed": 0, "last_updated": ""}
            resp.raise_for_status()
            data = resp.json()
            return {
                "total_usdc_earned": float(data.get("totalFees", 0) or 0),
                "trades_attributed": int(data.get("totalTrades", 0) or 0),
                "last_updated": data.get("updatedAt", ""),
            }
        except Exception as e:
            log.debug("builder_fees_fetch_failed", builder_code=builder_code, error=str(e))
            return {"total_usdc_earned": 0.0, "trades_attributed": 0, "last_updated": ""}

    async def close(self) -> None:
        await self._client.aclose()
