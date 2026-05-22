"""
MarketDataScout — reads live Polymarket order books, recent trades, and
market metadata from the Gamma API and CLOB API to derive price-based
evidence for a prediction market.

Signals computed:
  - current_price (YES implied probability from Gamma market info)
  - volume_24h (market liquidity indicator)
  - large_order_detected (single trade > $5,000 in last 50 transactions)
  - orderbook_imbalance ((bid_size - ask_size) / (bid_size + ask_size))
  - price_momentum (>5% move in last 5 trades)
  - manipulation_risk (>30% price move AND volume spike)
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx
import structlog

from .base_scout import BaseScout, Evidence

logger = structlog.get_logger(__name__)

_HIGH_VOLUME_THRESHOLD = 10_000.0   # USD
_LARGE_TRADE_THRESHOLD = 5_000.0    # USD single trade
_PRICE_MOMENTUM_THRESHOLD = 0.05    # 5 %
_MANIPULATION_PRICE_MOVE = 0.30     # 30 %


class MarketDataScout(BaseScout):
    """
    Reads Polymarket's CLOB (Central Limit Order Book) and Gamma REST APIs
    to produce price-based evidence. The YES token price is used directly as
    supports_yes_probability; additional signals affect confidence.
    """

    scout_type = "market_data"
    reliability_score = 0.70

    def __init__(self, clob_api: str, gamma_api: str) -> None:
        # Strip trailing slashes for safe URL construction
        self._clob_api = clob_api.rstrip("/")
        self._gamma_api = gamma_api.rstrip("/")

    # ------------------------------------------------------------------
    # Data fetchers
    # ------------------------------------------------------------------

    async def _fetch_market_info(
        self, market_id: str, client: httpx.AsyncClient
    ) -> dict:
        """
        GET {gamma_api}/markets/{market_id}
        Returns empty dict on 404 or any network error.
        """
        url = f"{self._gamma_api}/markets/{market_id}"
        try:
            resp = await client.get(url, timeout=12.0)
            if resp.status_code == 404:
                logger.warning("market_data_scout.market_not_found", market_id=market_id)
                return {}
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("market_data_scout.gamma_failed", market_id=market_id, exc=str(exc))
            return {}

    async def _fetch_order_book(
        self, yes_token_id: str, client: httpx.AsyncClient
    ) -> dict:
        """
        GET {clob_api}/book?token_id={yes_token_id}
        Returns empty dict on failure.
        """
        url = f"{self._clob_api}/book"
        try:
            resp = await client.get(url, params={"token_id": yes_token_id}, timeout=12.0)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "market_data_scout.orderbook_failed",
                token_id=yes_token_id,
                exc=str(exc),
            )
            return {}

    async def _fetch_recent_trades(
        self, condition_id: str, client: httpx.AsyncClient
    ) -> list[dict]:
        """
        GET {clob_api}/trades?market={condition_id}&limit=50
        Returns empty list on failure.
        """
        url = f"{self._clob_api}/trades"
        try:
            resp = await client.get(
                url,
                params={"market": condition_id, "limit": 50},
                timeout=12.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("data", data.get("trades", []))
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "market_data_scout.trades_failed",
                condition_id=condition_id,
                exc=str(exc),
            )
            return []

    # ------------------------------------------------------------------
    # Signal computation helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_orderbook_imbalance(order_book: dict) -> Optional[float]:
        """
        Returns (bid_size - ask_size) / (bid_size + ask_size) or None if data
        is not available. Positive means more buying pressure.
        """
        bids = order_book.get("bids", [])
        asks = order_book.get("asks", [])
        if not bids and not asks:
            return None
        try:
            total_bid = sum(float(b.get("size", 0)) for b in bids)
            total_ask = sum(float(a.get("size", 0)) for a in asks)
            denom = total_bid + total_ask
            if denom == 0:
                return None
            return (total_bid - total_ask) / denom
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _detect_large_order(trades: list[dict]) -> tuple[bool, float]:
        """
        Returns (detected, largest_trade_usd).
        A trade is large if its USD value exceeds _LARGE_TRADE_THRESHOLD.
        """
        largest = 0.0
        for trade in trades:
            try:
                size = float(trade.get("size", 0))
                price = float(trade.get("price", 0))
                usd_value = size * price
                if usd_value > largest:
                    largest = usd_value
            except (TypeError, ValueError):
                continue
        return largest >= _LARGE_TRADE_THRESHOLD, largest

    @staticmethod
    def _detect_price_momentum(trades: list[dict]) -> tuple[bool, float]:
        """
        Returns (momentum_detected, price_change_fraction) from the last 5
        trades. Momentum is detected if |change| > _PRICE_MOMENTUM_THRESHOLD.
        """
        recent = trades[:5]
        prices: list[float] = []
        for t in recent:
            try:
                prices.append(float(t.get("price", 0)))
            except (TypeError, ValueError):
                continue
        if len(prices) < 2:
            return False, 0.0
        change = (prices[0] - prices[-1]) / prices[-1] if prices[-1] != 0 else 0.0
        return abs(change) > _PRICE_MOMENTUM_THRESHOLD, change

    @staticmethod
    def _detect_manipulation(trades: list[dict], volume_24h: float) -> bool:
        """
        Flags manipulation risk if price moved >30% across recent trades AND
        there is a volume spike (volume > 2× the median expected value).
        Heuristic: volume spike ≥ $50,000 qualifies for this check.
        """
        if not trades:
            return False
        prices: list[float] = []
        for t in trades:
            try:
                prices.append(float(t.get("price", 0)))
            except (TypeError, ValueError):
                continue
        if len(prices) < 2:
            return False
        price_range = max(prices) - min(prices)
        base = min(prices) if min(prices) > 0 else 1e-9
        price_move_frac = price_range / base
        volume_spike = volume_24h >= 50_000.0
        return price_move_frac > _MANIPULATION_PRICE_MOVE and volume_spike

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch_evidence(
        self,
        market_id: str,
        market_question: str,
        resolution_date: datetime,
    ) -> Evidence:
        async with httpx.AsyncClient() as client:
            market_info = await self._fetch_market_info(market_id, client)

        if not market_info:
            return Evidence(
                scout_type=self.scout_type,
                market_id=market_id,
                market_question=market_question,
                raw_data={},
                extracted_facts=[
                    f"Market {market_id} not found or Gamma API unavailable."
                ],
                supports_yes_probability=0.5,
                confidence=0.0,
                source_urls=[],
                timestamp=datetime.utcnow(),
                reliability_weight=self.reliability_score,
            )

        # ---- Parse market metadata ----
        outcome_prices = market_info.get("outcomePrices", [])
        try:
            current_price = float(outcome_prices[0]) if outcome_prices else 0.5
        except (TypeError, ValueError, IndexError):
            current_price = 0.5

        try:
            volume_24h = float(market_info.get("volume24hr", market_info.get("volume", 0)) or 0)
        except (TypeError, ValueError):
            volume_24h = 0.0

        condition_id = market_info.get("conditionId", market_info.get("condition_id", ""))
        clob_token_ids = market_info.get("clobTokenIds", market_info.get("clob_token_ids", []))
        yes_token_id = clob_token_ids[0] if clob_token_ids else ""

        # ---- Fetch order book and recent trades in parallel ----
        async with httpx.AsyncClient() as client:
            import asyncio as _asyncio
            order_book_task = _asyncio.create_task(
                self._fetch_order_book(yes_token_id, client) if yes_token_id else _noop_dict()
            )
            trades_task = _asyncio.create_task(
                self._fetch_recent_trades(condition_id, client) if condition_id else _noop_list()
            )
            order_book, recent_trades = await _asyncio.gather(order_book_task, trades_task)

        # ---- Compute signals ----
        large_order_detected, largest_trade_usd = self._detect_large_order(recent_trades)
        momentum_detected, price_change = self._detect_price_momentum(recent_trades)
        manipulation_risk = self._detect_manipulation(recent_trades, volume_24h)
        ob_imbalance = self._compute_orderbook_imbalance(order_book)

        # ---- Build extracted facts ----
        facts: list[str] = [
            f"Current YES price: {current_price:.4f} ({current_price * 100:.1f}% implied probability)",
            f"24h trading volume: ${volume_24h:,.2f}",
        ]

        if large_order_detected:
            facts.append(
                f"Large order detected: ${largest_trade_usd:,.0f} trade in last 50 transactions"
            )

        if ob_imbalance is not None:
            direction = "bid-heavy (buying pressure)" if ob_imbalance > 0 else "ask-heavy (selling pressure)"
            facts.append(
                f"Order book imbalance: {ob_imbalance:+.3f} ({direction})"
            )

        if momentum_detected:
            direction = "upward" if price_change > 0 else "downward"
            facts.append(
                f"Price momentum detected: {direction} move of {abs(price_change) * 100:.1f}% "
                "in last 5 trades"
            )

        if manipulation_risk:
            facts.append(
                "WARNING: Manipulation risk flagged — price moved >30% with high volume spike"
            )

        # ---- Compute confidence ----
        confidence = 0.8 if volume_24h >= _HIGH_VOLUME_THRESHOLD else 0.5
        if manipulation_risk:
            confidence = min(confidence, 0.35)

        # ---- Build source URLs ----
        source_urls = [f"{self._gamma_api}/markets/{market_id}"]
        if yes_token_id:
            source_urls.append(f"{self._clob_api}/book?token_id={yes_token_id}")

        return Evidence(
            scout_type=self.scout_type,
            market_id=market_id,
            market_question=market_question,
            raw_data={
                "current_price": current_price,
                "volume_24h": volume_24h,
                "large_order_detected": large_order_detected,
                "largest_trade_usd": largest_trade_usd,
                "orderbook_imbalance": ob_imbalance,
                "price_momentum": price_change,
                "manipulation_risk": manipulation_risk,
            },
            extracted_facts=facts,
            supports_yes_probability=current_price,
            confidence=confidence,
            source_urls=source_urls,
            timestamp=datetime.utcnow(),
            reliability_weight=self.reliability_score,
        )

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{self._gamma_api}/markets",
                    params={"limit": 1},
                    timeout=8.0,
                )
                return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False


# ---------------------------------------------------------------------------
# Coroutine helpers for parallel gather with no-op paths
# ---------------------------------------------------------------------------

async def _noop_dict() -> dict:
    return {}


async def _noop_list() -> list:
    return []
