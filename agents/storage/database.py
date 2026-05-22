"""Database engine, session factory, and CRUD helpers for Oracle Sentinel."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator

import structlog
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session, sessionmaker

from .models import (
    Attestation,
    AgentJob,
    Base,
    CalibrationRecord,
    DisputeAlert,
    Market,
)

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Model aliases (for backend router compatibility)
# ---------------------------------------------------------------------------

AttestationRecord = Attestation
MarketRecord = Market
DisputeAlertRecord = DisputeAlert

# ---------------------------------------------------------------------------
# Engine & session factory
# ---------------------------------------------------------------------------

_DB_PATH = Path(__file__).parent.parent / "data" / "oracle_sentinel.db"
_DB_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(_DB_URL, echo=False, connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create all tables and ensure the data directory exists."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    log.info("database_initialized", path=str(_DB_PATH))


# ---------------------------------------------------------------------------
# Session context manager
# ---------------------------------------------------------------------------


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy Session and close it on exit."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_fastapi() -> Generator[Session, None, None]:
    """FastAPI-compatible generator dependency (use with Depends())."""
    session: Session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# CRUD helpers
# ---------------------------------------------------------------------------


def upsert_market(session: Session, data: dict) -> Market:
    """Insert or update a Market row by primary key (id)."""
    market = session.get(Market, data["id"])
    if market is None:
        market = Market(id=data["id"])
        session.add(market)
    for key, value in data.items():
        if key != "id" and hasattr(market, key):
            setattr(market, key, value)
    session.flush()
    log.debug("upsert_market", market_id=data["id"])
    return market


def save_attestation(session: Session, data: dict) -> Attestation:
    """Persist a new Attestation row."""
    attestation = Attestation(**{k: v for k, v in data.items() if hasattr(Attestation, k)})
    session.add(attestation)
    session.flush()
    log.info(
        "attestation_saved",
        market_id=attestation.market_id,
        arc_tx_hash=attestation.arc_tx_hash,
    )
    return attestation


def save_job(session: Session, data: dict) -> AgentJob:
    """Persist a new (or update existing) AgentJob row."""
    job = session.get(AgentJob, data.get("id", ""))
    if job is None:
        job = AgentJob(**{k: v for k, v in data.items() if hasattr(AgentJob, k)})
        session.add(job)
    else:
        for key, value in data.items():
            if key != "id" and hasattr(job, key):
                setattr(job, key, value)
    session.flush()
    log.info("job_saved", job_id=job.id, status=job.status)
    return job


def save_dispute_alert(session: Session, data: dict) -> DisputeAlert:
    """Persist a new DisputeAlert row."""
    alert = DisputeAlert(**{k: v for k, v in data.items() if hasattr(DisputeAlert, k)})
    session.add(alert)
    session.flush()
    log.info(
        "dispute_alert_saved",
        market_id=alert.market_id,
        deviation=alert.deviation,
        triggered=alert.dispute_triggered,
    )
    return alert


def save_calibration_record(session: Session, data: dict) -> CalibrationRecord:
    """Persist a new CalibrationRecord row."""
    record = CalibrationRecord(
        **{k: v for k, v in data.items() if hasattr(CalibrationRecord, k)}
    )
    session.add(record)
    session.flush()
    log.info(
        "calibration_record_saved",
        market_id=record.market_id,
        correct=record.correct,
        brier_score=record.brier_score,
    )
    return record


def get_markets(
    session: Session,
    resolved: bool | None = None,
    limit: int = 100,
) -> list[Market]:
    """Return a list of Market rows, optionally filtered by resolution status."""
    stmt = select(Market)
    if resolved is not None:
        stmt = stmt.where(Market.resolved == resolved)
    stmt = stmt.limit(limit)
    return list(session.scalars(stmt).all())


def get_attestations(
    session: Session,
    market_id: str | None = None,
    limit: int = 50,
) -> list[Attestation]:
    """Return Attestation rows, optionally filtered by market_id."""
    stmt = select(Attestation).order_by(Attestation.timestamp.desc())
    if market_id is not None:
        stmt = stmt.where(Attestation.market_id == market_id)
    stmt = stmt.limit(limit)
    return list(session.scalars(stmt).all())


def get_latest_attestation(session: Session, market_id: str) -> Attestation | None:
    """Return the most recent Attestation for a given market, or None."""
    stmt = (
        select(Attestation)
        .where(Attestation.market_id == market_id)
        .order_by(Attestation.timestamp.desc())
        .limit(1)
    )
    return session.scalars(stmt).first()


def get_calibration_stats(session: Session) -> dict:
    """
    Compute aggregate calibration metrics.

    Returns:
        accuracy_overall  – fraction of correct calls over all time
        accuracy_7d       – fraction of correct calls in the last 7 days
        total_markets     – total number of resolved markets with a record
        correct_calls     – total number of correct calls
        avg_brier_score   – mean Brier score (lower is better; 0 = perfect)
        calibration_grade – letter grade derived from avg_brier_score
    """
    # All-time stats
    total: int = session.scalar(select(func.count(CalibrationRecord.id))) or 0
    correct: int = (
        session.scalar(
            select(func.count(CalibrationRecord.id)).where(
                CalibrationRecord.correct == True  # noqa: E712
            )
        )
        or 0
    )
    avg_brier: float = (
        session.scalar(select(func.avg(CalibrationRecord.brier_score))) or 0.0
    )

    # 7-day accuracy
    cutoff = datetime.utcnow() - timedelta(days=7)
    total_7d: int = (
        session.scalar(
            select(func.count(CalibrationRecord.id)).where(
                CalibrationRecord.timestamp >= cutoff
            )
        )
        or 0
    )
    correct_7d: int = (
        session.scalar(
            select(func.count(CalibrationRecord.id)).where(
                CalibrationRecord.correct == True,  # noqa: E712
                CalibrationRecord.timestamp >= cutoff,
            )
        )
        or 0
    )

    accuracy_overall = correct / total if total > 0 else 0.0
    accuracy_7d = correct_7d / total_7d if total_7d > 0 else 0.0

    # Brier-score letter grade (scale 0–1; lower is better)
    # A: ≤0.05, B: ≤0.10, C: ≤0.15, D: ≤0.20, F: >0.20
    if avg_brier <= 0.05:
        grade = "A"
    elif avg_brier <= 0.10:
        grade = "B"
    elif avg_brier <= 0.15:
        grade = "C"
    elif avg_brier <= 0.20:
        grade = "D"
    else:
        grade = "F"

    return {
        "accuracy_overall": round(accuracy_overall, 4),
        "accuracy_7d": round(accuracy_7d, 4),
        "total_markets": total,
        "correct_calls": correct,
        "avg_brier_score": round(avg_brier, 6),
        "calibration_grade": grade,
    }
