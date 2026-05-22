"""
Oracle Sentinel Judge Agent — LangGraph state machine.

Orchestrates the full judgement pipeline:
  validate_evidence → compute_probability → generate_narrative →
  build_trace → publish_ipfs → commit_arc → END

Each node is a pure async function operating on JudgementState. The graph
is compiled once at module load; JudgeAgent.judge_market() invokes it.
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, TypedDict

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph

from .calibration_tracker import get_calibration_stats
from .ipfs_publisher import upload_to_irys
from .probability_engine import compute_posterior
from .trace_builder import build_trace

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Arc AttestationVault minimal ABI
# ---------------------------------------------------------------------------

_ATTESTATION_VAULT_ABI = [
    {
        "inputs": [
            {"name": "marketId", "type": "string"},
            {"name": "traceHash", "type": "bytes32"},
            {"name": "ipfsCid", "type": "string"},
            {"name": "probability", "type": "uint256"},
            {"name": "confidence", "type": "uint256"},
            {"name": "recommendation", "type": "string"},
        ],
        "name": "commitAttestation",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "attestationId", "type": "uint256"}],
        "name": "getAttestation",
        "outputs": [
            {"name": "marketId", "type": "string"},
            {"name": "traceHash", "type": "bytes32"},
            {"name": "ipfsCid", "type": "string"},
            {"name": "probability", "type": "uint256"},
            {"name": "confidence", "type": "uint256"},
            {"name": "recommendation", "type": "string"},
            {"name": "timestamp", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
]


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


class JudgementState(TypedDict):
    market_id: str
    market_question: str
    resolution_date: str
    current_market_price: float
    scout_evidences: list
    filtered_evidences: list
    probability_result: Any | None
    llm_narrative: str
    trace: Any | None
    trace_hash: bytes | None
    ipfs_cid: str
    arc_attestation: dict | None
    error: str | None


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------


def _make_empty_state_defaults() -> dict:
    return {
        "filtered_evidences": [],
        "probability_result": None,
        "llm_narrative": "",
        "trace": None,
        "trace_hash": None,
        "ipfs_cid": "",
        "arc_attestation": None,
        "error": None,
    }


async def node_validate_evidence(state: JudgementState) -> dict:
    """Filter evidences to those with confidence > 0.1.

    If no evidence passes the threshold, falls back to keeping any evidence
    from a market_data scout so the pipeline always has at least some signal.
    """
    raw = state.get("scout_evidences") or []
    passed = [
        ev for ev in raw if getattr(ev, "confidence", 0.0) > 0.1
    ]

    if not passed:
        # Fallback: keep market_data scout evidence regardless of confidence.
        market_data_ev = [
            ev for ev in raw if getattr(ev, "scout_type", "") == "market_data"
        ]
        passed = market_data_ev

    log.info(
        "judge.validate_evidence",
        market_id=state.get("market_id"),
        total=len(raw),
        accepted=len(passed),
    )
    return {"filtered_evidences": passed}


async def node_compute_probability(state: JudgementState) -> dict:
    """Run Bayesian inference over filtered evidence."""
    prior = float(state.get("current_market_price") or 0.5)
    evidences = state.get("filtered_evidences") or []

    result = compute_posterior(prior=prior, evidences=evidences)

    log.info(
        "judge.probability_computed",
        market_id=state.get("market_id"),
        prior=round(prior, 4),
        posterior=round(result.final_probability, 4),
        n_evidence=result.num_evidence_pieces,
    )
    return {"probability_result": result}


async def node_generate_narrative(state: JudgementState, anthropic_api_key: str) -> dict:
    """Generate a human-readable 3-paragraph narrative via Claude Haiku."""
    result = state["probability_result"]
    evidences = state.get("filtered_evidences") or []
    market_question = state.get("market_question", "")
    final_prob = result.final_probability

    # Summarise evidence for the prompt.
    evidence_bullets = []
    for ev in evidences[:10]:  # cap at 10 to stay within context
        scout = getattr(ev, "scout_type", "unknown")
        facts = getattr(ev, "extracted_facts", [])[:3]
        p_yes = getattr(ev, "supports_yes_probability", 0.5)
        for fact in facts:
            evidence_bullets.append(f"- [{scout}] {fact}")
        if not facts:
            evidence_bullets.append(f"- [{scout}] supports_yes={p_yes:.2f}")

    evidence_text = "\n".join(evidence_bullets) if evidence_bullets else "No structured evidence available."

    bayesian_summary = ""
    for step in (result.bayesian_log or [])[:5]:
        bayesian_summary += (
            f"  {step.scout_type}: prior={step.prior:.3f} → posterior={step.posterior:.3f} "
            f"(likelihood_yes={step.likelihood_yes:.3f})\n"
        )
    if not bayesian_summary:
        bayesian_summary = "  No Bayesian updates applied.\n"

    ci_lo, ci_hi = result.confidence_interval
    recommendation = "YES" if final_prob > 0.6 else "NO" if final_prob < 0.4 else "UNCERTAIN"

    system_prompt = (
        "You are a professional prediction market analyst. Write precise, evidence-based "
        "analysis. Do not use hedging phrases like 'it seems' or 'perhaps'. "
        "Your output must be exactly three paragraphs with no headers."
    )

    user_prompt = f"""Market question: {market_question}

