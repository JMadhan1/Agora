"""SQLAlchemy 2.x ORM models for Oracle Sentinel persistent state."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Market(Base):
    """A Polymarket prediction market being monitored."""

    __tablename__ = "markets"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    question: Mapped[str] = mapped_column(String, nullable=False, default="")
    category: Mapped[str] = mapped_column(String, nullable=False, default="")
    resolution_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    current_yes_price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    our_latest_estimate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    our_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    last_scouted: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    actual_resolution: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    attestations: Mapped[list["Attestation"]] = relationship(
        "Attestation", back_populates="market", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return (
            f"<Market id={self.id!r} question={self.question[:40]!r} "
            f"resolved={self.resolved} estimate={self.our_latest_estimate:.3f}>"
        )


class Attestation(Base):
    """An on-chain attestation committed to the Arc Testnet AttestationVault."""

    __tablename__ = "attestations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(
        String, ForeignKey("markets.id"), nullable=False
    )
    trace_hash: Mapped[str] = mapped_column(String, nullable=False, default="")
    ipfs_cid: Mapped[str] = mapped_column(String, nullable=False, default="")
    arc_tx_hash: Mapped[str] = mapped_column(String, nullable=False, default="")
    arc_scan_url: Mapped[str] = mapped_column(String, nullable=False, default="")
    arc_block_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recommendation: Mapped[str] = mapped_column(String, nullable=False, default="")
    probability_estimate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    market: Mapped["Market"] = relationship("Market", back_populates="attestations")

    def __repr__(self) -> str:
        return (
            f"<Attestation id={self.id} market_id={self.market_id!r} "
            f"confidence={self.confidence} tx={self.arc_tx_hash[:12]!r}>"
        )


class AgentJob(Base):
    """A job posted to and completed via AgenticCommerce on Arc Testnet."""

    __tablename__ = "agent_jobs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    market_id: Mapped[str] = mapped_column(String, nullable=False, default="")
    budget_usdc: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    status: Mapped[str] = mapped_column(String, nullable=False, default="CREATED")
    deliverable_hash: Mapped[str] = mapped_column(String, nullable=False, default="")
    deliverable_cid: Mapped[str] = mapped_column(String, nullable=False, default="")
    arc_create_tx: Mapped[str] = mapped_column(String, nullable=False, default="")
    arc_complete_tx: Mapped[str] = mapped_column(String, nullable=False, default="")
    usdc_earned: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AgentJob id={self.id!r} market_id={self.market_id!r} "
            f"status={self.status!r} budget={self.budget_usdc:.2f} USDC "
            f"earned={self.usdc_earned:.2f} USDC>"
        )


class DisputeAlert(Base):
    """A dispute alert raised when market price diverges from our Bayesian estimate."""

    __tablename__ = "dispute_alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String, nullable=False)
    proposed_resolution: Mapped[str] = mapped_column(String, nullable=False, default="")
    our_estimate: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    deviation: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    manipulation_suspected: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    dispute_triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    dispute_tx_hash: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    dispute_won: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    reward_usdc: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<DisputeAlert id={self.id} market_id={self.market_id!r} "
            f"deviation={self.deviation:.3f} triggered={self.dispute_triggered} "
            f"won={self.dispute_won}>"
        )


class CalibrationRecord(Base):
    """Post-resolution calibration record for Brier scoring and accuracy tracking."""

    __tablename__ = "calibration_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    market_id: Mapped[str] = mapped_column(String, nullable=False)
    our_prediction: Mapped[str] = mapped_column(String, nullable=False, default="")
    our_confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    actual_resolution: Mapped[str] = mapped_column(String, nullable=False, default="")
    correct: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    brier_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow
    )

    def __repr__(self) -> str:
        return (
            f"<CalibrationRecord id={self.id} market_id={self.market_id!r} "
            f"correct={self.correct} brier={self.brier_score:.4f} "
            f"confidence={self.our_confidence:.3f}>"
        )
