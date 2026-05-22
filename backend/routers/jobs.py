"""ERC-8183 agent jobs router."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "agents"))

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from storage.database import get_db, save_job
from storage.models import AgentJob

router = APIRouter()


class JobResponse(BaseModel):
    id: str
    market_id: str
    budget_usdc: float
    status: str
    deliverable_hash: Optional[str] = None
    deliverable_cid: Optional[str] = None
    arc_create_tx: Optional[str] = None
    arc_complete_tx: Optional[str] = None
    usdc_earned: float
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class JobStats(BaseModel):
    total_jobs: int
    completed: int
    failed: int
    pending: int
    total_usdc_earned: float


def _db():
    with get_db() as session:
        yield session


@router.get("/", response_model=list[JobResponse])
async def list_jobs(
    status: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    db: Session = Depends(_db),
):
    q = db.query(AgentJob)
    if status:
        q = q.filter(AgentJob.status == status.upper())
    return q.order_by(AgentJob.created_at.desc()).limit(limit).all()


@router.get("/stats", response_model=JobStats)
async def job_stats(db: Session = Depends(_db)):
    all_jobs = db.query(AgentJob).all()
    total = len(all_jobs)
    completed = sum(1 for j in all_jobs if j.status == "COMPLETED")
    failed = sum(1 for j in all_jobs if j.status == "FAILED")
    pending = sum(1 for j in all_jobs if j.status in ("CREATED", "FUNDED"))
    earned = sum(j.usdc_earned or 0 for j in all_jobs)
    return JobStats(
        total_jobs=total,
        completed=completed,
        failed=failed,
        pending=pending,
        total_usdc_earned=round(earned, 4),
    )


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, db: Session = Depends(_db)):
    job = db.query(AgentJob).filter(AgentJob.id == job_id).first()
    if not job:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Job not found")
    return job
