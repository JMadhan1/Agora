"""
NewsScout — gathers evidence from NewsAPI (primary) and DuckDuckGo HTML
scraping (fallback). Results are cached in SQLite for 1 hour.

Rate limiting: NewsAPI free tier allows 100 req/day. When the daily call
counter reaches 95 the scout automatically switches to the DuckDuckGo
fallback for the rest of the day.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import httpx
import structlog
from groq import AsyncGroq

from .base_scout import BaseScout, Evidence

logger = structlog.get_logger(__name__)

_GROQ_MODEL = "llama-3.1-8b-instant"
_CACHE_TTL_SECONDS = 3600  # 1 hour
_NEWSAPI_DAILY_LIMIT = 95
_DDG_URL = "https://duckduckgo.com/html/"
_NEWSAPI_BASE = "https://newsapi.org/v2/everything"


class NewsScout(BaseScout):
    """
    Fetches news articles relevant to a prediction market question and uses
    Groq LLM to assess whether each article supports the YES resolution.
    """

    scout_type = "news"
    reliability_score = 0.75

    def __init__(
        self,
        news_api_key: str,
        groq_api_key: str,
        db_path: str = "data/oracle_sentinel.db",
    ) -> None:
        self._news_api_key = news_api_key
        self._groq_client = AsyncGroq(api_key=groq_api_key)
        self._db_path = db_path
        self._init_db()

    # ------------------------------------------------------------------
    # Database helpers
    # ------------------------------------------------------------------

    def _get_conn(self) -> sqlite3.Connection:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_cache (
                    cache_key TEXT PRIMARY KEY,
                    payload   TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS newsapi_usage (
                    usage_date TEXT PRIMARY KEY,
                    call_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            conn.commit()

    def _cache_get(self, key: str) -> Optional[dict]:
        now = datetime.utcnow().timestamp()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT payload, created_at FROM evidence_cache WHERE cache_key = ?",
                (key,),
            ).fetchone()
        if row and (now - row["created_at"]) < _CACHE_TTL_SECONDS:
            try:
                return json.loads(row["payload"])
            except json.JSONDecodeError:
                return None
        return None

    def _cache_set(self, key: str, data: dict) -> None:
        now = datetime.utcnow().timestamp()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO evidence_cache (cache_key, payload, created_at)
                VALUES (?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET payload=excluded.payload,
                                                     created_at=excluded.created_at
                """,
                (key, json.dumps(data), now),
            )
            conn.commit()

    def _daily_api_calls(self) -> int:
        today = date.today().isoformat()
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT call_count FROM newsapi_usage WHERE usage_date = ?",
                (today,),
            ).fetchone()
        return row["call_count"] if row else 0

    def _increment_daily_calls(self) -> None:
        today = date.today().isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO newsapi_usage (usage_date, call_count) VALUES (?, 1)
                ON CONFLICT(usage_date) DO UPDATE SET call_count = call_count + 1
                """,
                (today,),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # LLM helpers
    # ------------------------------------------------------------------

    async def _extract_keywords(self, question: str) -> list[str]:
        prompt = (
            "Extract 3-5 search keywords from this prediction market question for a news "
            "search. Return only the keywords as a comma-separated list, nothing else.\n"
            f"Market: {question}"
        )
        try:
            resp = await self._groq_client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60,
                temperature=0.0,
            )
            raw = resp.choices[0].message.content.strip()
            keywords = [k.strip() for k in raw.split(",") if k.strip()]
            return keywords[:5] if keywords else [question[:80]]
        except Exception as exc:  # noqa: BLE001
            logger.warning("news_scout.keyword_extraction_failed", exc=str(exc))
            # Naive fallback: take first significant words from question
            words = re.findall(r"\b[A-Za-z]{4,}\b", question)
            return list(dict.fromkeys(words))[:5] or ["news"]

    async def _analyze_article(
        self,
        title: str,
        description: str,
        question: str,
    ) -> dict:
        """
        Returns {"relevant": bool, "supports_yes": float, "key_fact": str}.
        Defaults to irrelevant on any failure.
        """
        snippet = f"{title}. {description}"[:800]
        prompt = (
            f'You are analysing a news article for relevance to a prediction market.\n'
            f"Market: {question}\n"
            f"Article snippet: {snippet}\n\n"
            'Return ONLY valid JSON with keys: "relevant" (boolean), '
            '"supports_yes" (float 0.0-1.0), "key_fact" (string ≤120 chars). '
            "No markdown, no explanation."
        )
        try:
            resp = await self._groq_client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=120,
                temperature=0.0,
            )
            raw = resp.choices[0].message.content.strip()
            # Strip markdown fences if present
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            result = json.loads(raw)
            return {
                "relevant": bool(result.get("relevant", False)),
                "supports_yes": float(result.get("supports_yes", 0.5)),
                "key_fact": str(result.get("key_fact", "")),
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("news_scout.article_analysis_failed", exc=str(exc))
            return {"relevant": False, "supports_yes": 0.5, "key_fact": ""}

    # ------------------------------------------------------------------
    # Fetch strategies
    # ------------------------------------------------------------------

    async def _fetch_newsapi(
        self, keywords: list[str], from_date: str, client: httpx.AsyncClient
    ) -> list[dict]:
        """Returns list of {title, description, url} dicts."""
        q = " ".join(keywords)
        params = {
            "q": q,
            "from": from_date,
            "sortBy": "relevance",
            "pageSize": 10,
            "apiKey": self._news_api_key,
        }
        try:
            self._increment_daily_calls()
            resp = await client.get(_NEWSAPI_BASE, params=params, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            articles = data.get("articles", [])
            return [
                {
                    "title": a.get("title", ""),
                    "description": a.get("description", "") or "",
                    "url": a.get("url", ""),
                }
                for a in articles
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning("news_scout.newsapi_failed", exc=str(exc))
            return []

    async def _fetch_duckduckgo(
        self, keywords: list[str], client: httpx.AsyncClient
    ) -> list[dict]:
        """Scrapes DuckDuckGo HTML results for Reuters/AP News articles."""
        q = quote_plus(
            " ".join(keywords) + " site:reuters.com OR site:apnews.com"
        )
        url = f"{_DDG_URL}?q={q}"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (compatible; OracleSentinel/1.0; +https://oracle-sentinel.ai)"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            resp = await client.get(url, headers=headers, timeout=20.0)
            html = resp.text
            # Extract result links: <a class="result__a" href="...">text</a>
            links = re.findall(
                r'<a[^>]+class=["\']result__a["\'][^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>',
                html,
                re.IGNORECASE | re.DOTALL,
            )
            results = []
            for href, text in links[:10]:
                clean_text = re.sub(r"<[^>]+>", "", text).strip()
                results.append({"title": clean_text, "description": "", "url": href})
            return results
        except Exception as exc:  # noqa: BLE001
            logger.warning("news_scout.duckduckgo_failed", exc=str(exc))
            return []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch_evidence(
        self,
        market_id: str,
        market_question: str,
        resolution_date: datetime,
    ) -> Evidence:
        cache_key = f"{market_id}_news_{date.today()}"
        cached = self._cache_get(cache_key)
        if cached:
            logger.debug("news_scout.cache_hit", market_id=market_id)
            return Evidence(**{**cached, "timestamp": datetime.fromisoformat(cached["timestamp"])})

        keywords = await self._extract_keywords(market_question)
        from_date = (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%d")

        use_fallback = (
            not self._news_api_key
            or self._daily_api_calls() >= _NEWSAPI_DAILY_LIMIT
        )

        async with httpx.AsyncClient() as client:
            if use_fallback:
                logger.info("news_scout.using_fallback", market_id=market_id)
                articles = await self._fetch_duckduckgo(keywords, client)
            else:
                articles = await self._fetch_newsapi(keywords, from_date, client)
                if not articles:
                    logger.info("news_scout.newsapi_empty_fallback", market_id=market_id)
                    articles = await self._fetch_duckduckgo(keywords, client)

        source_urls: list[str] = []
        extracted_facts: list[str] = []
        weighted_sum = 0.0
        weight_total = 0.0

        for article in articles:
            analysis = await self._analyze_article(
                article["title"], article["description"], market_question
            )
            if not analysis["relevant"]:
                continue
            p = analysis["supports_yes"]
            weighted_sum += p
            weight_total += 1.0
            if article["url"]:
                source_urls.append(article["url"])
            if analysis["key_fact"]:
                extracted_facts.append(analysis["key_fact"])

        if weight_total > 0:
            supports_yes = weighted_sum / weight_total
            confidence = min(0.9, 0.4 + 0.1 * weight_total)
        else:
            supports_yes = 0.5
            confidence = 0.1

        if not extracted_facts:
            extracted_facts.append(
                f"No strongly relevant articles found for keywords: {', '.join(keywords)}"
            )

        raw_data = {
            "keywords": keywords,
            "articles_fetched": len(articles),
            "articles_relevant": int(weight_total),
            "used_fallback": use_fallback,
        }

        evidence = Evidence(
            scout_type=self.scout_type,
            market_id=market_id,
            market_question=market_question,
            raw_data=raw_data,
            extracted_facts=extracted_facts,
            supports_yes_probability=supports_yes,
            confidence=confidence,
            source_urls=source_urls[:10],
            timestamp=datetime.utcnow(),
            reliability_weight=self.reliability_score,
        )

        # Cache serialisable snapshot
        cache_payload = {
            **evidence.__dict__,
            "timestamp": evidence.timestamp.isoformat(),
        }
        self._cache_set(cache_key, cache_payload)

        return evidence

    async def health_check(self) -> bool:
        if not self._news_api_key:
            return False
        params = {"q": "test", "pageSize": 1, "apiKey": self._news_api_key}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(_NEWSAPI_BASE, params=params, timeout=8.0)
                return resp.status_code in (200, 401)  # 401 = bad key but service up
        except Exception:  # noqa: BLE001
            return False
