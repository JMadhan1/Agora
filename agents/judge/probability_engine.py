"""
Bayesian probability engine for Oracle Sentinel Judge agent.

Sequentially updates a prior probability using evidence from scout agents.
Each evidence piece is weighted by the scout's reliability score and its
own confidence level. Uses scipy Beta distribution for 95% credible intervals.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import structlog
from scipy.stats import beta as beta_dist

log = structlog.get_logger(__name__)

_PROB_MIN = 0.01
_PROB_MAX = 0.99
_PRIOR_DEFAULT = 0.5
_MIN_CONFIDENCE = 0.1


@dataclass
class BayesianUpdate:
    """Single Bayesian update step recorded for audit purposes."""

    prior: float
    likelihood_yes: float
    likelihood_no: float
    posterior: float
    scout_type: str
    reliability_weight: float


@dataclass
class ProbabilityResult:
    """Aggregated result of the full Bayesian inference pass."""

    final_probability: float
    confidence_interval: tuple[float, float]
    num_evidence_pieces: int
    bayesian_log: list[BayesianUpdate] = field(default_factory=list)
    brier_score_prediction: float = 0.0


def _clamp(value: float, lo: float = _PROB_MIN, hi: float = _PROB_MAX) -> float:
    return max(lo, min(hi, value))


def bayesian_update(
    prior: float,
    evidence_supports_yes: float,
    reliability: float,
) -> float:
    """
    Apply a single Bayesian update to *prior* given one piece of evidence.

    P(YES|E) = P(E|YES)*P(YES) / [P(E|YES)*P(YES) + P(E|NO)*P(NO)]

    The effective likelihoods are blended with the uninformative 0.5 baseline
    according to the scout's reliability so that unreliable scouts have
    attenuated influence on the posterior.

    Args:
        prior: Current probability estimate in (0, 1).
        evidence_supports_yes: Fraction 0–1 indicating how strongly the
            evidence supports the YES resolution.
        reliability: Scout reliability weight in [0, 1].

    Returns:
        Updated probability clamped to [0.01, 0.99].
    """
    reliability = _clamp(reliability, 0.0, 1.0)
    evidence_supports_yes = _clamp(evidence_supports_yes, 0.0, 1.0)
    prior = _clamp(prior)

    # Blend the raw signal with the 0.5 baseline proportionally to reliability.
    p_e_given_yes = reliability * evidence_supports_yes + (1.0 - reliability) * 0.5
    p_e_given_no = reliability * (1.0 - evidence_supports_yes) + (1.0 - reliability) * 0.5

    prior_no = 1.0 - prior
    numerator = p_e_given_yes * prior
    denominator = numerator + p_e_given_no * prior_no

    if denominator < 1e-15:
        log.warning(
            "bayesian_update.zero_denominator",
            prior=prior,
            p_e_yes=p_e_given_yes,
            p_e_no=p_e_given_no,
        )
        return prior

    posterior = numerator / denominator
    return _clamp(posterior)


def compute_posterior(
    prior: float,
    evidences: list[Any],
) -> ProbabilityResult:
    """
    Sequentially apply Bayesian updates for all evidences above the
    minimum confidence threshold.

    The Beta distribution parameters are inferred from the final probability
    and the number of effective evidence pieces to produce a 95% credible
    interval. The Brier score prediction is computed against the final
    estimate as a self-referential sanity metric (will be re-evaluated once
    actual resolution is known via the calibration tracker).

    Args:
        prior: Starting probability (typically the current Polymarket price).
        evidences: List of Evidence dataclass instances from scout agents.

    Returns:
        ProbabilityResult with full Bayesian audit log.
    """
    current_p = _clamp(prior if prior and not math.isnan(prior) else _PRIOR_DEFAULT)

    accepted: list[Any] = []
    for ev in evidences:
        confidence = getattr(ev, "confidence", 0.0)
        if confidence < _MIN_CONFIDENCE:
            log.debug(
                "probability_engine.evidence_skipped",
                scout_type=getattr(ev, "scout_type", "unknown"),
                confidence=confidence,
            )
            continue
        accepted.append(ev)

    bayesian_log: list[BayesianUpdate] = []

    for ev in accepted:
        p_yes = getattr(ev, "supports_yes_probability", 0.5)
        reliability = getattr(ev, "reliability_weight", 0.5)
        scout_type = getattr(ev, "scout_type", "unknown")

        p_e_yes = reliability * p_yes + (1.0 - reliability) * 0.5
        p_e_no = reliability * (1.0 - p_yes) + (1.0 - reliability) * 0.5

        posterior = bayesian_update(current_p, p_yes, reliability)

        bayesian_log.append(
            BayesianUpdate(
                prior=current_p,
                likelihood_yes=p_e_yes,
                likelihood_no=p_e_no,
                posterior=posterior,
                scout_type=scout_type,
                reliability_weight=reliability,
            )
        )

        log.debug(
            "probability_engine.update",
            scout=scout_type,
            prior=round(current_p, 4),
            p_yes=round(p_yes, 4),
            reliability=round(reliability, 4),
            posterior=round(posterior, 4),
        )

        current_p = posterior

    # Build 95% credible interval using Beta distribution.
    # Effective sample size scales with evidence count.
    n_eff = max(1.0, float(len(accepted)) * 2.0)
    alpha_param = current_p * n_eff
    beta_param = (1.0 - current_p) * n_eff
    alpha_param = max(alpha_param, 0.5)
    beta_param = max(beta_param, 0.5)

    lo, hi = beta_dist.interval(0.95, alpha_param, beta_param)
    lo = float(_clamp(lo, 0.0, 1.0))
    hi = float(_clamp(hi, 0.0, 1.0))

    # Brier score prediction: will be near 0 for high-confidence, 0.25 for 50/50.
    brier_prediction = current_p * (1.0 - current_p)

    log.info(
        "probability_engine.final",
        prior=round(prior, 4),
        posterior=round(current_p, 4),
        ci_lo=round(lo, 4),
        ci_hi=round(hi, 4),
        n_accepted=len(accepted),
        n_total=len(evidences),
    )

    return ProbabilityResult(
        final_probability=current_p,
        confidence_interval=(lo, hi),
        num_evidence_pieces=len(accepted),
        bayesian_log=bayesian_log,
        brier_score_prediction=brier_prediction,
    )
