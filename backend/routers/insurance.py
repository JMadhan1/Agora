"""
Insurance router — REST API for Dispute Insurance marketplace.

GET  /api/insurance/stats        — pool stats (live from contract or fallback)
POST /api/insurance/quote        — calculate premium for coverage amount
POST /api/insurance/buy          — buy a policy (demo: returns simulated tx)
GET  /api/insurance/policies     — list policies for a buyer address
GET  /api/insurance/policy/{id}  — single policy detail
"""
from __future__ import annotations

import os
import time
import uuid
from typing import Annotated

import structlog
from fastapi import APIRouter, Query
from pydantic import BaseModel

log = structlog.get_logger()
router = APIRouter()

DISPUTE_INSURANCE_ADDRESS = os.getenv("DISPUTE_INSURANCE_ADDRESS", "")
PAYOUT_MULTIPLIER = 5
PREMIUM_BPS = 500  # 5%

# In-memory demo policies (persists for the session; real impl uses DB)
_demo_policies: list[dict] = []


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class InsuranceStats(BaseModel):
    pool_balance_usdc: float
    total_premiums_usdc: float
    total_payouts_usdc: float
    total_policies: int
    contract_address: str
    payout_multiplier: int
    premium_rate_pct: float
    network: str


class QuoteRequest(BaseModel):
    coverage_usdc: float  # $10–$1000


class QuoteResponse(BaseModel):
    coverage_usdc: float
    premium_usdc: float
    payout_usdc: float
    premium_rate_pct: float
    payout_multiplier: int
    policy_duration_days: int


class BuyPolicyRequest(BaseModel):
    market_id: str
    coverage_usdc: float
    buyer_address: str


class BuyPolicyResponse(BaseModel):
    success: bool
    policy_id: str
    market_id: str
    coverage_usdc: float
    premium_usdc: float
    payout_usdc: float
    expires_at: int
    tx_hash: str
    arc_scan_url: str
    message: str


class PolicyOut(BaseModel):
    policy_id: str
    buyer: str
    market_id: str
    premium_usdc: float
    coverage_usdc: float
    payout_usdc: float
    purchased_at: int
    expires_at: int
    active: bool
    paid: bool


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@router.get("/stats", response_model=InsuranceStats)
async def get_insurance_stats():
    """Pool statistics — tries on-chain read, falls back to in-memory totals."""
    total_premiums = sum(p["premium_usdc"] for p in _demo_policies)
    total_payouts = sum(p["premium_usdc"] * PAYOUT_MULTIPLIER for p in _demo_policies if p.get("paid"))

    if DISPUTE_INSURANCE_ADDRESS:
        try:
            from arc.arc_client import ArcClient
            # Full arc_client integration would go here
            pass
        except Exception:
            pass

    return InsuranceStats(
        pool_balance_usdc=round(max(0, total_premiums * 3 - total_payouts + 50.0), 2),
        total_premiums_usdc=round(total_premiums, 2),
        total_payouts_usdc=round(total_payouts, 2),
        total_policies=len(_demo_policies),
        contract_address=DISPUTE_INSURANCE_ADDRESS or "0x — deploy DisputeInsurance.sol",
        payout_multiplier=PAYOUT_MULTIPLIER,
        premium_rate_pct=5.0,
        network="Arc Testnet (chainId: 5042002)",
    )


@router.post("/quote", response_model=QuoteResponse)
async def get_quote(req: QuoteRequest):
    """Calculate premium and payout for a given coverage amount."""
    if req.coverage_usdc < 10 or req.coverage_usdc > 1000:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Coverage must be $10–$1,000 USDC")
    premium = round(req.coverage_usdc * PREMIUM_BPS / 10000, 4)
    payout = round(req.coverage_usdc * PAYOUT_MULTIPLIER, 2)
    return QuoteResponse(
        coverage_usdc=req.coverage_usdc,
        premium_usdc=premium,
        payout_usdc=payout,
        premium_rate_pct=5.0,
        payout_multiplier=PAYOUT_MULTIPLIER,
        policy_duration_days=7,
    )


@router.post("/buy", response_model=BuyPolicyResponse)
async def buy_policy(req: BuyPolicyRequest):
    """Purchase a dispute insurance policy."""
    if req.coverage_usdc < 10 or req.coverage_usdc > 1000:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Coverage must be $10–$1,000 USDC")

    premium = round(req.coverage_usdc * PREMIUM_BPS / 10000, 4)
    payout = round(req.coverage_usdc * PAYOUT_MULTIPLIER, 2)
    policy_id = f"pol_{uuid.uuid4().hex[:10]}"
    now = int(time.time())
    expires_at = now + 7 * 24 * 3600
    tx_hash = f"0x{uuid.uuid4().hex}{uuid.uuid4().hex[:32]}"

    policy = {
        "policy_id": policy_id,
        "buyer": req.buyer_address,
        "market_id": req.market_id,
        "premium_usdc": premium,
        "coverage_usdc": req.coverage_usdc,
        "payout_usdc": payout,
        "purchased_at": now,
        "expires_at": expires_at,
        "active": True,
        "paid": False,
    }
    _demo_policies.append(policy)

    log.info(
        "insurance.policy_bought",
        policy_id=policy_id,
        market_id=req.market_id,
        coverage=req.coverage_usdc,
        premium=premium,
    )

    return BuyPolicyResponse(
        success=True,
        policy_id=policy_id,
        market_id=req.market_id,
        coverage_usdc=req.coverage_usdc,
        premium_usdc=premium,
        payout_usdc=payout,
        expires_at=expires_at,
        tx_hash=tx_hash,
        arc_scan_url=f"https://testnet.arcscan.app/tx/{tx_hash}",
        message=(
            f"Policy purchased! If Oracle Sentinel wins a dispute on market {req.market_id}, "
            f"you receive ${payout:.2f} USDC (5× your ${req.coverage_usdc:.2f} coverage)."
        ),
    )


@router.get("/policies", response_model=list[PolicyOut])
async def list_policies(buyer: Annotated[str | None, Query()] = None):
    """List all policies, optionally filtered by buyer address."""
    policies = _demo_policies
    if buyer:
        policies = [p for p in policies if p["buyer"].lower() == buyer.lower()]
    return [PolicyOut(**p) for p in policies]


@router.get("/policy/{policy_id}", response_model=PolicyOut)
async def get_policy(policy_id: str):
    """Get a single policy by ID."""
    for p in _demo_policies:
        if p["policy_id"] == policy_id:
            return PolicyOut(**p)
    from fastapi import HTTPException
    raise HTTPException(status_code=404, detail="Policy not found")
