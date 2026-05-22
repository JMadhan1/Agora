"""Watchdog router — dispute alerts and manipulation detection."""
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from storage.database import DisputeAlertRecord, get_db_fastapi as get_db

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class DisputeAlertOut(BaseModel):
    id: int
    market_id: str
    proposed_resolution: Optional[str] = None
    our_estimate: Optional[float] = None
    sentinel_estimate: Optional[float] = None
    deviation: Optional[float] = None
    reason: Optional[str] = None
    manipulation_suspected: bool
    dispute_triggered: bool
    dispute_tx_hash: Optional[str] = None
    dispute_won: Optional[bool] = None
    reward_usdc: float
    timestamp: str
    created_at: Optional[str] = None

    model_config = {"from_attributes": True}

    def model_post_init(self, __context: object) -> None:
        if self.sentinel_estimate is None:
            self.sentinel_estimate = self.our_estimate
        if self.created_at is None:
            self.created_at = self.timestamp
        if self.reason is None and self.deviation is not None:
            self.reason = f"Deviation {round((self.deviation or 0) * 100)}% detected"


class WatchdogStats(BaseModel):
    total_alerts: int
    triggered: int
    won: int
    total_reward_usdc: float


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=WatchdogStats)
def get_watchdog_stats(db: Session = Depends(get_db)) -> WatchdogStats:
    total_alerts = db.query(func.count(DisputeAlertRecord.id)).scalar() or 0
    triggered = (
        db.query(func.count(DisputeAlertRecord.id))
        .filter(DisputeAlertRecord.dispute_triggered == True)  # noqa: E712
        .scalar()
        or 0
    )
    won = (
        db.query(func.count(DisputeAlertRecord.id))
        .filter(DisputeAlertRecord.dispute_won == True)  # noqa: E712
        .scalar()
        or 0
    )
    total_reward = db.query(func.sum(DisputeAlertRecord.reward_usdc)).scalar() or 0.0

    return WatchdogStats(
        total_alerts=total_alerts,
        triggered=triggered,
        won=won,
        total_reward_usdc=round(float(total_reward), 2),
    )


@router.get("/alerts", response_model=List[DisputeAlertOut])
def list_alerts(
    triggered_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[DisputeAlertOut]:
    query = db.query(DisputeAlertRecord)
    if triggered_only:
        query = query.filter(DisputeAlertRecord.dispute_triggered == True)  # noqa: E712
    records = query.order_by(DisputeAlertRecord.timestamp.desc()).limit(limit).all()
    return records  # type: ignore[return-value]


@router.get("/alerts/{alert_id}", response_model=DisputeAlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)) -> DisputeAlertOut:
    record = db.query(DisputeAlertRecord).filter(DisputeAlertRecord.id == alert_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Alert not found")
    return record  # type: ignore[return-value]
