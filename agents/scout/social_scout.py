"""
SocialScout — gathers sentiment evidence from Reddit communities that
discuss Polymarket and prediction markets.

Features:
  - Searches r/Polymarket and r/PredictionMarkets for relevant posts
  - Uses Groq LLM for per-post sentiment classification
  - Applies time decay weighting (fresh posts count more)
  - Detects coordinated manipulation via post-similarity clustering
  - Computes weighted-average supports_yes_probability
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Optional

import httpx
import structlog
from groq import AsyncGroq

from .base_scout import BaseScout, Evidence

logger = structlog.get_logger(__name__)

_GROQ_MODEL = "llama-3.1-8b-instant"
_REDDIT_BASE = "https://www.reddit.com"
_USER_AGENT = "OracleSentinel/1.0 (prediction market research bot; contact: oracle@sentinel.ai)"

# Time-decay weights
_WEIGHT_UNDER_24H = 1.0
_WEIGHT_UNDER_7D = 0.5
_WEIGHT_OLDER = 0.2

# Sentiment → float mapping
_SENTIMENT_SCORES: dict[str, float] = {
    "STRONGLY_YES": 0.9,
    "LEANING_YES": 0.7,
    "NEUTRAL": 0.5,
    "LEANING_NO": 0.3,
    "STRONGLY_NO": 0.1,
}

# Manipulation detection parameters
_MANIPULATION_POST_THRESHOLD = 5        # minimum posts to check
_MANIPULATION_SIMILARITY_THRESHOLD = 0.80  # fraction of shared word-set


class SocialScout(BaseScout):
    """
    Fetches Reddit posts from prediction market communities and uses Groq to
    classify sentiment toward YES resolution. Applies time-decay weighting
    and detects coordinated posting campaigns.
    """

    scout_type = "social"
    reliability_score = 0.55

    def __init__(self, groq_api_key: str) -> None:
        self._groq_client = AsyncGroq(api_key=groq_api_key)

    # ------------------------------------------------------------------
    # Reddit fetching
    # ------------------------------------------------------------------

    async def _search_subreddit(
        self,
        subreddit: str,
        keywords: str,
        client: httpx.AsyncClient,
    ) -> list[dict]:
        """
        Search a subreddit for posts matching keywords via Reddit JSON API.
        Returns list of post dicts with title, selftext, url, created_utc.
        """
        url = f"{_REDDIT_BASE}/r/{subreddit}/search.json"
        params = {"q": keywords, "sort": "new", "limit": 25, "t": "week", "restrict_sr": 1}
        headers = {"User-Agent": _USER_AGENT}
        try:
            resp = await client.get(url, params=params, headers=headers, timeout=15.0)
            resp.raise_for_status()
            data = resp.json()
            posts = data.get("data", {}).get("children", [])
            return [
                {
                    "title": p["data"].get("title", ""),
                    "selftext": p["data"].get("selftext", ""),
                    "url": p["data"].get("url", ""),
                    "permalink": f"https://reddit.com{p['data'].get('permalink', '')}",
                    "created_utc": p["data"].get("created_utc", 0),
                    "score": p["data"].get("score", 0),
                    "num_comments": p["data"].get("num_comments", 0),
                }
                for p in posts
                if "data" in p
            ]
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "social_scout.reddit_search_failed",
                subreddit=subreddit,
                exc=str(exc),
            )
            return []

    async def _search_reddit(self, keywords: str) -> list[dict]:
        """
        Searches r/Polymarket and r/PredictionMarkets, deduplicating by URL.
        """
        async with httpx.AsyncClient() as client:
            polymarket_posts = await self._search_subreddit("Polymarket", keywords, client)
            predmarket_posts = await self._search_subreddit("PredictionMarkets", keywords, client)

        seen_urls: set[str] = set()
        combined: list[dict] = []
        for post in polymarket_posts + predmarket_posts:
            u = post.get("url", "")
            if u not in seen_urls:
                seen_urls.add(u)
                combined.append(post)

        return combined

    # ------------------------------------------------------------------
    # LLM sentiment classification
    # ------------------------------------------------------------------

    async def _classify_sentiment(
        self, post_text: str, question: str
    ) -> dict:
        """
        Returns {"sentiment": str, "confidence": float}.
        Defaults to NEUTRAL/0.0 on failure.
        """
        truncated = post_text[:600]
        prompt = (
            f"Classify the sentiment toward YES resolution in this post about:\n"
            f"Market: {question}\n\n"
            f"Post:\n{truncated}\n\n"
            "Return ONLY valid JSON:\n"
            '{"sentiment": "STRONGLY_YES"|"LEANING_YES"|"NEUTRAL"|"LEANING_NO"|"STRONGLY_NO", '
            '"confidence": <float 0.0-1.0>}\n'
            "No markdown, no explanation."
        )
        try:
            resp = await self._groq_client.chat.completions.create(
                model=_GROQ_MODEL,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=60,
                temperature=0.0,
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r"^```[a-z]*\n?", "", raw)
            raw = re.sub(r"\n?```$", "", raw)
            result = json.loads(raw)
            sentiment = str(result.get("sentiment", "NEUTRAL")).upper()
            if sentiment not in _SENTIMENT_SCORES:
                sentiment = "NEUTRAL"
            return {
                "sentiment": sentiment,
                "confidence": float(result.get("confidence", 0.5)),
            }
        except Exception as exc:  # noqa: BLE001
            logger.debug("social_scout.sentiment_failed", exc=str(exc))
            return {"sentiment": "NEUTRAL", "confidence": 0.0}

    # ------------------------------------------------------------------
    # Time-decay weight
    # ------------------------------------------------------------------

    @staticmethod
    def _time_weight(created_utc: float) -> float:
        now = datetime.now(tz=timezone.utc).timestamp()
        age_hours = (now - created_utc) / 3600.0
        if age_hours < 24:
            return _WEIGHT_UNDER_24H
        if age_hours < 168:  # 7 days
            return _WEIGHT_UNDER_7D
        return _WEIGHT_OLDER

    # ------------------------------------------------------------------
    # Manipulation detection
    # ------------------------------------------------------------------

    @staticmethod
    def _word_set(text: str) -> frozenset[str]:
        return frozenset(re.findall(r"\b[a-z]{3,}\b", text.lower()))

    def _detect_manipulation(self, posts: list[dict]) -> bool:
        """
        Returns True if more than 5 posts share >80% word overlap with each
        other (indicative of copy-pasted coordinated campaign).
        """
        if len(posts) < _MANIPULATION_POST_THRESHOLD:
            return False
        word_sets = [
            self._word_set(p.get("title", "") + " " + p.get("selftext", ""))
            for p in posts
        ]
        cluster_count = 0
        for i in range(len(word_sets)):
            for j in range(i + 1, len(word_sets)):
                a, b = word_sets[i], word_sets[j]
                if not a or not b:
                    continue
                intersection = len(a & b)
                union = len(a | b)
                if union > 0 and intersection / union >= _MANIPULATION_SIMILARITY_THRESHOLD:
                    cluster_count += 1
                    if cluster_count > 5:
                        return True
        return False

    # ------------------------------------------------------------------
    # Keyword extraction (lightweight, no LLM call needed)
    # ------------------------------------------------------------------

    @staticmethod
    def _build_keywords(question: str) -> str:
        """Extract meaningful words from market question for Reddit search."""
        # Remove common stop words and return top terms
        stop = {
            "will", "the", "a", "an", "by", "in", "on", "at", "to", "for",
            "of", "and", "or", "is", "be", "this", "that", "with", "from",
            "its", "are", "was", "were", "been", "have", "has", "had",
            "do", "does", "did", "get", "got", "year", "before", "after",
            "end", "until", "than", "more", "less", "over", "under", "which",
        }
        words = re.findall(r"\b[A-Za-z]{4,}\b", question)
        unique = list(dict.fromkeys(w for w in words if w.lower() not in stop))
        return " ".join(unique[:8])

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def fetch_evidence(
        self,
        market_id: str,
        market_question: str,
        resolution_date: datetime,
    ) -> Evidence:
        keywords = self._build_keywords(market_question)
        posts = await self._search_reddit(keywords)

        if not posts:
            return Evidence(
                scout_type=self.scout_type,
                market_id=market_id,
                market_question=market_question,
                raw_data={"posts_found": 0, "keywords": keywords},
                extracted_facts=["No relevant Reddit posts found for this market question."],
                supports_yes_probability=0.5,
                confidence=0.1,
                source_urls=[],
                timestamp=datetime.utcnow(),
                reliability_weight=self.reliability_score,
            )

        coordinated_manipulation = self._detect_manipulation(posts)
        if coordinated_manipulation:
            logger.warning(
                "social_scout.manipulation_detected",
                market_id=market_id,
                posts=len(posts),
            )

        weighted_sum = 0.0
        weight_total = 0.0
        extracted_facts: list[str] = []
        source_urls: list[str] = []
        sentiment_counts: dict[str, int] = {k: 0 for k in _SENTIMENT_SCORES}

        for post in posts:
            post_text = post["title"] + ". " + post.get("selftext", "")
            classification = await self._classify_sentiment(post_text, market_question)
            sentiment = classification["sentiment"]
            sentiment_score = _SENTIMENT_SCORES[sentiment]
            llm_confidence = classification["confidence"]

            time_w = self._time_weight(post.get("created_utc", 0))
            # Downweight low LLM confidence
            effective_weight = time_w * max(llm_confidence, 0.1)

            if coordinated_manipulation:
                effective_weight *= 0.1  # severely downweight suspect posts

            weighted_sum += sentiment_score * effective_weight
            weight_total += effective_weight
            sentiment_counts[sentiment] = sentiment_counts.get(sentiment, 0) + 1

            permalink = post.get("permalink", "")
            if permalink:
                source_urls.append(permalink)

            # Keep interesting facts (non-neutral posts only)
            if sentiment != "NEUTRAL" and llm_confidence >= 0.6:
                title = post["title"][:100]
                extracted_facts.append(
                    f"Reddit [{sentiment}] (score={post.get('score', 0)}): {title}"
                )

        if weight_total > 0:
            supports_yes = weighted_sum / weight_total
            n = len(posts)
            confidence = min(0.85, 0.3 + 0.05 * n)
            if coordinated_manipulation:
                confidence = 0.1
        else:
            supports_yes = 0.5
            confidence = 0.1

        if not extracted_facts:
            extracted_facts = [
                f"Analysed {len(posts)} Reddit post(s). "
                f"Sentiment distribution: {json.dumps(sentiment_counts)}"
            ]
        else:
            # Prepend summary
            extracted_facts.insert(
                0,
                f"Analysed {len(posts)} Reddit post(s). "
                f"Sentiment: {json.dumps(sentiment_counts)}",
            )

        if coordinated_manipulation:
            extracted_facts.append(
                "WARNING: Coordinated manipulation detected — >5 posts with >80% word overlap. "
                "Social evidence confidence reduced to 0.1."
            )

        return Evidence(
            scout_type=self.scout_type,
            market_id=market_id,
            market_question=market_question,
            raw_data={
                "posts_found": len(posts),
                "keywords": keywords,
                "sentiment_counts": sentiment_counts,
                "coordinated_manipulation_detected": coordinated_manipulation,
            },
            extracted_facts=extracted_facts[:15],
            supports_yes_probability=supports_yes,
            confidence=confidence,
            source_urls=source_urls[:10],
            timestamp=datetime.utcnow(),
            reliability_weight=self.reliability_score,
        )

    async def health_check(self) -> bool:
        headers = {"User-Agent": _USER_AGENT}
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_REDDIT_BASE}/r/Polymarket/new.json",
                    headers=headers,
                    params={"limit": 1},
                    timeout=10.0,
                )
                return resp.status_code == 200
        except Exception:  # noqa: BLE001
            return False
