"""ERC-8183 agent jobs router."""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from storage.database import AgentJobRecord, get_db_fastapi as get_db

router = APIRouter()


class JobResponse(BaseModel):
    id: int
    job_id: str
    agent_address: str
    market_id: Optional[str] = None
    status: str
    usdc_earned: float
    arc_tx_hash: Optional[str] = None
    arc_scan_url: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    error_message: Optional[str] = None

    model_config = {"from_attributes": True}


class JobStats(BaseModel):
    total_jobs: int
    completed: int
    failed: int
    pending: int
    total_usdc_earned: float


@router.get("/", response_model=list[JobResponse])
def list_jobs(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(AgentJobRecord)
    if status:
        q = q.filter(AgentJobRecord.status == status.upper())
    return q.order_by(AgentJobRecord.id.desc()).limit(limit).all()


@router.get("/stats", response_model=JobStats)
def job_stats(db: Session = Depends(get_db)):
    total = db.query(func.count(AgentJobRecord.id)).scalar() or 0
    completed = db.query(func.count(AgentJobRecord.id)).filter(AgentJobRecord.status == "COMPLETED").scalar() or 0
    failed = db.query(func.count(AgentJobRecord.id)).filter(AgentJobRecord.status == "FAILED").scalar() or 0
    pending = db.query(func.count(AgentJobRecord.id)).filter(AgentJobRecord.status.in_(["PENDING", "CREATED", "FUNDED"])).scalar() or 0
    earned = db.query(func.sum(AgentJobRecord.usdc_earned)).scalar() or 0.0
    return JobStats(
        total_jobs=total,
        completed=completed,
        failed=failed,
        pending=pending,
        total_usdc_earned=round(float(earned), 4),
    )


@router.get("/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    record = db.query(AgentJobRecord).filter(AgentJobRecord.job_id == job_id).first()
    if not record:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return record
