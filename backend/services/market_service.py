"""Market data service — merges Polymarket API with on-chain Sentinel data."""
from __future__ import annotations
import httpx
import structlog

log = structlog.get_logger()

GAMMA_API = "https://gamma-api.polymarket.com"


class MarketService:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "OracleSentinel/1.0"})

    async def get_live_polymarket_markets(self, limit: int = 50) -> list[dict]:
        """Fetches top active markets from Polymarket Gamma API."""
        try:
            resp = await self._client.get(
                f"{GAMMA_API}/markets",
                params={"active": "true", "closed": "false", "limit": limit, "order": "volume", "ascending": "false"},
            )
            resp.raise_for_status()
            raw = resp.json()
            markets = raw if isinstance(raw, list) else raw.get("markets", [])
            return [
                {
                    "id": m.get("id", ""),
                    "question": m.get("question", ""),
                    "category": m.get("category", ""),
                    "volume": float(m.get("volume", 0) or 0),
                    "current_yes_price": float((m.get("outcomePrices") or ["0.5"])[0]),
                    "resolution_date": m.get("endDate", ""),
                }
                for m in markets if m.get("question")
            ]
        except Exception as e:
            log.error("live_markets_fetch_failed", error=str(e))
            return []

    async def close(self):
        await self._client.aclose()
