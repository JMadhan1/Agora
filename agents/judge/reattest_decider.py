"""
Re-attestation Decider — LLM decides if new evidence warrants another Arc commit.

Each Arc attestation costs real USDC in gas (~$0.01). Running the Judge
on every market every cycle wastes money and pollutes the chain with duplicate
records. This module makes the Judge COST-AWARE and AUTONOMOUS:

  "Is this new evidence materially different from our last attestation?"
  If yes → commit. If no → skip.

This is a key "full autonomy" signal for the hackathon judges:
the AI is making explicit tradeoff decisions, not just executing a schedule.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import structlog

log = structlog.get_logger(__name__)


@dataclass
class ReattestDecision:
    should_reattest: bool
    reason: str
    significance_score: float  # 0-1, how significant the new evidence is
    probability_shift: float  # Expected change in probability estimate
    cost_justified: bool


class ReattestDecider:
    """
    LLM-powered decision: is this new batch of scout evidence significant
    enough to justify the gas cost of a new on-chain attestation?
    """

    def __init__(self, groq_api_key: str, gas_cost_usd: float = 0.01) -> None:
        self.groq_api_key = groq_api_key
        self.gas_cost_usd = gas_cost_usd

    async def decide(
        self,
        market_id: str,
        market_question: str,
        last_attestation: dict | None,
        new_evidences: list,
    ) -> ReattestDecision:
        """
        Decide whether new evidence warrants re-attesting.

        Args:
            market_id: Market identifier
            market_question: The question text
            last_attestation: Previous attestation record (probability, timestamp, confidence)
            new_evidences: New Evidence objects from scouts
        """
        # If no previous attestation, always attest
        if not last_attestation:
            return ReattestDecision(
                should_reattest=True,
                reason="No prior attestation — first-time judgement required.",
                significance_score=1.0,
                probability_shift=0.5,
                cost_justified=True,
            )

        last_prob = last_attestation.get("probability_estimate", 0.5)
        last_confidence = last_attestation.get("confidence", 0)
        hours_since = last_attestation.get("hours_since", 99)

        # Quick rule: if last attestation was <1 hour ago and confidence is high, skip
        if hours_since < 1 and last_confidence > 85:
            return ReattestDecision(
                should_reattest=False,
                reason=f"Recent high-confidence attestation ({last_confidence}% conf, {hours_since:.1f}h ago). Skipping to conserve gas.",
                significance_score=0.1,
                probability_shift=0.0,
                cost_justified=False,
            )

        # Build evidence summary for LLM
        evidence_summary = []
        for ev in new_evidences[:8]:
            scout_type = getattr(ev, "scout_type", "unknown")
            facts = getattr(ev, "extracted_facts", [])[:2]
            p_yes = getattr(ev, "supports_yes_probability", 0.5)
            confidence = getattr(ev, "confidence", 0.5)
            evidence_summary.append({
                "scout": scout_type,
                "p_yes": round(p_yes, 3),
                "confidence": round(confidence, 3),
                "key_facts": facts,
            })

        prompt = f"""You are the Judge intelligence system for Oracle Sentinel. Each on-chain attestation costs ${self.gas_cost_usd} in gas. You must decide if new scout evidence is significantly different from our previous attestation.

MARKET: {market_question}

PREVIOUS ATTESTATION:
- Probability estimate: {last_prob:.1%} YES
- Confidence: {last_confidence}%
- Hours ago: {hours_since:.1f}h

NEW SCOUT EVIDENCE:
{json.dumps(evidence_summary, indent=2)}

DECISION CRITERIA - Re-attest if:
1. New evidence shifts probability estimate by >10 percentage points
2. Evidence reveals manipulation signals (coordinated activity, fake news)
3. Major new factual development (event happened, announcement made)
4. More than 24 hours since last attestation (mandatory refresh)
5. Our confidence was low (<60%) and new evidence is high-quality

Skip if:
1. Evidence is redundant (same facts as before)
2. Probability shift would be <5%
3. All evidence is low-confidence or from unreliable sources

Respond with EXACTLY this JSON:
{{
  "should_reattest": true | false,
  "reason": "1-2 sentence explanation",
  "significance_score": 0.0-1.0,
  "probability_shift": 0.0-1.0,
  "cost_justified": true | false
}}"""

        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=self.groq_api_key)
            resp = await client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=256,
            )
            content = resp.choices[0].message.content.strip()

            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(content[start:end])
            else:
                raise ValueError("No JSON found")

            result = ReattestDecision(
                should_reattest=bool(parsed.get("should_reattest", True)),
                reason=parsed.get("reason", ""),
                significance_score=float(parsed.get("significance_score", 0.5)),
                probability_shift=float(parsed.get("probability_shift", 0.0)),
                cost_justified=bool(parsed.get("cost_justified", True)),
            )

            log.info(
                "reattest_decider.decision",
                market_id=market_id,
                should_reattest=result.should_reattest,
                significance=result.significance_score,
            )
            return result

        except Exception as exc:
            log.warning("reattest_decider.llm_failed", market_id=market_id, error=str(exc))
            # Fallback: attest if >6h since last or no previous
            should = hours_since > 6
            return ReattestDecision(
                should_reattest=should,
                reason=f"LLM unavailable. Fallback: {'Reattest' if should else 'Skip'} ({hours_since:.1f}h since last).",
                significance_score=0.5,
                probability_shift=0.1,
                cost_justified=should,
            )
