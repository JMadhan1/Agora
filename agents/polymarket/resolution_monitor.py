"""Monitors Polymarket for market resolutions."""
from __future__ import annotations
import asyncio
import httpx
import structlog

log = structlog.get_logger()


class ResolutionMonitor:
    """Polls Polymarket Gamma API for market resolution status."""

    def __init__(self, gamma_api: str = "https://gamma-api.polymarket.com"):
        self.gamma_api = gamma_api.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": "OracleSentinel/1.0"},
        )

    async def check_resolution(self, market_id: str) -> dict | None:
        """Returns resolution dict if market is resolved, else None."""
        try:
            resp = await self._client.get(f"{self.gamma_api}/markets/{market_id}")
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()

            resolved = data.get("closed", False) or data.get("resolved", False)
            resolution = data.get("resolution") or data.get("outcome", "")

            if resolved and resolution:
                return {
                    "market_id": market_id,
                    "resolution": resolution.upper(),
                    "resolved_at": data.get("resolutionTime", data.get("endDate", "")),
                }
        except Exception as e:
            log.debug("resolution_check_failed", market_id=market_id, error=str(e))
        return None

    async def get_newly_resolved(self, market_ids: list[str]) -> list[dict]:
        """
        Checks all market IDs in parallel (semaphore-limited to 10 concurrent).
        Returns list of resolved market dicts.
        """
        sem = asyncio.Semaphore(10)

        async def _check(mid: str) -> dict | None:
            async with sem:
                return await self.check_resolution(mid)

        results = await asyncio.gather(*[_check(mid) for mid in market_ids], return_exceptions=True)
        return [r for r in results if isinstance(r, dict)]

    async def close(self) -> None:
        await self._client.aclose()
