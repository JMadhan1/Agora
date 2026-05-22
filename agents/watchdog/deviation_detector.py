"""Detects statistical deviation between Sentinel estimates and market/UMA resolutions."""
from __future__ import annotations
from dataclasses import dataclass
import structlog

log = structlog.get_logger()


@dataclass
class DeviationResult:
    deviation: float
    manipulation_suspected: bool
    our_estimate: float
    proposed_resolution: str
    proposed_value: float
    our_confidence: float
    threshold: float
    risk_score: float


class DeviationDetector:
    """Compares Sentinel probability estimates against proposed UMA resolutions."""

    def __init__(self, threshold: float = 0.40, min_confidence: float = 0.65):
        self.threshold = threshold
        self.min_confidence = min_confidence

    def check_deviation(
        self,
        our_estimate: float,
        proposed_resolution: str,
        market_price: float,
        our_confidence: float,
    ) -> DeviationResult:
        """
        Compare Sentinel estimate against a proposed UMA resolution.
        Returns manipulation_suspected=True if deviation >= threshold AND confidence >= min.
        """
        proposed_value = 1.0 if proposed_resolution.upper() == "YES" else 0.0
        deviation = abs(our_estimate - proposed_value)

        # Risk score: weighted by confidence and deviation magnitude
        risk_score = deviation * our_confidence

        manipulation_suspected = (
            deviation >= self.threshold
            and our_confidence >= self.min_confidence
        )

        result = DeviationResult(
            deviation=deviation,
            manipulation_suspected=manipulation_suspected,
            our_estimate=our_estimate,
            proposed_resolution=proposed_resolution,
            proposed_value=proposed_value,
            our_confidence=our_confidence,
            threshold=self.threshold,
            risk_score=risk_score,
        )

        if manipulation_suspected:
            log.warning(
                "manipulation_suspected",
                deviation=f"{deviation:.2%}",
                our_estimate=our_estimate,
                proposed=proposed_resolution,
                confidence=our_confidence,
                risk_score=risk_score,
            )

        return result

    def analyze_market_signals(self, market_data_facts: list[str]) -> dict:
        """
        Parses MarketDataScout extracted_facts for manipulation signals.
        Returns { manipulation_risk_score, large_order_detected, price_spike, imbalance }.
        """
        large_order = any("large order" in f.lower() for f in market_data_facts)
        price_spike = any("spike" in f.lower() or "30%" in f for f in market_data_facts)
        imbalance = any("imbalance" in f.lower() for f in market_data_facts)
        manipulation_words = any(
            w in " ".join(market_data_facts).lower()
            for w in ["manipulation", "suspicious", "unusual", "whale"]
        )

        score = sum([
            0.4 if large_order else 0,
            0.3 if price_spike else 0,
            0.2 if imbalance else 0,
            0.1 if manipulation_words else 0,
        ])

        return {
            "manipulation_risk_score": round(score, 2),
            "large_order_detected": large_order,
            "price_spike_detected": price_spike,
            "orderbook_imbalance": imbalance,
        }