Evidence gathered:
{evidence_text}

Bayesian inference steps:
{bayesian_summary}
Final probability estimate: {final_prob:.1%}
95% credible interval: [{ci_lo:.1%}, {ci_hi:.1%}]
Recommendation: {recommendation}

Write a 3-paragraph analytical narrative:
Paragraph 1: Summarise the key evidence and what it tells us about likely resolution.
Paragraph 2: Explain the Bayesian reasoning — how each evidence source shifted the probability.
Paragraph 3: State the final recommendation with a clear rationale and note key uncertainties.
"""

    try:
        llm = ChatAnthropic(
            model="claude-haiku-4-5-20251001",
            api_key=anthropic_api_key,
            max_tokens=600,
            temperature=0.2,
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
        response = await llm.ainvoke(messages)
        narrative = response.content.strip()
    except Exception as exc:  # noqa: BLE001
        log.warning("judge.narrative_error", error=str(exc))
        narrative = (
            f"Automated analysis: The Bayesian probability engine processed "
            f"{result.num_evidence_pieces} evidence pieces and produced a final "
            f"probability estimate of {final_prob:.1%} (recommendation: {recommendation}). "
            f"The 95% credible interval spans [{ci_lo:.1%}, {ci_hi:.1%}]. "
            f"Narrative generation encountered an error: {exc}"
        )

    log.info(
        "judge.narrative_generated",
        market_id=state.get("market_id"),
        length=len(narrative),
    )
    return {"llm_narrative": narrative}


async def node_build_trace(state: JudgementState, attestation_contract: str) -> dict:
    """Assemble the full ReasoningTrace and compute its SHA-256 hash."""
    trace, trace_hash = build_trace(
        market_id=state["market_id"],
        market_question=state["market_question"],
        resolution_date=state["resolution_date"],
        evidences=state.get("filtered_evidences") or [],
        probability_result=state["probability_result"],
        llm_narrative=state["llm_narrative"],
        current_market_price=state["current_market_price"],
        attestation_contract=attestation_contract,
    )
    log.info(
        "judge.trace_built",
        market_id=state["market_id"],
        hash_prefix=trace_hash.hex()[:12],
    )
    return {"trace": trace, "trace_hash": trace_hash}


async def node_publish_ipfs(state: JudgementState, private_key: str) -> dict:
    """Serialise and upload the trace to Irys/IPFS."""
    from dataclasses import asdict as _asdict
    import json as _json

    trace = state["trace"]
    trace_dict = _asdict(trace)
    trace_json = _json.dumps(trace_dict, sort_keys=True, default=str)

    cid = await upload_to_irys(trace_json, private_key)
    log.info("judge.ipfs_published", market_id=state["market_id"], cid=cid)
    return {"ipfs_cid": cid}


async def node_commit_arc(
    state: JudgementState,
    arc_client,
    vault_address: str,
    confidence_threshold: float,
) -> dict:
    """
    Commit the attestation to the Arc Testnet AttestationVault.

    Skips the on-chain call if confidence is below the configured threshold
    to avoid wasting gas on uncertain judgements.
    """
    result = state["probability_result"]
    trace = state["trace"]
    trace_hash = state["trace_hash"]
    ipfs_cid = state["ipfs_cid"]

    final_prob = result.final_probability
    ci_lo, ci_hi = result.confidence_interval
    # Derive confidence from the width of the credible interval.
    interval_width = ci_hi - ci_lo
    confidence = max(0.0, min(1.0, 1.0 - interval_width))
    confidence_int = int(confidence * 100)

    if confidence < confidence_threshold:
        log.warning(
            "judge.attestation_skipped_low_confidence",
            market_id=state["market_id"],
            confidence=round(confidence, 4),
            threshold=confidence_threshold,
        )
        return {"arc_attestation": {"skipped": True, "reason": "low_confidence", "confidence": confidence}}

    probability_bps = int(final_prob * 10_000)

    recommendation = trace.recommendation

    # Pad or truncate trace_hash to exactly 32 bytes for bytes32 parameter.
    hash_bytes32 = (trace_hash + b"\x00" * 32)[:32]

    try:
        tx_hash = await arc_client.call_contract_write(
            vault_address,
            _ATTESTATION_VAULT_ABI,
            "commitAttestation",
            [
                state["market_id"],
                hash_bytes32,
                ipfs_cid,
                probability_bps,
                confidence_int,
                recommendation,
            ],
        )

        receipt = await arc_client.wait_for_receipt(tx_hash)
        arc_scan_url = arc_client.arc_scan_url(tx_hash)

        attestation_result = {
            "tx_hash": tx_hash,
            "block_number": receipt.get("blockNumber"),
            "arc_scan_url": arc_scan_url,
            "probability_bps": probability_bps,
            "confidence": confidence,
            "recommendation": recommendation,
            "ipfs_cid": ipfs_cid,
            "trace_hash": trace_hash.hex(),
        }

        log.info(
            "judge.arc_attestation_committed",
            market_id=state["market_id"],
            tx_hash=tx_hash,
            arc_scan_url=arc_scan_url,
            recommendation=recommendation,
            probability=round(final_prob, 4),
        )
        return {"arc_attestation": attestation_result}

    except Exception as exc:  # noqa: BLE001
        log.error(
            "judge.arc_attestation_failed",
            market_id=state["market_id"],
            error=str(exc),
        )
        return {
            "arc_attestation": {
                "tx_hash": "",
                "error": str(exc),
                "probability_bps": probability_bps,
                "confidence": confidence,
                "recommendation": recommendation,
                "ipfs_cid": ipfs_cid,
            }
        }


async def node_handle_error(state: JudgementState) -> dict:
    """Log the error and return state unchanged — pipeline terminates cleanly."""
    log.error(
        "judge.pipeline_error",
        market_id=state.get("market_id"),
        error=state.get("error"),
    )
    return {}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def _build_graph(
    arc_client,
    vault_address: str,
    anthropic_api_key: str,
    private_key: str,
    confidence_threshold: float,
) -> Any:
    """Compile the LangGraph state machine with all nodes and edges."""

    async def _validate(state: JudgementState) -> dict:
        return await node_validate_evidence(state)

    async def _compute(state: JudgementState) -> dict:
        return await node_compute_probability(state)

    async def _narrative(state: JudgementState) -> dict:
        return await node_generate_narrative(state, anthropic_api_key=anthropic_api_key)

    async def _build_tr(state: JudgementState) -> dict:
        return await node_build_trace(state, attestation_contract=vault_address)

    async def _publish(state: JudgementState) -> dict:
        return await node_publish_ipfs(state, private_key=private_key)

    async def _commit(state: JudgementState) -> dict:
        return await node_commit_arc(
            state,
            arc_client=arc_client,
            vault_address=vault_address,
            confidence_threshold=confidence_threshold,
        )

    async def _error(state: JudgementState) -> dict:
        return await node_handle_error(state)

    def _after_validate(state: JudgementState) -> str:
        if not state.get("filtered_evidences"):
            return END
        return "compute_probability"

    builder = StateGraph(JudgementState)
    builder.add_node("validate_evidence", _validate)
    builder.add_node("compute_probability", _compute)
    builder.add_node("generate_narrative", _narrative)
    builder.add_node("build_trace", _build_tr)
    builder.add_node("publish_ipfs", _publish)
    builder.add_node("commit_arc", _commit)
    builder.add_node("handle_error", _error)

    builder.set_entry_point("validate_evidence")
    builder.add_conditional_edges("validate_evidence", _after_validate)
    builder.add_edge("compute_probability", "generate_narrative")
    builder.add_edge("generate_narrative", "build_trace")
    builder.add_edge("build_trace", "publish_ipfs")
    builder.add_edge("publish_ipfs", "commit_arc")
    builder.add_edge("commit_arc", END)
    builder.add_edge("handle_error", END)

    return builder.compile()


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


class JudgeAgent:
    """
    High-level Oracle Sentinel Judge orchestrator.

    Wraps the compiled LangGraph and exposes a single ``judge_market`` coroutine.
    """

    def __init__(
        self,
        arc_client,
        vault_address: str,
        anthropic_api_key: str,
        settings,
    ) -> None:
        self._arc_client = arc_client
        self._vault_address = vault_address
        self._anthropic_api_key = anthropic_api_key
        self._settings = settings

        self._graph = _build_graph(
            arc_client=arc_client,
            vault_address=vault_address,
            anthropic_api_key=anthropic_api_key,
            private_key=getattr(settings, "deployer_private_key", ""),
            confidence_threshold=getattr(settings, "judge_confidence_threshold", 0.65),
        )

    async def judge_market(
        self,
        market_id: str,
        market_question: str,
        resolution_date: str,
        current_price: float,
        evidences: list,
    ) -> JudgementState:
        """
        Run the full judgement pipeline for one market.

        Args:
            market_id: Polymarket condition ID.
            market_question: The resolution question text.
            resolution_date: ISO-8601 resolution deadline.
            current_price: Live Polymarket YES price (0–1).
            evidences: List of Evidence instances from all scouts.

        Returns:
            Final JudgementState after all pipeline nodes have executed.
        """
        initial_state: JudgementState = {
            "market_id": market_id,
            "market_question": market_question,
            "resolution_date": str(resolution_date),
            "current_market_price": float(current_price),
            "scout_evidences": list(evidences),
            "filtered_evidences": [],
            "probability_result": None,
            "llm_narrative": "",
            "trace": None,
            "trace_hash": None,
            "ipfs_cid": "",
            "arc_attestation": None,
            "error": None,
        }

        log.info(
            "judge.pipeline_start",
            market_id=market_id,
            n_evidences=len(evidences),
            current_price=round(current_price, 4),
        )

        try:
            final_state: JudgementState = await self._graph.ainvoke(initial_state)
        except Exception as exc:  # noqa: BLE001
            log.error("judge.pipeline_exception", market_id=market_id, error=str(exc))
            initial_state["error"] = str(exc)
            return initial_state

        log.info(
            "judge.pipeline_complete",
            market_id=market_id,
            recommendation=final_state.get("trace") and final_state["trace"].recommendation,
            ipfs_cid=final_state.get("ipfs_cid", ""),
            arc_tx=final_state.get("arc_attestation", {}) and final_state["arc_attestation"].get("tx_hash", ""),
        )
        return final_state


async def run_judgement(
    market_id: str,
    market_question: str,
    resolution_date: str,
    current_price: float,
    evidences: list,
    arc_client,
    vault_address: str,
    anthropic_api_key: str,
    settings,
) -> JudgementState:
    """
    Convenience coroutine — creates a JudgeAgent and runs one judgement.

    Useful for one-off calls without maintaining a JudgeAgent instance.
    """
    agent = JudgeAgent(
        arc_client=arc_client,
        vault_address=vault_address,
        anthropic_api_key=anthropic_api_key,
        settings=settings,
    )
    return await agent.judge_market(
        market_id=market_id,
        market_question=market_question,
        resolution_date=resolution_date,
        current_price=current_price,
        evidences=evidences,
    )
