"""
Calibration tracker for Oracle Sentinel Judge agent.

Records post-resolution outcomes against prior predictions, computes Brier
scores, and exposes aggregate calibration statistics used to grade the
system's long-run forecasting accuracy.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from sqlalchemy import select

from storage.models import Attestation, CalibrationRecord

log = structlog.get_logger(__name__)


def record_market_outcome(
    session,
    market_id: str,
    actual_resolution: str,
) -> None:
    """
    Record the resolved outcome for a market and compute the calibration metrics.

    Looks up the most recent Attestation for *market_id*, then derives:
    - ``correct``: whether our recommendation matched the actual resolution.
    - ``brier_score``: ``(p - outcome)^2`` where outcome is 1 for YES, 0 for NO.

    Saves a new CalibrationRecord and logs the result.

    Args:
        session: SQLAlchemy session (sync).
        market_id: Polymarket market / condition ID.
        actual_resolution: ``"YES"`` or ``"NO"``.
    """
    actual_resolution = actual_resolution.upper().strip()
    outcome_value = 1.0 if actual_resolution == "YES" else 0.0

    stmt = (
        select(Attestation)
        .where(Attestation.market_id == market_id)
        .order_by(Attestation.timestamp.desc())
        .limit(1)
    )
    attestation: Attestation | None = session.scalars(stmt).first()

    if attestation is None:
        log.warning(
            "calibration_tracker.no_attestation",
            market_id=market_id,
            actual_resolution=actual_resolution,
        )
        return

    probability_estimate = attestation.probability_estimate
    recommendation = attestation.recommendation.upper().strip()
    confidence = attestation.confidence / 100.0  # stored as 0-100 int

    correct = recommendation == actual_resolution

    # Brier score: (forecast_probability - actual_outcome)^2
    brier_score = (probability_estimate - outcome_value) ** 2

    record = CalibrationRecord(
        market_id=market_id,
        our_prediction=recommendation,
        our_confidence=confidence,
        actual_resolution=actual_resolution,
        correct=correct,
        brier_score=brier_score,
        timestamp=datetime.utcnow(),
    )
    session.add(record)
    session.commit()

    log.info(
        "calibration_tracker.outcome_recorded",
        market_id=market_id,
        actual=actual_resolution,
        prediction=recommendation,
        correct=correct,
        brier_score=round(brier_score, 6),
        probability_estimate=round(probability_estimate, 4),
    )


def get_calibration_stats(session) -> dict:
    """
    Compute aggregate calibration statistics across all resolved markets.

    Returns a dict with:
    - ``accuracy_overall``: fraction of correct calls across all time.
    - ``accuracy_7d``: fraction of correct calls in the last 7 days.
    - ``total_markets``: total number of resolved markets evaluated.
    - ``correct_calls``: absolute count of correct predictions.
    - ``avg_brier_score``: mean Brier score (lower is better; 0 = perfect).
    - ``calibration_grade``: letter grade derived from avg_brier_score.
    """
    all_records: list[CalibrationRecord] = list(
        session.scalars(select(CalibrationRecord)).all()
    )

    total_markets = len(all_records)
    correct_calls = sum(1 for r in all_records if r.correct)
    accuracy_overall = correct_calls / total_markets if total_markets else 0.0

    cutoff_7d = datetime.utcnow() - timedelta(days=7)
    recent = [r for r in all_records if r.timestamp >= cutoff_7d]
    correct_7d = sum(1 for r in recent if r.correct)
    accuracy_7d = correct_7d / len(recent) if recent else 0.0

    avg_brier = (
        sum(r.brier_score for r in all_records) / total_markets
        if total_markets
        else 0.0
    )

    calibration_grade = _brier_to_grade(avg_brier)

    stats = {
        "accuracy_overall": round(accuracy_overall, 4),
        "accuracy_7d": round(accuracy_7d, 4),
        "total_markets": total_markets,
        "correct_calls": correct_calls,
        "avg_brier_score": round(avg_brier, 6),
        "calibration_grade": calibration_grade,
    }

    log.info("calibration_tracker.stats", **stats)
    return stats


def _brier_to_grade(avg_brier: float) -> str:
    """Convert an average Brier score to a human-readable grade."""
    if avg_brier <= 0.05:
        return "A+"
    if avg_brier <= 0.10:
        return "A"
    if avg_brier <= 0.15:
        return "B"
    if avg_brier <= 0.20:
        return "C"
    if avg_brier <= 0.25:
        return "D"
    return "F"
