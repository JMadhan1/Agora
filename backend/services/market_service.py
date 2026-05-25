"""Market data service — merges Polymarket API with on-chain Sentinel data."""
from __future__ import annotations
import httpx
import structlog

log = structlog.get_logger()

GAMMA_API = "https://gamma-api.polymarket.com"

_SEED_MARKETS = [
    {"id": "seed-btc-100k", "question": "Will Bitcoin reach $100,000 before end of 2025?", "category": "Crypto", "volume": 5000000.0, "current_yes_price": 0.62, "resolution_date": "2025-12-31T00:00:00Z", "our_latest_estimate": 0.5, "our_confidence": 0.0, "last_scouted": None, "resolved": False, "actual_resolution": None, "created_at": "2025-01-01T00:00:00Z"},
    {"id": "seed-eth-flip-btc", "question": "Will Ethereum flip Bitcoin in market cap in 2025?", "category": "Crypto", "volume": 2000000.0, "current_yes_price": 0.12, "resolution_date": "2025-12-31T00:00:00Z", "our_latest_estimate": 0.5, "our_confidence": 0.0, "last_scouted": None, "resolved": False, "actual_resolution": None, "created_at": "2025-01-01T00:00:00Z"},
    {"id": "seed-fed-rate-cut", "question": "Will the Fed cut interest rates by July 2025?", "category": "Economics", "volume": 3000000.0, "current_yes_price": 0.45, "resolution_date": "2025-07-31T00:00:00Z", "our_latest_estimate": 0.5, "our_confidence": 0.0, "last_scouted": None, "resolved": False, "actual_resolution": None, "created_at": "2025-01-01T00:00:00Z"},
    {"id": "seed-trump-approval", "question": "Will Trump's approval rating exceed 50% in 2025?", "category": "Politics", "volume": 1500000.0, "current_yes_price": 0.35, "resolution_date": "2025-12-31T00:00:00Z", "our_latest_estimate": 0.5, "our_confidence": 0.0, "last_scouted": None, "resolved": False, "actual_resolution": None, "created_at": "2025-01-01T00:00:00Z"},
    {"id": "seed-arc-mainnet", "question": "Will Arc Mainnet launch before end of 2025?", "category": "Crypto", "volume": 500000.0, "current_yes_price": 0.78, "resolution_date": "2025-12-31T00:00:00Z", "our_latest_estimate": 0.5, "our_confidence": 0.0, "last_scouted": None, "resolved": False, "actual_resolution": None, "created_at": "2025-01-01T00:00:00Z"},
]


class MarketService:
    def __init__(self):
        self._client = httpx.AsyncClient(timeout=4.0, headers={"User-Agent": "OracleSentinel/1.0"})

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
            log.warning("live_markets_fetch_failed_using_seeds", error=str(e))
            return _SEED_MARKETS[:limit]

    async def close(self):
        await self._client.aclose()
