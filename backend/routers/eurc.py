"""EURC Market Router — F10
Exposes curated EU prediction markets and EURC-denominated attestations.
Settlement currency: EURC (Circle Euro stablecoin, ERC-20).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Body

router = APIRouter()

# ── Curated EU market catalogue ───────────────────────────────────────────────

_EU_MARKETS: list[dict[str, Any]] = [
    {
        "market_id": "eurc-001",
        "question": "Will the ECB cut its main refinancing rate by at least 25 bps at the June 2026 meeting?",
        "category": "Monetary Policy",
        "source": "European Central Bank",
        "resolution_date": "2026-06-12",
        "resolution_criteria": (
            "Resolves YES if the ECB Governing Council announces a reduction of ≥25 bps "
            "in the main refinancing operations rate at its June 2026 monetary policy meeting. "
            "Resolves NO otherwise."
        ),
        "settlement_currency": "EURC",
        "yes_price": 0.61,
        "no_price": 0.39,
        "volume_eurc": 142_500.00,
        "open_interest_eurc": 38_200.00,
        "tags": ["ECB", "interest-rates", "eurozone", "monetary-policy"],
    },
    {
        "market_id": "eurc-002",
        "question": "Will Eurozone CPI (flash estimate) come in below 2.0% year-on-year for May 2026?",
        "category": "Economic Data",
        "source": "Eurostat",
        "resolution_date": "2026-06-02",
        "resolution_criteria": (
            "Resolves YES if Eurostat's flash estimate for Eurozone HICP YoY for May 2026 "
            "is published at < 2.0%. Resolves NO if ≥ 2.0%."
        ),
        "settlement_currency": "EURC",
        "yes_price": 0.47,
        "no_price": 0.53,
        "volume_eurc": 89_750.00,
        "open_interest_eurc": 21_600.00,
        "tags": ["CPI", "inflation", "eurostat", "eurozone"],
    },
    {
        "market_id": "eurc-003",
        "question": "Will the far-right RN party win the most seats in the 2027 French legislative elections?",
        "category": "EU Elections",
        "source": "French Interior Ministry",
        "resolution_date": "2027-06-30",
        "resolution_criteria": (
            "Resolves YES if Rassemblement National (RN) or its direct electoral alliance wins "
            "more Assemblée Nationale seats than any other single party or alliance in the first "
            "or second round of the 2027 French legislative elections."
        ),
        "settlement_currency": "EURC",
        "yes_price": 0.38,
        "no_price": 0.62,
        "volume_eurc": 215_000.00,
        "open_interest_eurc": 67_300.00,
        "tags": ["France", "elections", "RN", "legislative", "EU-politics"],
    },
    {
        "market_id": "eurc-004",
        "question": "Will Germany's GDP growth for Q1 2026 be positive (avoid a technical recession)?",
        "category": "Economic Data",
        "source": "Destatis / Eurostat",
        "resolution_date": "2026-05-30",
        "resolution_criteria": (
            "Resolves YES if Destatis' flash estimate of German GDP QoQ growth for Q1 2026 "
            "is ≥ 0.0%. Resolves NO if the reading is negative."
        ),
        "settlement_currency": "EURC",
        "yes_price": 0.55,
        "no_price": 0.45,
        "volume_eurc": 178_300.00,
        "open_interest_eurc": 44_800.00,
        "tags": ["Germany", "GDP", "recession", "eurozone", "economics"],
    },
    {
        "market_id": "eurc-005",
        "question": "Will the EU AI Act's first tier of obligations (GPAI providers) be enforced before August 2026?",
        "category": "EU Regulation",
        "source": "European Commission",
        "resolution_date": "2026-08-01",
        "resolution_criteria": (
            "Resolves YES if the European Commission formally initiates at least one enforcement action "
            "or issues at least one compliance notice to a GPAI model provider under the EU AI Act "
            "before 2026-08-01. Resolves NO otherwise."
        ),
        "settlement_currency": "EURC",
        "yes_price": 0.29,
        "no_price": 0.71,
        "volume_eurc": 63_400.00,
        "open_interest_eurc": 15_200.00,
        "tags": ["AI-Act", "EU-regulation", "GPAI", "tech-policy"],
    },
]

# ── In-memory attestation store ───────────────────────────────────────────────

_MOCK_ATTESTATIONS: list[dict[str, Any]] = [
    {
        "attestation_id": "att-eurc-0001",
        "market_id": "eurc-001",
        "agent_id": "scout-eu-01",
        "outcome": "YES",
        "confidence": 0.63,
        "amount_eurc": 50.00,
        "tx_hash": "0xabc123def456aaa000111222333444555666777888999aaabbbccc",
        "created_at": "2026-05-17T10:22:00Z",
        "on_chain": True,
    },
    {
        "attestation_id": "att-eurc-0002",
        "market_id": "eurc-002",
        "agent_id": "judge-eu-01",
        "outcome": "NO",
        "confidence": 0.54,
        "amount_eurc": 25.00,
        "tx_hash": "0xdeadbeef01020304050607080910111213141516171819202122",
        "created_at": "2026-05-18T08:45:00Z",
        "on_chain": True,
    },
    {
        "attestation_id": "att-eurc-0003",
        "market_id": "eurc-004",
        "agent_id": "scout-eu-01",
        "outcome": "YES",
        "confidence": 0.58,
        "amount_eurc": 40.00,
        "tx_hash": "0xcafe0001cafe0002cafe0003cafe0004cafe0005cafe0006cafe",
        "created_at": "2026-05-19T06:00:00Z",
        "on_chain": False,
    },
]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/markets", summary="List curated EU prediction markets")
async def list_eurc_markets() -> dict[str, Any]:
    """Return the curated list of EU-focused prediction markets settled in EURC."""
    return {
        "settlement_currency": "EURC",
        "count": len(_EU_MARKETS),
        "markets": _EU_MARKETS,
    }


@router.get("/attestations", summary="EURC-denominated attestations")
async def list_eurc_attestations(market_id: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Return mock EURC-denominated attestations, optionally filtered by market_id."""
    results = _MOCK_ATTESTATIONS
    if market_id:
        results = [a for a in results if a["market_id"] == market_id]
    results = results[:limit]
    return {
        "settlement_currency": "EURC",
        "count": len(results),
        "attestations": results,
    }


