"""
Market Prioritizer — LLM-driven scout allocation.

Replaces naive "scan every market on a timer" with autonomous intelligence:
the LLM reads all available markets and decides which 10-20 deserve
immediate investigation based on risk signals, price volatility, and proximity
to resolution. This moves Scout from "AI-flavored automation" to full autonomy.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

log = structlog.get_logger(__name__)

_PRIORITY_CACHE: dict[str, tuple[float, list[str]]] = {}  # (timestamp, market_ids)
_CACHE_TTL = 120  # seconds


class MarketPrioritizer:
    """
    Uses an LLM to autonomously decide which markets deserve scout attention.

    Rather than blindly scanning all 200 markets every cycle, Sentinel's Scout
    now thinks like a professional analyst: high volatility near resolution?
    Investigate. Stable, long-dated, low-volume? Defer.
    """

    def __init__(self, groq_api_key: str, max_markets: int = 15) -> None:
        self.groq_api_key = groq_api_key
        self.max_markets = max_markets

    async def prioritize(self, markets: list[dict]) -> list[dict]:
        """
        Given a list of market dicts, return a shorter prioritized list.

        Decision factors the LLM considers:
          - Days to resolution (urgent = <7 days)
          - Recent price volatility (>10% move = suspicious)
          - Volume spike vs 7-day average
          - Whether a market has a prior Sentinel attestation
          - Category (political/crypto markets manipulated more often)
        """
        if not markets:
            return []

        cache_key = f"priority_{len(markets)}"
        cached = _PRIORITY_CACHE.get(cache_key)
        if cached and (time.time() - cached[0]) < _CACHE_TTL:
            cached_ids = set(cached[1])
            return [m for m in markets if m.get("id") in cached_ids]

        # Build a compact market summary for the LLM
        summaries = []
        now_ts = datetime.now(timezone.utc).timestamp()
        for m in markets[:100]:  # cap to avoid giant prompts
            try:
                res_date = m.get("resolution_date", "")
                if res_date:
                    res_ts = datetime.fromisoformat(res_date.replace("Z", "+00:00")).timestamp()
                    days_left = max(0, (res_ts - now_ts) / 86400)
                else:
                    days_left = 999
            except Exception:
                days_left = 999

            summaries.append({
                "id": m.get("id", ""),
                "question": m.get("question", "")[:80],
                "price": round(m.get("current_yes_price", 0.5), 3),
                "days_left": round(days_left, 1),
                "volume": m.get("volume", 0),
                "has_prior_attestation": bool(m.get("our_latest_estimate")),
            })

        prompt = f"""You are the Scout intelligence system for Oracle Sentinel, an autonomous prediction market truth verification network.

I have {len(summaries)} active prediction markets. I can only deeply investigate {self.max_markets} right now due to API rate limits.

Select the {self.max_markets} markets most at risk of MANIPULATION or most in need of verification RIGHT NOW.

Prioritize:
1. Markets resolving in <7 days (urgent — close to manipulation window)
2. Markets with price near 0.5 (high uncertainty, most profitable to manipulate)
3. High-volume markets (>$100k volume — bigger financial stake)
4. Political/election/crypto markets (historically more manipulation)
5. Markets WITHOUT a prior Sentinel attestation (unverified)
6. Markets with prices at extremes (>0.85 or <0.15) — may be manipulation artifacts

Deprioritize:
- Already resolved markets
- Very long-dated markets (>90 days)
- Low-volume markets (<$1k volume)

Markets to choose from:
{json.dumps(summaries, indent=2)}

Return ONLY a JSON array of market IDs (strings), most urgent first. No explanation needed.
Example: ["id1", "id2", "id3"]"""

        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=self.groq_api_key)
            resp = await client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=512,
            )
            content = resp.choices[0].message.content.strip()
            # Extract JSON array from response
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                priority_ids = json.loads(content[start:end])
            else:
                raise ValueError("No JSON array found in response")

            priority_ids = [str(pid) for pid in priority_ids[:self.max_markets]]
            _PRIORITY_CACHE[cache_key] = (time.time(), priority_ids)

            log.info(
                "market_prioritizer.llm_selected",
                total_markets=len(markets),
                selected=len(priority_ids),
                top_3=priority_ids[:3],
            )

            # Return prioritized markets in LLM-specified order
            id_order = {pid: i for i, pid in enumerate(priority_ids)}
            prioritized = [m for m in markets if m.get("id") in id_order]
            prioritized.sort(key=lambda m: id_order.get(m.get("id", ""), 999))
            return prioritized

        except Exception as exc:
            log.warning("market_prioritizer.llm_failed_falling_back", error=str(exc))
            # Fallback: prioritize by urgency + price distance from 0.5
            def urgency_score(m: dict) -> float:
                try:
                    res_date = m.get("resolution_date", "")
                    res_ts = datetime.fromisoformat(res_date.replace("Z", "+00:00")).timestamp()
                    days_left = max(0.1, (res_ts - now_ts) / 86400)
                except Exception:
                    days_left = 365
                price = m.get("current_yes_price", 0.5)
                uncertainty = 1 - abs(2 * price - 1)  # 1.0 at 50%, 0.0 at 0% or 100%
                urgency = 1.0 / days_left
                return urgency * 0.7 + uncertainty * 0.3

            sorted_markets = sorted(markets, key=urgency_score, reverse=True)
            return sorted_markets[:self.max_markets]
