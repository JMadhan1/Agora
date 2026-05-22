"""
OnchainScout — gathers on-chain and crypto-native evidence for prediction
markets using Polygon RPC, CoinGecko, and Snapshot GraphQL.

Market type classification drives which data sources are queried:
  CRYPTO_PRICE      → CoinGecko price feed
  GOVERNANCE_VOTE   → Snapshot.org GraphQL proposals
  DEFI_EVENT        → Polygon eth_getLogs for common DeFi signatures
  TOKEN_LAUNCH      → CoinGecko markets list
  All others        → neutral evidence (confidence=0.3)
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Optional

import httpx
import structlog
from groq import AsyncGroq
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

from .base_scout import BaseScout, Evidence

logger = structlog.get_logger(__name__)

_GROQ_MODEL = "llama-3.1-8b-instant"
_POLYGON_RPC = "https://polygon-rpc.com"
_COINGECKO_PRICE = "https://api.coingecko.com/api/v3/simple/price"
_COINGECKO_MARKETS = "https://api.coingecko.com/api/v3/coins/markets"
_SNAPSHOT_GQL = "https://hub.snapshot.org/graphql"

_MARKET_TYPES = frozenset(
    [
        "CRYPTO_PRICE",
        "GOVERNANCE_VOTE",
        "TOKEN_LAUNCH",
        "DEFI_EVENT",
        "SPORTS",
        "POLITICS",
        "MACRO_ECONOMIC",
        "OTHER",
    ]
)

# Common DeFi event topic hashes (keccak256 of signature)
_DEFI_TOPICS = {
    "Swap":     "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822",
    "Deposit":  "0xe1fffcc4923d04b559f4d29a8bfc6cda04eb5b0d3c460751c2402c5c5cc9109c",
    "Withdraw": "0x884edad9ce6fa2440d8a54cc123490eb96d2768479d49ff9c7366125a9424364",
    "Liquidation": "0xe413a321e8681d831f4dbccbca790d2952b56f977908e45be37335533e005286",
}


class OnchainScout(BaseScout):
    """
    Reads blockchain state and crypto-market data to assess prediction market
    probabilities. Uses Web3.py (async) for Polygon and httpx for REST APIs.
    """

    scout_type = "onchain"
    reliability_score = 0.95

    def __init__(self, groq_api_key: str) -> None:
        self._groq_client = AsyncGroq(api_key=groq_api_key)
        self._w3 = AsyncWeb3(AsyncHTTPProvider(_POLYGON_RPC))

    # ------------------------------------------------------------------
    # Market classification
    # ------------------------------------------------------------------

    async def _classify_market_type(self, question: str) -> str:
        prompt = (
            "Classify this prediction market question into exactly one category.\n"
            "Categories: CRYPTO_PRICE | GOVERNANCE_VOTE | TOKEN_LAUNCH | DEFI_EVENT | "
            "SPORTS | POLITICS | MACRO_ECONOMIC | OTHER\n"
            f"Question: {question}\n\n"
            "Return only the category name, nothing else."
        )
        try:
            resp = await self._groq_client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=20,
                temperature=0.0,
            )
            raw = resp.choices[0].message.content.strip().upper()
            # Normalise: extract first matching token
            for mtype in _MARKET_TYPES:
                if mtype in raw:
                    return mtype
            return "OTHER"
        except Exception as exc:  # noqa: BLE001
            logger.warning("onchain_scout.classify_failed", exc=str(exc))
            return "OTHER"

    # ------------------------------------------------------------------
    # CRYPTO_PRICE handlers
    # ------------------------------------------------------------------

    async def _extract_coin_id(self, question: str) -> Optional[str]:
        """Ask Groq for the CoinGecko coin id implied by the question."""
        prompt = (
            "What is the CoinGecko coin ID for the cryptocurrency mentioned in this "
            "prediction market question? Return only the lowercase coin ID (e.g. 'bitcoin', "
            "'ethereum', 'matic-network'). If unclear return 'UNKNOWN'.\n"
            f"Question: {question}"
        )
        try:
            resp = await self._groq_client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=30,
                temperature=0.0,
            )
            coin_id = resp.choices[0].message.content.strip().lower()
            if coin_id == "unknown" or not coin_id:
                return None
            # Sanitise to CoinGecko id format
            coin_id = re.sub(r"[^a-z0-9\-]", "", coin_id)
            return coin_id or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("onchain_scout.coin_id_failed", exc=str(exc))
            return None

    async def _extract_price_target(self, question: str) -> Optional[float]:
        """Return the numeric price threshold from the question, or None."""
        # Try to find a dollar amount in the question
        match = re.search(r"\$\s*([\d,]+(?:\.\d+)?)", question)
        if match:
            try:
                return float(match.group(1).replace(",", ""))
            except ValueError:
                pass
        return None

    async def _handle_crypto_price(
        self, question: str, client: httpx.AsyncClient
    ) -> tuple[float, float, list[str], list[str]]:
        """
        Returns (supports_yes, confidence, facts, source_urls).
        Fetches current price from CoinGecko and evaluates whether it supports
        the YES resolution based on the price target in the question.
        """
        coin_id = await self._extract_coin_id(question)
        if not coin_id:
            return 0.5, 0.2, ["Could not identify cryptocurrency from question."], []

        try:
            resp = await client.get(
                _COINGECKO_PRICE,
                params={"ids": coin_id, "vs_currencies": "usd"},
                timeout=12.0,
            )
            resp.raise_for_status()
            data = resp.json()
            current_price = data.get(coin_id, {}).get("usd")
            if current_price is None:
                return 0.5, 0.2, [f"No price data for '{coin_id}' on CoinGecko."], []

            facts = [f"Current {coin_id} price: ${current_price:,.2f} USD (CoinGecko)"]
            source_urls = [f"{_COINGECKO_PRICE}?ids={coin_id}&vs_currencies=usd"]

            target = await self._extract_price_target(question)
            if target is not None:
                above = current_price >= target
                supports_yes = 0.8 if above else 0.2
                direction = "above" if above else "below"
                facts.append(
                    f"Price target ${target:,.2f}: current price is {direction} target "
                    f"→ {'supports' if above else 'contradicts'} YES."
                )
                return supports_yes, 0.85, facts, source_urls

            # No explicit target: neutral but slightly informative
            return 0.5, 0.5, facts, source_urls

        except Exception as exc:  # noqa: BLE001
            logger.warning("onchain_scout.coingecko_failed", exc=str(exc))
            return 0.5, 0.1, ["CoinGecko request failed."], []

    # ------------------------------------------------------------------
    # GOVERNANCE_VOTE handlers
    # ------------------------------------------------------------------

    async def _handle_governance_vote(
        self, question: str, client: httpx.AsyncClient
    ) -> tuple[float, float, list[str], list[str]]:
        # Extract keywords for Snapshot search
        keywords = re.findall(r"\b[A-Za-z]{4,}\b", question)[:6]
        search_term = " ".join(keywords)

        gql_query = """
        query Proposals($keyword: String!) {
          proposals(
            first: 5
            skip: 0
            where: { title_contains: $keyword, state_in: ["active", "closed"] }
            orderBy: "created"
            orderDirection: desc
          ) {
            id title state scores_total scores votes quorum
          }
        }
        """
        try:
            resp = await client.post(
                _SNAPSHOT_GQL,
                json={"query": gql_query, "variables": {"keyword": search_term}},
                timeout=15.0,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            proposals = resp.json().get("data", {}).get("proposals", [])
            if not proposals:
                return 0.5, 0.2, ["No matching governance proposals found on Snapshot."], []

            facts: list[str] = []
            source_urls: list[str] = []
            yes_signals: list[float] = []

            for p in proposals:
                state = p.get("state", "unknown")
                votes = p.get("votes", 0)
                scores_total = p.get("scores_total") or 0
                quorum = p.get("quorum") or 0
                pid = p.get("id", "")
                title = p.get("title", "")[:80]

                url = f"https://snapshot.org/#/proposal/{pid}"
                source_urls.append(url)
                facts.append(f"Proposal '{title}' — state={state}, votes={votes}, total score={scores_total:.0f}")

                if state == "closed" and scores_total > 0:
                    # Check if quorum met and majority passed
                    quorum_met = scores_total >= quorum if quorum > 0 else True
                    if quorum_met:
                        yes_signals.append(0.85)  # passed
                    else:
                        yes_signals.append(0.15)  # failed quorum
                elif state == "active":
                    yes_signals.append(0.5)  # uncertain

            supports_yes = sum(yes_signals) / len(yes_signals) if yes_signals else 0.5
            return supports_yes, 0.75, facts, source_urls

        except Exception as exc:  # noqa: BLE001
            logger.warning("onchain_scout.snapshot_failed", exc=str(exc))
            return 0.5, 0.1, ["Snapshot GraphQL request failed."], []

    # ------------------------------------------------------------------
    # DEFI_EVENT handlers
    # ------------------------------------------------------------------

    async def _handle_defi_event(
        self, question: str
    ) -> tuple[float, float, list[str], list[str]]:
        """
        Queries Polygon for recent occurrences of common DeFi events.
        Uses eth_getLogs from the last ~1000 blocks.
        """
        try:
            latest_block = await self._w3.eth.block_number
            from_block = max(0, latest_block - 1000)

            event_counts: dict[str, int] = {}
            for event_name, topic in _DEFI_TOPICS.items():
                try:
                    logs = await self._w3.eth.get_logs(
                        {
                            "fromBlock": from_block,
                            "toBlock": "latest",
                            "topics": [topic],
                        }
                    )
                    event_counts[event_name] = len(logs)
                except Exception:  # noqa: BLE001
                    event_counts[event_name] = 0

            facts = [
                f"Polygon recent DeFi events (last ~1000 blocks): "
                + ", ".join(f"{k}={v}" for k, v in event_counts.items())
            ]
            facts.append(f"Latest Polygon block: {latest_block:,}")

            total_events = sum(event_counts.values())
            # High event volume suggests active DeFi = mild YES signal
            if total_events > 500:
                supports_yes = 0.65
                confidence = 0.6
            elif total_events > 100:
                supports_yes = 0.55
                confidence = 0.4
            else:
                supports_yes = 0.5
                confidence = 0.3

            return supports_yes, confidence, facts, [_POLYGON_RPC]

        except Exception as exc:  # noqa: BLE001
            logger.warning("onchain_scout.defi_event_failed", exc=str(exc))
            return 0.5, 0.1, ["Polygon RPC query failed."], []

    # ------------------------------------------------------------------
    # TOKEN_LAUNCH handlers
    # ------------------------------------------------------------------

    async def _handle_token_launch(
        self, question: str, client: httpx.AsyncClient
    ) -> tuple[float, float, list[str], list[str]]:
        """Check CoinGecko markets list for a recently-launched token."""
        coin_id = await self._extract_coin_id(question)
        if not coin_id:
            return 0.5, 0.2, ["Could not identify token from question."], []
        try:
            resp = await client.get(
                _COINGECKO_MARKETS,
                params={
                    "vs_currency": "usd",
                    "ids": coin_id,
                    "order": "market_cap_desc",
                    "per_page": 1,
                    "page": 1,
                    "sparkline": "false",
                },
                timeout=12.0,
            )
            resp.raise_for_status()
            coins = resp.json()
            if not coins:
                return 0.2, 0.7, [f"Token '{coin_id}' not yet listed on CoinGecko."], []

            coin = coins[0]
            name = coin.get("name", coin_id)
            price = coin.get("current_price", 0)
            mcap = coin.get("market_cap", 0)
            facts = [
                f"Token {name} is listed on CoinGecko — price=${price}, market_cap=${mcap:,.0f}",
                "Token appears to have launched successfully.",
            ]
            return 0.85, 0.8, facts, [f"{_COINGECKO_MARKETS}?ids={coin_id}"]

        except Exception as exc:  # noqa: BLE001
            logger.warning("onchain_scout.token_launch_failed", exc=str(exc))
            return 0.5, 0.1, ["CoinGecko token lookup failed."], []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch_evidence(
        self,
        market_id: str,
        market_question: str,
        resolution_date: datetime,
    ) -> Evidence:
        market_type = await self._classify_market_type(market_question)
        log = logger.bind(market_id=market_id, market_type=market_type)
        log.info("onchain_scout.market_type_classified")

        async with httpx.AsyncClient() as client:
            if market_type == "CRYPTO_PRICE":
                p_yes, conf, facts, urls = await self._handle_crypto_price(
                    market_question, client
                )
            elif market_type == "GOVERNANCE_VOTE":
                p_yes, conf, facts, urls = await self._handle_governance_vote(
                    market_question, client
                )
            elif market_type == "DEFI_EVENT":
                p_yes, conf, facts, urls = await self._handle_defi_event(market_question)
            elif market_type == "TOKEN_LAUNCH":
                p_yes, conf, facts, urls = await self._handle_token_launch(
                    market_question, client
                )
            else:
                p_yes = 0.5
                conf = 0.3
                facts = [
                    f"Market type '{market_type}' has no dedicated on-chain data source. "
                    "Neutral evidence returned."
                ]
                urls = []

        return Evidence(
            scout_type=self.scout_type,
            market_id=market_id,
            market_question=market_question,
            raw_data={"market_type": market_type},
            extracted_facts=facts,
            supports_yes_probability=p_yes,
            confidence=conf,
            source_urls=urls,
            timestamp=datetime.utcnow(),
            reliability_weight=self.reliability_score,
        )

    async def health_check(self) -> bool:
        try:
            block = await self._w3.eth.block_number
            return block > 0
        except Exception:  # noqa: BLE001
            return False
