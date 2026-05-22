"""Attestations router — on-chain truth records written to Arc."""
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from storage.database import AttestationRecord, get_db_fastapi as get_db

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class AttestationOut(BaseModel):
    id: int
    market_id: str
    trace_hash: Optional[str]
    ipfs_cid: Optional[str]
    arc_tx_hash: Optional[str]
    arc_scan_url: Optional[str]
    arc_block_number: Optional[int]
    confidence: float
    recommendation: str
    probability_estimate: float
    timestamp: str

    model_config = {"from_attributes": True}


class AttestationStats(BaseModel):
    total: int
    by_recommendation: dict
    avg_confidence: float


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=AttestationStats)
def get_attestation_stats(db: Session = Depends(get_db)) -> AttestationStats:
    total = db.query(func.count(AttestationRecord.id)).scalar() or 0

    yes_count = (
        db.query(func.count(AttestationRecord.id))
        .filter(AttestationRecord.recommendation == "YES")
        .scalar()
        or 0
    )
    no_count = (
        db.query(func.count(AttestationRecord.id))
        .filter(AttestationRecord.recommendation == "NO")
        .scalar()
        or 0
    )
    uncertain_count = (
        db.query(func.count(AttestationRecord.id))
        .filter(AttestationRecord.recommendation == "UNCERTAIN")
        .scalar()
        or 0
    )

    avg_confidence = db.query(func.avg(AttestationRecord.confidence)).scalar() or 0.0

    return AttestationStats(
        total=total,
        by_recommendation={"YES": yes_count, "NO": no_count, "UNCERTAIN": uncertain_count},
        avg_confidence=round(float(avg_confidence), 4),
    )


@router.get("/", response_model=List[AttestationOut])
def list_attestations(
    market_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[AttestationOut]:
    query = db.query(AttestationRecord)
    if market_id:
        query = query.filter(AttestationRecord.market_id == market_id)
    records = query.order_by(AttestationRecord.timestamp.desc()).limit(limit).all()
    return records  # type: ignore[return-value]


@router.get("/{attestation_id}", response_model=AttestationOut)
def get_attestation(attestation_id: int, db: Session = Depends(get_db)) -> AttestationOut:
    record = db.query(AttestationRecord).filter(AttestationRecord.id == attestation_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Attestation not found")
    return record  # type: ignore[return-value]
