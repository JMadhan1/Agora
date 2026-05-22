"""Fetches and normalizes active Polymarket markets."""
from __future__ import annotations
import asyncio
import time
from datetime import datetime
import httpx
import structlog

log = structlog.get_logger()

GAMMA_BASE = "https://gamma-api.polymarket.com"


def _normalize_market(raw: dict) -> dict:
    """Normalize a Gamma API market response to a consistent dict."""
    outcome_prices = raw.get("outcomePrices", ["0.5", "0.5"])
    try:
        yes_price = float(outcome_prices[0]) if outcome_prices else 0.5
    except (ValueError, IndexError):
        yes_price = 0.5

    end_date = raw.get("endDate") or raw.get("endDateIso") or ""
    return {
        "id": raw.get("id", ""),
        "condition_id": raw.get("conditionId", raw.get("id", "")),
        "question": raw.get("question", ""),
        "category": raw.get("category", ""),
        "resolution_date": end_date,
        "current_yes_price": yes_price,
        "our_latest_estimate": 0.5,
        "our_confidence": 0.0,
        "volume": float(raw.get("volume", 0) or 0),
        "liquidity": float(raw.get("liquidity", 0) or 0),
        "yes_token_id": raw.get("clobTokenIds", [None])[0] if raw.get("clobTokenIds") else None,
        "no_token_id": raw.get("clobTokenIds", [None, None])[1] if raw.get("clobTokenIds") and len(raw.get("clobTokenIds", [])) > 1 else None,
        "resolved": raw.get("closed", False) or raw.get("resolved", False),
        "created_at": raw.get("createdAt", datetime.utcnow().isoformat()),
        "last_scouted": datetime.utcnow().isoformat(),
    }


class MarketFetcher:
    """Fetches active Polymarket markets via Gamma API."""

    _cache_markets: list[dict] = []
    _cache_ts: float = 0
    CACHE_TTL = 60  # seconds

    def __init__(self, gamma_api: str = GAMMA_BASE, clob_api: str = "https://clob.polymarket.com"):
        self.gamma_api = gamma_api.rstrip("/")
        self.clob_api = clob_api.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=30.0,
            headers={"User-Agent": "OracleSentinel/1.0"},
        )

    async def get_active_markets(self, limit: int = 200) -> list[dict]:
        """Fetches top markets by volume, returns normalized list."""
        now = time.time()
        if MarketFetcher._cache_markets and (now - MarketFetcher._cache_ts) < self.CACHE_TTL:
            return MarketFetcher._cache_markets[:limit]

        try:
            url = f"{self.gamma_api}/markets"
            params = {
                "active": "true",
                "closed": "false",
                "limit": min(limit, 500),
                "order": "volume",
                "ascending": "false",
            }
            resp = await self._client.get(url, params=params)
            resp.raise_for_status()
            raw = resp.json()

            # Gamma API returns list or { markets: [...] }
            if isinstance(raw, list):
                markets_raw = raw
            else:
                markets_raw = raw.get("markets", raw.get("data", []))

            markets = [_normalize_market(m) for m in markets_raw if m.get("question")]

            # Filter out very low volume / test markets
            markets = [m for m in markets if m["volume"] > 100 or m["liquidity"] > 50]

            MarketFetcher._cache_markets = markets
            MarketFetcher._cache_ts = now
            log.info("markets_fetched", count=len(markets))
            return markets[:limit]

        except Exception as e:
            log.error("market_fetch_failed", error=str(e))
            return MarketFetcher._cache_markets[:limit] if MarketFetcher._cache_markets else []

    async def get_market_detail(self, market_id: str) -> dict:
        """Fetches detailed info for a single market."""
        try:
            url = f"{self.gamma_api}/markets/{market_id}"
            resp = await self._client.get(url)
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            return _normalize_market(resp.json())
        except Exception as e:
            log.error("market_detail_failed", market_id=market_id, error=str(e))
            return {}

    async def get_categories(self) -> list[str]:
        """Returns distinct market categories."""
        markets = await self.get_active_markets(limit=500)
        cats = sorted(set(m["category"] for m in markets if m.get("category")))
        return cats

    async def close(self) -> None:
        await self._client.aclose()
