"""Nanopayments Router — F4
Simulates Circle Gateway micro-payments for unlocking trace data.
All state is in-memory (suitable for hackathon demo).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body, HTTPException

router = APIRouter()

# ── In-memory state ───────────────────────────────────────────────────────────

_payment_history: list[dict[str, Any]] = []

_stats: dict[str, Any] = {
    "total_payments": 0,
    "total_revenue_usdc": 0.0,
    "trace_views": 0,
}

# Traces that have been unlocked (trace_id → True)
_unlocked_traces: set[str] = set()


def _make_circle_payment_id() -> str:
    """Generate a realistic Circle-style payment ID: circ_pay_<UUID4>."""
    return f"circ_pay_{uuid.uuid4()}"


def _make_tx_hash() -> str:
    """Simulate a plausible Arc Testnet transaction hash."""
    return f"0x{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats", summary="Nanopayment aggregate statistics")
async def get_stats() -> dict[str, Any]:
    """Return aggregate nanopayment stats for the Oracle Sentinel demo."""
    return {
        "total_payments": _stats["total_payments"],
        "total_revenue_usdc": round(_stats["total_revenue_usdc"], 6),
        "avg_payment_usdc": (
            round(_stats["total_revenue_usdc"] / _stats["total_payments"], 6)
            if _stats["total_payments"] > 0
            else 0.0
        ),
        "trace_views": _stats["trace_views"],
        "currency": "USDC",
        "gateway": "Circle Programmable Wallets",
        "network": "Arc Testnet",
    }


@router.post("/pay", summary="Process a Circle Gateway nanopayment to unlock a trace")
async def process_payment(
    payload: dict[str, Any] = Body(
        ...,
        example={"trace_id": "trace-abc-001", "amount_usdc": 0.01},
    )
) -> dict[str, Any]:
    """
    Simulate a Circle Gateway nanopayment.

    - Accepts trace_id and amount_usdc.
    - Always succeeds in demo mode.
    - Returns a realistic Circle payment_id and a mock Arc Testnet transaction hash.
    - Marks the trace as unlocked so subsequent GET /history confirms access.
    """
    trace_id: str | None = payload.get("trace_id")
    amount_usdc: float | None = payload.get("amount_usdc")

    if not trace_id:
        raise HTTPException(status_code=422, detail="trace_id is required.")
    if amount_usdc is None:
        raise HTTPException(status_code=422, detail="amount_usdc is required.")
    try:
        amount_usdc = float(amount_usdc)
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="amount_usdc must be a number.")
    if amount_usdc <= 0:
        raise HTTPException(status_code=422, detail="amount_usdc must be positive.")

    payment_id = _make_circle_payment_id()
    tx_hash = _make_tx_hash()
    now = datetime.now(timezone.utc).isoformat()

    # Record the payment
    record: dict[str, Any] = {
        "payment_id": payment_id,
        "trace_id": trace_id,
        "amount_usdc": round(amount_usdc, 6),
        "currency": "USDC",
        "status": "COMPLETE",
        "transaction_hash": tx_hash,
        "network": "Arc Testnet",
        "gateway": "Circle Programmable Wallets",
        "created_at": now,
        "trace_unlocked": True,
    }
    _payment_history.append(record)

    # Update aggregate stats
    _stats["total_payments"] += 1
    _stats["total_revenue_usdc"] += amount_usdc
    _stats["trace_views"] += 1
    _unlocked_traces.add(trace_id)

    return {
        "success": True,
        "payment_id": payment_id,
        "trace_unlocked": True,
        "transaction_hash": tx_hash,
        "amount_usdc": round(amount_usdc, 6),
        "currency": "USDC",
        "created_at": now,
    }


@router.get("/history", summary="List all nanopayment records")
async def get_history(limit: int = 50) -> dict[str, Any]:
    """Return recent nanopayment records (newest first, capped at limit)."""
    records = list(reversed(_payment_history))[:limit]
    return {
        "count": len(records),
        "payments": records,
    }
