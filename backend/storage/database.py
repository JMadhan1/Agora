"""SQLAlchemy database setup for Oracle Sentinel backend."""
import os
from typing import Generator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./oracle_sentinel.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# ORM Models
# ---------------------------------------------------------------------------


class MarketRecord(Base):
    __tablename__ = "markets"

    id = Column(String, primary_key=True, index=True)
    question = Column(Text, nullable=False)
    category = Column(String, default="general")
    resolution_date = Column(String, nullable=True)
    current_yes_price = Column(Float, default=0.5)
    our_latest_estimate = Column(Float, nullable=True)
    our_confidence = Column(Float, nullable=True)
    last_scouted = Column(String, nullable=True)
    resolved = Column(Boolean, default=False)
    actual_resolution = Column(String, nullable=True)
    created_at = Column(String, default="")


class AttestationRecord(Base):
    __tablename__ = "attestations"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    market_id = Column(String, index=True, nullable=False)
    trace_hash = Column(String, nullable=True)
    ipfs_cid = Column(String, nullable=True)
    arc_tx_hash = Column(String, nullable=True)
    arc_scan_url = Column(String, nullable=True)
    arc_block_number = Column(Integer, nullable=True)
    confidence = Column(Float, default=0.0)
    recommendation = Column(String, default="UNCERTAIN")
    probability_estimate = Column(Float, default=0.5)
    timestamp = Column(String, nullable=False)


class AgentJobRecord(Base):
    __tablename__ = "agent_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    job_id = Column(String, unique=True, index=True, nullable=False)
    agent_address = Column(String, nullable=False)
    market_id = Column(String, nullable=True)
    status = Column(String, default="PENDING")
    usdc_earned = Column(Float, default=0.0)
    arc_tx_hash = Column(String, nullable=True)
    arc_scan_url = Column(String, nullable=True)
    started_at = Column(String, nullable=True)
    completed_at = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)


class DisputeAlertRecord(Base):
    __tablename__ = "dispute_alerts"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    market_id = Column(String, index=True, nullable=False)
    proposed_resolution = Column(String, nullable=True)
    our_estimate = Column(Float, nullable=True)
    deviation = Column(Float, nullable=True)
    manipulation_suspected = Column(Boolean, default=False)
    dispute_triggered = Column(Boolean, default=False)
    dispute_tx_hash = Column(String, nullable=True)
    dispute_won = Column(Boolean, nullable=True)
    reward_usdc = Column(Float, default=0.0)
    timestamp = Column(String, nullable=False)


class CalibrationRecord(Base):
    __tablename__ = "calibration_records"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    market_id = Column(String, index=True, nullable=False)
    our_estimate = Column(Float, nullable=False)
    actual_outcome = Column(Float, nullable=False)
    brier_score = Column(Float, nullable=True)
    correct = Column(Boolean, nullable=True)
    recorded_at = Column(String, nullable=False)


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def init_db() -> None:
    """Create all tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and ensures it's closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
