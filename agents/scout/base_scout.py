"""
Base scout abstract class and Evidence dataclass for Oracle Sentinel.

All scouts inherit from BaseScout and return Evidence objects. The safe_fetch
wrapper ensures scouts never propagate exceptions to callers.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class Evidence:
    """
    Structured evidence returned by each scout.

    supports_yes_probability is the primary signal used by the Judge agent
    for Bayesian inference. All floats are clamped to [0.0, 1.0].
    """

    scout_type: str
    market_id: str
    market_question: str
    raw_data: dict
    extracted_facts: list[str]
    supports_yes_probability: float
    confidence: float
    source_urls: list[str]
    timestamp: datetime
    reliability_weight: float
    error: Optional[str] = None

    def __post_init__(self) -> None:
        self.supports_yes_probability = max(0.0, min(1.0, self.supports_yes_probability))
        self.confidence = max(0.0, min(1.0, self.confidence))
        self.reliability_weight = max(0.0, min(1.0, self.reliability_weight))


class BaseScout(ABC):
    """
    Abstract base for all Oracle Sentinel scout agents.

    Subclasses must implement fetch_evidence and health_check. Callers should
    use safe_fetch instead of fetch_evidence directly so failures degrade
    gracefully into error Evidence objects.
    """

    scout_type: str = "base"
    reliability_score: float = 0.7

    @abstractmethod
    async def fetch_evidence(
        self,
        market_id: str,
        market_question: str,
        resolution_date: datetime,
    ) -> Evidence:
        """
        Fetch and analyse evidence for the given market.

        Must not propagate exceptions — callers use safe_fetch which wraps this
        method, but implementations should still handle their own internal errors
        and return sensible partial results where possible.
        """
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Return True if the scout's primary data source is reachable."""
        ...

    async def safe_fetch(
        self,
        market_id: str,
        market_question: str,
        resolution_date: datetime,
    ) -> Evidence:
        """
        Wraps fetch_evidence with a broad try/except so that a scout failure
        never crashes the Judge pipeline. Returns an error Evidence with
        supports_yes_probability=0.5 (neutral) on any unhandled exception.
        """
        log = logger.bind(
            scout=self.scout_type,
            market_id=market_id,
        )
        try:
            log.debug("scout.fetch_start")
            evidence = await self.fetch_evidence(market_id, market_question, resolution_date)
            log.debug(
                "scout.fetch_complete",
                p_yes=round(evidence.supports_yes_probability, 4),
                confidence=round(evidence.confidence, 4),
                facts=len(evidence.extracted_facts),
            )
            return evidence
        except asyncio.CancelledError:
            # Never swallow cancellation.
            raise
        except Exception as exc:  # noqa: BLE001
            log.error("scout.fetch_error", exc_type=type(exc).__name__, exc=str(exc))
            return Evidence(
                scout_type=self.scout_type,
                market_id=market_id,
                market_question=market_question,
                raw_data={},
                extracted_facts=[],
                supports_yes_probability=0.5,
                confidence=0.0,
                source_urls=[],
                timestamp=datetime.utcnow(),
                reliability_weight=self.reliability_score,
                error=f"{type(exc).__name__}: {exc}",
            )
