"""
Reasoning trace builder for Oracle Sentinel Judge agent.

Constructs a fully serializable ReasoningTrace dataclass capturing the
complete audit trail from raw scout evidence through Bayesian inference to
the final recommendation. Also computes the SHA-256 digest of the
canonically serialised trace for on-chain attestation.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

import structlog

log = structlog.get_logger(__name__)


@dataclass
class EvidenceSummary:
    """Condensed view of one scout's evidence contribution."""

    scout_type: str
    facts: list[str]
    supports_yes: float
    confidence: float
    source_urls: list[str]
    reliability_weight: float


@dataclass
class ReasoningTrace:
    """
    Complete audit trail for a single market judgement.

    This dataclass is serialised to JSON, hashed, and the hash is committed
    to the Arc Testnet AttestationVault.  Every field is included in the
    canonical hash so any post-hoc tampering is detectable.
    """

    # Market identifiers
    market_id: str
    market_question: str
    resolution_date: str

    # Price context
    current_market_price: float
    prior_probability: float

    # Probability result
    final_probability: float
    confidence_interval_lo: float
    confidence_interval_hi: float
    num_evidence_pieces: int
    brier_score_prediction: float

    # Recommendation
    recommendation: str  # "YES" | "NO" | "UNCERTAIN"

    # Evidence summaries
    evidence_summaries: list[EvidenceSummary]

    # Bayesian log (serialised as list of dicts)
    bayesian_log: list[dict]

    # Narrative
    llm_narrative: str

    # On-chain references
    attestation_contract: str
    ipfs_cid: str = ""

    # Metadata
    agent_version: str = "1.0.0"
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    trace_schema_version: str = "1"


def build_trace(
    market_id: str,
    market_question: str,
    resolution_date: str,
    evidences: list[Any],
    probability_result: Any,
    llm_narrative: str,
    current_market_price: float,
    attestation_contract: str,
) -> tuple[ReasoningTrace, bytes]:
    """
    Construct a ReasoningTrace and return it together with its SHA-256 digest.

    The digest is computed over the canonically serialised JSON
    (``sort_keys=True``) so the same trace always produces the same hash
    regardless of Python dict insertion order.

    Args:
        market_id: Polymarket condition / market ID.
        market_question: Human-readable resolution question.
        resolution_date: ISO-8601 resolution deadline.
        evidences: Filtered list of Evidence instances from scouts.
        probability_result: ProbabilityResult from compute_posterior().
        llm_narrative: Claude-generated human-readable narrative.
        current_market_price: Live Polymarket YES price at judgement time.
        attestation_contract: Arc contract address receiving the attestation.

    Returns:
        (trace, sha256_digest_bytes)
    """
    final_prob = probability_result.final_probability
    ci_lo, ci_hi = probability_result.confidence_interval

    if final_prob > 0.6:
        recommendation = "YES"
    elif final_prob < 0.4:
        recommendation = "NO"
    else:
        recommendation = "UNCERTAIN"

    evidence_summaries: list[EvidenceSummary] = []
    for ev in evidences:
        summary = EvidenceSummary(
            scout_type=getattr(ev, "scout_type", "unknown"),
            facts=list(getattr(ev, "extracted_facts", [])),
            supports_yes=float(getattr(ev, "supports_yes_probability", 0.5)),
            confidence=float(getattr(ev, "confidence", 0.0)),
            source_urls=list(getattr(ev, "source_urls", [])),
            reliability_weight=float(getattr(ev, "reliability_weight", 0.5)),
        )
        evidence_summaries.append(summary)

    bayesian_log_dicts: list[dict] = []
    for update in probability_result.bayesian_log:
        bayesian_log_dicts.append(
            {
                "prior": update.prior,
                "likelihood_yes": update.likelihood_yes,
                "likelihood_no": update.likelihood_no,
                "posterior": update.posterior,
                "scout_type": update.scout_type,
                "reliability_weight": update.reliability_weight,
            }
        )

    trace = ReasoningTrace(
        market_id=market_id,
        market_question=market_question,
        resolution_date=str(resolution_date),
        current_market_price=float(current_market_price),
        prior_probability=float(current_market_price),
        final_probability=float(final_prob),
        confidence_interval_lo=float(ci_lo),
        confidence_interval_hi=float(ci_hi),
        num_evidence_pieces=probability_result.num_evidence_pieces,
        brier_score_prediction=float(probability_result.brier_score_prediction),
        recommendation=recommendation,
        evidence_summaries=evidence_summaries,
        bayesian_log=bayesian_log_dicts,
        llm_narrative=llm_narrative,
        attestation_contract=attestation_contract,
    )

    trace_dict = asdict(trace)
    trace_json = json.dumps(trace_dict, sort_keys=True, default=str)
    trace_hash = hashlib.sha256(trace_json.encode("utf-8")).digest()

    log.info(
        "trace_builder.built",
        market_id=market_id,
        recommendation=recommendation,
        final_probability=round(final_prob, 4),
        trace_hash_hex=trace_hash.hex()[:16] + "...",
        evidence_count=len(evidence_summaries),
    )

    return trace, trace_hash
