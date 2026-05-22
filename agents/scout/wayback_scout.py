"""
WaybackScout — uses the Wayback Machine CDX API and snapshot fetcher to
find historical snapshots of official resolution URLs and assess whether
archived page content confirms YES resolution of the market.

Rate limit: Wayback CDX allows ~5 requests/minute, so we sleep 12 seconds
between CDX API calls.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta
from typing import Optional

import httpx
import structlog
from groq import AsyncGroq

from .base_scout import BaseScout, Evidence

logger = structlog.get_logger(__name__)

_GROQ_MODEL = "llama-3.1-8b-instant"
_CDX_API = "http://web.archive.org/cdx/search/cdx"
_WAYBACK_BASE = "https://web.archive.org/web"
_SNAPSHOT_TEXT_LIMIT = 3000
_CDX_SLEEP_SECONDS = 12  # 5 req/min → 12 s between calls


class WaybackScout(BaseScout):
    """
    Looks up the Wayback Machine for snapshots of official resolution sources
    and uses Groq LLM to determine whether archived content supports the YES
    resolution of the prediction market.
    """

    scout_type = "wayback"
    reliability_score = 0.85

    def __init__(self, groq_api_key: str) -> None:
        self._groq_client = AsyncGroq(api_key=groq_api_key)

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    async def _extract_resolution_url(self, question: str) -> Optional[str]:
        """
        Ask Groq for the most likely official URL that would confirm or deny
        resolution of the market question. Returns None if no specific URL
        can be determined.
        """
        prompt = (
            "What official URL would confirm the resolution of this prediction market?\n"
            f"Market: {question}\n\n"
            "If you can determine a specific URL (government site, official announcement, "
            "company press release, regulatory body, etc.) return just the URL with no "
            "additional text. If no specific URL can be determined, return 'NONE'."
        )
        try:
            resp = await self._groq_client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.0,
            )
            raw = resp.choices[0].message.content.strip()
            if raw.upper() == "NONE" or not raw:
                return None
            # Basic URL validation
            url = raw.split()[0]  # take first token in case of trailing text
            if re.match(r"https?://", url, re.IGNORECASE):
                return url
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("wayback_scout.url_extraction_failed", exc=str(exc))
            return None

    async def _analyze_snapshot(self, text: str, question: str) -> dict:
        """
        Returns {"confirms_yes": float 0-1, "key_finding": str}.
        Defaults to neutral on failure.
        """
        prompt = (
            f"Does this archived page confirm or deny the following prediction market "
            f"resolution?\n"
            f"Market: {question}\n\n"
            f"Page text (truncated):\n{text[:2000]}\n\n"
            'Return ONLY valid JSON: {"confirms_yes": <float 0.0-1.0>, "key_finding": '
            '"<string max 150 chars>"}. No markdown, no explanation.'
        )
        try:
            resp = await self._groq_client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.0,
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            result = json.loads(raw)
            return {
                "confirms_yes": float(result.get("confirms_yes", 0.5)),
                "key_finding": str(result.get("key_finding", ""))[:150],
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("wayback_scout.snapshot_analysis_failed", exc=str(exc))
            return {"confirms_yes": 0.5, "key_finding": "Analysis failed."}

    # ------------------------------------------------------------------
    # Wayback Machine API helpers
    # ------------------------------------------------------------------

    async def _fetch_cdx_entries(
        self,
        url: str,
        from_date: str,
        to_date: str,
        client: httpx.AsyncClient,
    ) -> list[dict]:
        """
        Queries CDX for up to 3 snapshots of `url` within the date range.
        Returns list of {"timestamp": str, "statuscode": str, "digest": str}.
        """
        params = {
            "url": url,
            "output": "json",
            "limit": 3,
            "from": from_date,
            "to": to_date,
            "fl": "timestamp,statuscode,digest",
        }
        try:
            resp = await client.get(_CDX_API, params=params, timeout=20.0)
            resp.raise_for_status()
            rows = resp.json()
            # First row is the header ["timestamp","statuscode","digest"]
            if not rows or len(rows) < 2:
                return []
            headers = rows[0]
            return [dict(zip(headers, row)) for row in rows[1:]]
        except Exception as exc:  # noqa: BLE001
            logger.warning("wayback_scout.cdx_failed", url=url, exc=str(exc))
            return []

    async def _fetch_snapshot_text(
        self,
        timestamp: str,
        url: str,
        client: httpx.AsyncClient,
    ) -> str:
        """
        Fetches the Wayback Machine snapshot and returns stripped plain text,
        truncated to _SNAPSHOT_TEXT_LIMIT characters.
        """
        snapshot_url = f"{_WAYBACK_BASE}/{timestamp}/{url}"
        try:
            resp = await client.get(
                snapshot_url,
                timeout=25.0,
                follow_redirects=True,
                headers={"User-Agent": "OracleSentinel/1.0"},
            )
            html = resp.text
            # Strip HTML tags
            text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)
            text = re.sub(r"<[^>]+>", " ", text)
            # Collapse whitespace
            text = re.sub(r"\s{2,}", " ", text).strip()
            return text[:_SNAPSHOT_TEXT_LIMIT]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "wayback_scout.snapshot_fetch_failed",
                timestamp=timestamp,
                url=url,
                exc=str(exc),
            )
            return ""

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch_evidence(
        self,
        market_id: str,
        market_question: str,
        resolution_date: datetime,
    ) -> Evidence:
        resolution_url = await self._extract_resolution_url(market_question)
        if not resolution_url:
            return Evidence(
                scout_type=self.scout_type,
                market_id=market_id,
                market_question=market_question,
                raw_data={"resolution_url": None},
                extracted_facts=["No specific resolution URL could be determined for this market."],
                supports_yes_probability=0.5,
                confidence=0.1,
                source_urls=[],
                timestamp=datetime.utcnow(),
                reliability_weight=self.reliability_score,
            )

        # Search window: 30 days before resolution to 7 days after
        from_dt = resolution_date - timedelta(days=30)
        to_dt = resolution_date + timedelta(days=7)
        from_date = from_dt.strftime("%Y%m%d")
        to_date = to_dt.strftime("%Y%m%d")

        log = logger.bind(market_id=market_id, resolution_url=resolution_url)
        log.info("wayback_scout.searching")

        async with httpx.AsyncClient() as client:
            await asyncio.sleep(_CDX_SLEEP_SECONDS)
            snapshots = await self._fetch_cdx_entries(
                resolution_url, from_date, to_date, client
            )

            if not snapshots:
                return Evidence(
                    scout_type=self.scout_type,
                    market_id=market_id,
                    market_question=market_question,
                    raw_data={
                        "resolution_url": resolution_url,
                        "snapshots_found": 0,
                    },
                    extracted_facts=[
                        f"No Wayback Machine snapshots found for {resolution_url} "
                        f"in the window {from_date}–{to_date}."
                    ],
                    supports_yes_probability=0.5,
                    confidence=0.15,
                    source_urls=[resolution_url],
                    timestamp=datetime.utcnow(),
                    reliability_weight=self.reliability_score,
                )

            analyses: list[dict] = []
            snapshot_urls: list[str] = []

            for i, snap in enumerate(snapshots):
                ts = snap.get("timestamp", "")
                status = snap.get("statuscode", "")
                if status not in ("200", "301", "302", ""):
                    log.debug("wayback_scout.skipping_snapshot", status=status, ts=ts)
                    continue

                if i > 0:
                    # Respect rate limit between CDX/snapshot calls
                    await asyncio.sleep(_CDX_SLEEP_SECONDS)

                text = await self._fetch_snapshot_text(ts, resolution_url, client)
                if not text:
                    continue

                analysis = await self._analyze_snapshot(text, market_question)
                analyses.append(analysis)
                snap_url = f"{_WAYBACK_BASE}/{ts}/{resolution_url}"
                snapshot_urls.append(snap_url)
                log.debug(
                    "wayback_scout.snapshot_analysed",
                    ts=ts,
                    confirms_yes=analysis["confirms_yes"],
                )

        if not analyses:
            return Evidence(
                scout_type=self.scout_type,
                market_id=market_id,
                market_question=market_question,
                raw_data={
                    "resolution_url": resolution_url,
                    "snapshots_found": len(snapshots),
                    "snapshots_analysed": 0,
                },
                extracted_facts=[
                    f"Found {len(snapshots)} Wayback snapshot(s) but none could be "
                    "successfully fetched or analysed."
                ],
                supports_yes_probability=0.5,
                confidence=0.15,
                source_urls=snapshot_urls or [resolution_url],
                timestamp=datetime.utcnow(),
                reliability_weight=self.reliability_score,
            )

        # Weighted average: more recent snapshots carry more weight
        total_weight = 0.0
        weighted_sum = 0.0
        for idx, a in enumerate(analyses):
            weight = 1.0 / (idx + 1)  # 1, 0.5, 0.33 …
            weighted_sum += a["confirms_yes"] * weight
            total_weight += weight

        supports_yes = weighted_sum / total_weight if total_weight > 0 else 0.5
        confidence = min(0.9, 0.5 + 0.15 * len(analyses))

        extracted_facts = [a["key_finding"] for a in analyses if a["key_finding"]]
        if not extracted_facts:
            extracted_facts = [
                f"Analysed {len(analyses)} archived snapshot(s) of {resolution_url}."
            ]

        return Evidence(
            scout_type=self.scout_type,
            market_id=market_id,
            market_question=market_question,
            raw_data={
                "resolution_url": resolution_url,
                "snapshots_found": len(snapshots),
                "snapshots_analysed": len(analyses),
            },
            extracted_facts=extracted_facts,
            supports_yes_probability=supports_yes,
            confidence=confidence,
            source_urls=snapshot_urls[:5],
            timestamp=datetime.utcnow(),
            reliability_weight=self.reliability_score,
        )

    async def health_check(self) -> bool:
        params = {
            "url": "example.com",
            "output": "json",
            "limit": 1,
            "fl": "timestamp",
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(_CDX_API, params=params, timeout=10.0)
                return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False
