"""Markets router — exposes prediction market data with optional Polymarket enrichment."""
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from storage.database import AttestationRecord, MarketRecord, get_db_fastapi as get_db
from services.market_service import MarketService

log = structlog.get_logger()
router = APIRouter()


# ---------------------------------------------------------------------------
# Pydantic response models
# ---------------------------------------------------------------------------


class MarketOut(BaseModel):
    id: str
    question: str
    category: str
    resolution_date: Optional[str]
    current_yes_price: float
    our_latest_estimate: Optional[float]
    our_confidence: Optional[float]
    last_scouted: Optional[str]
    resolved: bool
    actual_resolution: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


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


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/", response_model=List[MarketOut])
async def list_markets(
    resolved: Optional[bool] = Query(None, description="Filter by resolved status"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[MarketOut]:
    """Return markets stored locally, optionally enriched with Polymarket data."""
    query = db.query(MarketRecord)
    if resolved is not None:
        query = query.filter(MarketRecord.resolved == resolved)
    records = query.order_by(MarketRecord.created_at.desc()).limit(limit).all()

    if not records:
        # Attempt to fetch live Polymarket data when DB is empty.
        try:
            service = MarketService(db)
            live = await service.get_live_polymarket_markets(limit=limit)
            return live  # type: ignore[return-value]
        except Exception as exc:
            log.warning("polymarket_fallback_failed", error=str(exc))

    return records  # type: ignore[return-value]


@router.get("/{market_id}", response_model=MarketOut)
def get_market(market_id: str, db: Session = Depends(get_db)) -> MarketOut:
    record = db.query(MarketRecord).filter(MarketRecord.id == market_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Market not found")
    return record  # type: ignore[return-value]


@router.get("/{market_id}/attestations", response_model=List[AttestationOut])
def get_market_attestations(
    market_id: str,
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
) -> List[AttestationOut]:
    records = (
        db.query(AttestationRecord)
        .filter(AttestationRecord.market_id == market_id)
        .order_by(AttestationRecord.timestamp.desc())
        .limit(limit)
        .all()
    )
    return records  # type: ignore[return-value]


@router.get("/{market_id}/latest-attestation", response_model=AttestationOut)
def get_latest_attestation(market_id: str, db: Session = Depends(get_db)) -> AttestationOut:
    record = (
        db.query(AttestationRecord)
        .filter(AttestationRecord.market_id == market_id)
        .order_by(AttestationRecord.timestamp.desc())
        .first()
    )
    if not record:
        raise HTTPException(status_code=404, detail="No attestations found for this market")
    return record  # type: ignore[return-value]
