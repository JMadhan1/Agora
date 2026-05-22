"""Calibration router — accuracy and Brier score tracking."""
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from storage.database import CalibrationRecord, get_db_fastapi as get_db

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class CalibrationRecordOut(BaseModel):
    id: int
    market_id: str
    our_estimate: float
    actual_outcome: float
    brier_score: Optional[float]
    correct: Optional[bool]
    recorded_at: str

    model_config = {"from_attributes": True}


class CalibrationStatsOut(BaseModel):
    accuracy_overall: float
    accuracy_7d: float
    total_markets: int
    correct_calls: int
    avg_brier_score: float
    calibration_grade: str


class BrierScoreOut(BaseModel):
    avg_brier: float
    rolling_7d_brier: float


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _compute_grade(accuracy: float) -> str:
    if accuracy >= 0.85:
        return "A"
    if accuracy >= 0.75:
        return "B"
    if accuracy >= 0.65:
        return "C"
    return "D"


def _get_calibration_stats(db: Session) -> CalibrationStatsOut:
    total = db.query(func.count(CalibrationRecord.id)).scalar() or 0
    correct = (
        db.query(func.count(CalibrationRecord.id))
        .filter(CalibrationRecord.correct == True)  # noqa: E712
        .scalar()
        or 0
    )
    accuracy_overall = round(correct / total, 4) if total > 0 else 0.0

    avg_brier = db.query(func.avg(CalibrationRecord.brier_score)).scalar() or 0.0

    # 7-day accuracy: use a simple string-prefix filter on ISO timestamps.
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    total_7d = (
        db.query(func.count(CalibrationRecord.id))
        .filter(CalibrationRecord.recorded_at >= cutoff)
        .scalar()
        or 0
    )
    correct_7d = (
        db.query(func.count(CalibrationRecord.id))
        .filter(CalibrationRecord.recorded_at >= cutoff, CalibrationRecord.correct == True)  # noqa: E712
        .scalar()
        or 0
    )
    accuracy_7d = round(correct_7d / total_7d, 4) if total_7d > 0 else 0.0

    return CalibrationStatsOut(
        accuracy_overall=accuracy_overall,
        accuracy_7d=accuracy_7d,
        total_markets=total,
        correct_calls=correct,
        avg_brier_score=round(float(avg_brier), 4),
        calibration_grade=_compute_grade(accuracy_overall),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=CalibrationStatsOut)
def get_calibration_stats(db: Session = Depends(get_db)) -> CalibrationStatsOut:
    return _get_calibration_stats(db)


@router.get("/history", response_model=List[CalibrationRecordOut])
def get_calibration_history(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> List[CalibrationRecordOut]:
    records = (
        db.query(CalibrationRecord)
        .order_by(CalibrationRecord.recorded_at.desc())
        .limit(limit)
        .all()
    )
    return records  # type: ignore[return-value]


@router.get("/brier-score", response_model=BrierScoreOut)
def get_brier_score(db: Session = Depends(get_db)) -> BrierScoreOut:
    from datetime import datetime, timedelta, timezone

    avg_brier = db.query(func.avg(CalibrationRecord.brier_score)).scalar() or 0.0

    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    rolling_7d = (
        db.query(func.avg(CalibrationRecord.brier_score))
        .filter(CalibrationRecord.recorded_at >= cutoff)
        .scalar()
        or 0.0
    )
    return BrierScoreOut(
        avg_brier=round(float(avg_brier), 4),
        rolling_7d_brier=round(float(rolling_7d), 4),
    )
