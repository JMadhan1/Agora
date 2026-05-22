"""Polymarket CLOB (Central Limit Order Book) API client."""
from __future__ import annotations
import asyncio
import json
import structlog
import httpx
import websockets

log = structlog.get_logger()

CLOB_BASE = "https://clob.polymarket.com"
WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


class ClobClient:
    """Async client for Polymarket CLOB API."""

    def __init__(self, base_url: str = CLOB_BASE):
        self.base_url = base_url.rstrip("/")
        self._client = httpx.AsyncClient(
            timeout=20.0,
            headers={"User-Agent": "OracleSentinel/1.0"},
        )

    async def _get(self, path: str, params: dict | None = None, retries: int = 3) -> dict | list:
        url = f"{self.base_url}{path}"
        for attempt in range(retries):
            try:
                resp = await self._client.get(url, params=params)
                if resp.status_code in (500, 502, 503, 504) and attempt < retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                resp.raise_for_status()
                return resp.json()
            except httpx.HTTPStatusError as e:
                if attempt == retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
            except Exception as e:
                if attempt == retries - 1:
                    log.error("clob_get_failed", path=path, error=str(e))
                    raise
                await asyncio.sleep(2 ** attempt)
        return {}

    async def get_market(self, condition_id: str) -> dict:
        return await self._get(f"/markets/{condition_id}")

    async def get_order_book(self, token_id: str) -> dict:
        return await self._get("/book", params={"token_id": token_id})

    async def get_trades(self, condition_id: str, limit: int = 50) -> list[dict]:
        result = await self._get("/trades", params={"market": condition_id, "limit": limit})
        return result if isinstance(result, list) else result.get("data", [])

    async def get_markets(self, next_cursor: str = "") -> dict:
        params: dict = {"limit": 100}
        if next_cursor:
            params["next_cursor"] = next_cursor
        return await self._get("/markets", params=params)

    async def subscribe_market(self, market_id: str, callback) -> None:
        """WebSocket subscription to live market updates."""
        subscribe_msg = json.dumps({
            "assets_ids": [market_id],
            "type": "market",
        })
        try:
            async with websockets.connect(WS_URL) as ws:
                await ws.send(subscribe_msg)
                log.info("polymarket_ws_subscribed", market_id=market_id)
                async for message in ws:
                    try:
                        data = json.loads(message)
                        await callback(data)
                    except Exception as e:
                        log.warning("ws_callback_error", error=str(e))
        except Exception as e:
            log.error("polymarket_ws_failed", market_id=market_id, error=str(e))

    async def close(self) -> None:
        await self._client.aclose()