@router.post("/attest", summary="Submit a simulated EURC attestation")
async def create_eurc_attestation(
    payload: dict[str, Any] = Body(
        ...,
        example={"market_id": "eurc-001", "question": "Will the ECB cut rates in June 2026?"},
    )
) -> dict[str, Any]:
    """
    Accept a market_id and optional question; return a simulated EURC attestation.
    In production this would trigger the Scout→Judge pipeline and publish on-chain.
    """
    market_id: str = payload.get("market_id", "eurc-unknown")
    question: str = payload.get("question", "")

    # Resolve market question from catalogue if not provided
    if not question:
        for m in _EU_MARKETS:
            if m["market_id"] == market_id:
                question = m["question"]
                break

    attestation_id = f"att-eurc-{uuid.uuid4().hex[:8]}"
    tx_hash = f"0x{uuid.uuid4().hex}{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()

    new_attestation: dict[str, Any] = {
        "attestation_id": attestation_id,
        "market_id": market_id,
        "question": question,
        "agent_id": "oracle-sentinel-auto",
        "outcome": "PENDING",
        "confidence": None,
        "amount_eurc": 10.00,
        "settlement_currency": "EURC",
        "tx_hash": tx_hash,
        "created_at": now,
        "on_chain": False,
        "pipeline_status": "scout_dispatched",
        "contracts": {
            "attestation_vault": "0x4dE6AF7329E88F08C0560DAf1290a0DF152901E3",
            "bond_manager": "0x2274D05C24527D0e4b689b215ddEAfE51B319008",
            "registry": "0x165825Bd33c87c8aE31d60211dE9EE93e8039adE",
        },
        "message": "Scout→Judge pipeline dispatched. Attestation will be updated on-chain once consensus is reached.",
    }

    _MOCK_ATTESTATIONS.append(new_attestation)
    return new_attestation
