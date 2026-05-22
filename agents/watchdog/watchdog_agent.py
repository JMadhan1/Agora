"""Watchdog agent — monitors for UMA manipulation and triggers disputes."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import TYPE_CHECKING
import httpx
import structlog

from .deviation_detector import DeviationDetector, DeviationResult
from .dispute_trigger import DisputeTrigger
from .dispute_reasoner import DisputeReasoner

if TYPE_CHECKING:
    from arc.arc_client import ArcClient

log = structlog.get_logger()

ATTESTATION_VAULT_ABI = [
    {
        "inputs": [
            {"name": "marketId", "type": "string"},
            {"name": "traceHash", "type": "bytes32"},
            {"name": "reason", "type": "string"},
        ],
        "name": "flagDispute",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    }
]


class WatchdogAgent:
    """
    Continuously monitors active Polymarket markets.
    When proposed UMA resolution deviates >40% from Sentinel estimate → triggers dispute.
    """

    def __init__(self, arc_client: "ArcClient", settings, db_session=None):
        self.arc_client = arc_client
        self.settings = settings
        self.db_session = db_session
        self.deviation_detector = DeviationDetector(
            threshold=settings.dispute_deviation_threshold,
            min_confidence=settings.judge_confidence_threshold,
        )
        self.dispute_trigger = DisputeTrigger(
            polygon_rpc_url="https://polygon-rpc.com",
            private_key=settings.deployer_private_key,
        )
        self.dispute_reasoner = DisputeReasoner(
            groq_api_key=getattr(settings, "groq_api_key", "") or "",
        )
        # market_id → { our_estimate, our_confidence, latest_trace_hash }
        self.monitored_markets: dict[str, dict] = {}
        self._http = httpx.AsyncClient(timeout=20.0)

    def update_market_estimate(
        self,
        market_id: str,
        estimate: float,
        confidence: float,
        trace_hash: str,
    ) -> None:
        """Called by JudgeAgent after each attestation to keep watchdog current."""
        self.monitored_markets[market_id] = {
            "our_estimate": estimate,
            "our_confidence": confidence,
            "latest_trace_hash": trace_hash,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    async def check_polymarket_resolution(self, market_id: str) -> dict | None:
        """Returns resolution dict if market is resolved on Polymarket, else None."""
        try:
            url = f"{self.settings.polymarket_gamma_api}/markets/{market_id}"
            resp = await self._http.get(url)
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            data = resp.json()
            if data.get("resolved") or data.get("resolution"):
                resolution_outcome = data.get("resolution") or data.get("outcome", "")
                return {
                    "market_id": market_id,
                    "resolution": resolution_outcome.upper(),
                    "resolved_at": data.get("resolutionTime", ""),
                }
        except Exception as e:
            log.debug("polymarket_resolution_check_failed", market_id=market_id, error=str(e))
        return None

    async def _flag_on_arc(self, market_id: str, trace_hash_hex: str, reason: str) -> str | None:
        """Commits a dispute flag to AttestationVault on Arc Testnet."""
        if not self.settings.attestation_vault_address:
            return None
        try:
            trace_bytes = bytes.fromhex(trace_hash_hex.lstrip("0x"))
            if len(trace_bytes) < 32:
                trace_bytes = trace_bytes.ljust(32, b"\x00")
            tx_hash = await self.arc_client.call_contract_write(
                self.settings.attestation_vault_address,
                ATTESTATION_VAULT_ABI,
                "flagDispute",
                [market_id, trace_bytes[:32], reason],
            )
            log.info("arc_dispute_flagged", market_id=market_id, tx_hash=tx_hash)
            return tx_hash
        except Exception as e:
            log.error("arc_flag_failed", market_id=market_id, error=str(e))
            return None

    async def scan_for_manipulation(self) -> list[dict]:
        """
        Checks all monitored markets for resolved/proposed outcomes that deviate
        from Sentinel's estimate. Returns list of alerts triggered.
        """
        alerts = []
        market_ids = list(self.monitored_markets.keys())

        for market_id in market_ids:
            try:
                market_data = self.monitored_markets[market_id]
                resolution = await self.check_polymarket_resolution(market_id)
                if not resolution:
                    continue

                deviation_result = self.deviation_detector.check_deviation(
                    our_estimate=market_data["our_estimate"],
                    proposed_resolution=resolution["resolution"],
                    market_price=market_data["our_estimate"],
                    our_confidence=market_data["our_confidence"],
                )

                alert = {
                    "market_id": market_id,
                    "proposed_resolution": resolution["resolution"],
                    "our_estimate": market_data["our_estimate"],
                    "deviation": deviation_result.deviation,
                    "manipulation_suspected": deviation_result.manipulation_suspected,
                    "dispute_triggered": False,
                    "dispute_tx_hash": None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                if deviation_result.manipulation_suspected:
                    log.warning(
                        "manipulation_detected",
                        market_id=market_id,
                        deviation=f"{deviation_result.deviation:.1%}",
                        our_estimate=market_data["our_estimate"],
                        proposed=resolution["resolution"],
                    )

                    # ── LLM Autonomy: Reason before posting $50 bond ──────
                    llm_reasoning = await self.dispute_reasoner.reason(
                        market_id=market_id,
                        market_question=market_data.get("question", market_id),
                        proposed_resolution=resolution["resolution"],
                        our_estimate=market_data["our_estimate"],
                        deviation=deviation_result.deviation,
                    )
                    alert["dispute_reasoning"] = llm_reasoning.reasoning
                    alert["dispute_type"] = llm_reasoning.deviation_type

                    if llm_reasoning.decision != "DISPUTE":
                        log.info(
                            "dispute_held_by_llm",
                            market_id=market_id,
                            decision=llm_reasoning.decision,
                            deviation_type=llm_reasoning.deviation_type,
                            reason=llm_reasoning.reasoning,
                        )
                        continue  # LLM decided not to dispute
                    # ── End LLM gate ──────────────────────────────────────

                    reason = (
                        f"[{llm_reasoning.deviation_type}] "
                        f"Deviation {deviation_result.deviation:.1%}: "
                        f"Sentinel={market_data['our_estimate']:.1%} vs UMA={resolution['resolution']}. "
                        f"{llm_reasoning.reasoning}"
                    )
                    trace_hash = market_data.get("latest_trace_hash", "")
                    if trace_hash:
                        arc_tx = await self._flag_on_arc(market_id, trace_hash, reason)
                        if arc_tx:
                            alert["arc_flag_tx"] = arc_tx

                    alert["dispute_triggered"] = True

                    # Save to DB if session available
                    if self.db_session:
                        try:
                            from storage.database import save_dispute_alert
                            save_dispute_alert(self.db_session, alert)
                        except Exception as e:
                            log.warning("db_save_alert_failed", error=str(e))

                    alerts.append(alert)

            except Exception as e:
                log.error("scan_market_failed", market_id=market_id, error=str(e))

        return alerts

    async def run_forever(self) -> None:
        """Main watchdog loop — scans every 30 seconds for manipulation."""
        while True:
            try:
                alerts = await self.scan_for_manipulation()
                if alerts:
                    log.info("watchdog_alerts_fired", count=len(alerts))
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("watchdog_loop_error", error=str(e))
            await asyncio.sleep(30)

    async def close(self) -> None:
        await self._http.aclose()
