"""
Oracle Sentinel — Main Agent Orchestrator
Runs Scout, Judge, and Watchdog agents in an async event loop.
"""
from __future__ import annotations
import asyncio
import signal
import sys
import json
from pathlib import Path
from datetime import datetime

import structlog

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live

# Add agents dir to path
sys.path.insert(0, str(Path(__file__).parent))

from config import settings, load_abi
from storage.database import init_db, get_db
from storage.database import upsert_market, save_attestation, get_markets
from arc.arc_client import ArcClient
from arc.attestation import commit_attestation
from arc.wallet_manager import load_or_create_wallets
from arc.bond_manager import AgentBondManager
from scout import NewsScout, OnchainScout, WaybackScout, MarketDataScout, SocialScout
from scout.market_prioritizer import MarketPrioritizer
from judge.judge_agent import JudgeAgent
from judge.reattest_decider import ReattestDecider
from watchdog.watchdog_agent import WatchdogAgent
from treasurer.treasurer_agent import TreasurerAgent
from polymarket.market_fetcher import MarketFetcher
from polymarket.resolution_monitor import ResolutionMonitor
from judge.calibration_tracker import record_market_outcome

log = structlog.get_logger()
console = Console()

# =========================================================================
# Startup Banner
# =========================================================================

BANNER = """
[bold cyan]
 ██████╗ ██████╗  █████╗  ██████╗██╗     ███████╗
██╔═══██╗██╔══██╗██╔══██╗██╔════╝██║     ██╔════╝
██║   ██║██████╔╝███████║██║     ██║     █████╗
██║   ██║██╔══██╗██╔══██║██║     ██║     ██╔══╝
╚██████╔╝██║  ██║██║  ██║╚██████╗███████╗███████╗
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝╚══════╝

███████╗███████╗███╗   ██╗████████╗██╗███╗   ██╗███████╗██╗
██╔════╝██╔════╝████╗  ██║╚══██╔══╝██║████╗  ██║██╔════╝██║
███████╗█████╗  ██╔██╗ ██║   ██║   ██║██╔██╗ ██║█████╗  ██║
╚════██║██╔══╝  ██║╚██╗██║   ██║   ██║██║╚██╗██║██╔══╝  ██║
███████║███████╗██║ ╚████║   ██║   ██║██║ ╚████║███████╗███████╗
╚══════╝╚══════╝╚═╝  ╚═══╝   ╚═╝   ╚═╝╚═╝  ╚═══╝╚══════╝╚══════╝
[/bold cyan]
[dim]Autonomous AI Truth Verification Network — Arc Testnet[/dim]
[dim]Agora Hackathon 2026 | Canteen × Circle × Arc[/dim]
"""


# =========================================================================
# Agent System
# =========================================================================

class OracleSentinelSystem:
    """Top-level orchestrator for all Oracle Sentinel agents."""

    def __init__(self):
        self.arc_client: ArcClient | None = None
        self.judge_agent: JudgeAgent | None = None
        self.watchdog: WatchdogAgent | None = None
        self.treasurer: TreasurerAgent | None = None
        self.market_prioritizer: MarketPrioritizer | None = None
        self.reattest_decider: ReattestDecider | None = None
        self.market_fetcher = MarketFetcher(
            gamma_api=settings.polymarket_gamma_api,
            clob_api=settings.polymarket_clob_api,
        )
        self.resolution_monitor = ResolutionMonitor(
            gamma_api=settings.polymarket_gamma_api
        )
        self.scouts: list = []
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def startup(self) -> None:
        """Initialize all systems and verify connectivity."""
        console.print(BANNER)
        console.print(Panel.fit(
            "[bold]Starting Oracle Sentinel...[/bold]",
            border_style="cyan",
        ))

        # Initialize database
        init_db()
        log.info("database_initialized")

        # Validate config
        if not settings.deployer_private_key:
            console.print("[bold red]❌ DEPLOYER_PRIVATE_KEY not set in .env[/bold red]")
            sys.exit(1)
        if not settings.arc_rpc_key and not settings.arc_rpc_url:
            console.print("[bold red]❌ ARC_RPC_KEY not set in .env[/bold red]")
            sys.exit(1)

        # Initialize Arc client
        self.arc_client = ArcClient(
            rpc_url=settings.arc_rpc_url,
            private_key=settings.deployer_private_key,
        )
        try:
            await self.arc_client.verify_connection()
            console.print(f"[green]✅ Arc Testnet connected — chain {settings.arc_chain_id}[/green]")
        except Exception as e:
            console.print(f"[yellow]⚠️  Arc Testnet connection failed: {e}[/yellow]")
            console.print("[yellow]   Continuing in offline mode (no on-chain attestations)[/yellow]")

        # Check USDC balance
        try:
            usdc_bal = await self.arc_client.get_usdc_balance(self.arc_client.address)
            console.print(f"[cyan]💰 Deployer USDC balance: {usdc_bal:.2f} USDC[/cyan]")
            if usdc_bal < 1.0:
                console.print("[yellow]⚠️  Low USDC balance — attestations may fail[/yellow]")
        except Exception as e:
            log.warning("usdc_balance_check_failed", error=str(e))

        # Load or create Circle wallets
        try:
            if settings.circle_api_key:
                wallets = await load_or_create_wallets()
                console.print(f"[green]✅ Agent wallets loaded[/green]")
                console.print(f"   Scout:    {wallets.get('scout', {}).get('address', 'N/A')}")
                console.print(f"   Judge:    {wallets.get('judge', {}).get('address', 'N/A')}")
                console.print(f"   Watchdog: {wallets.get('watchdog', {}).get('address', 'N/A')}")
            else:
                console.print("[yellow]⚠️  CIRCLE_API_KEY not set — using deployer wallet for all agents[/yellow]")
        except Exception as e:
            log.warning("wallet_load_failed", error=str(e))

        # Ensure bond is posted
        if settings.bond_manager_address:
            try:
                bond_mgr = AgentBondManager()
                sufficient = await bond_mgr.ensure_bond_deposited(
                    self.arc_client, settings.bond_manager_address
                )
                if sufficient:
                    console.print("[green]✅ Agent bond verified[/green]")
                else:
                    console.print("[yellow]⚠️  Bond insufficient — reputation events disabled[/yellow]")
            except Exception as e:
                log.warning("bond_check_failed", error=str(e))

        # Initialize scouts
        self.scouts = [
            MarketDataScout(
                clob_api=settings.polymarket_clob_api,
                gamma_api=settings.polymarket_gamma_api,
            ),
            NewsScout(
                news_api_key=settings.news_api_key,
                groq_api_key=settings.groq_api_key,
            ),
            OnchainScout(groq_api_key=settings.groq_api_key),
            WaybackScout(groq_api_key=settings.groq_api_key),
            SocialScout(groq_api_key=settings.groq_api_key),
        ]
        console.print(f"[green]✅ {len(self.scouts)} scouts initialized[/green]")

        # Initialize Judge agent
        self.judge_agent = JudgeAgent(
            arc_client=self.arc_client,
            vault_address=settings.attestation_vault_address,
            anthropic_api_key=getattr(settings, "anthropic_api_key", "") or "",
            settings=settings,
        )
        console.print("[green]✅ Judge agent initialized (LangGraph + Bayesian)[/green]")

        # Initialize Watchdog
        with get_db() as session:
            self.watchdog = WatchdogAgent(
                arc_client=self.arc_client,
                settings=settings,
                db_session=session,
            )
        console.print("[green]✅ Watchdog agent initialized[/green]")

        # Initialize LLM decision modules (full autonomy)
        groq_key = getattr(settings, "groq_api_key", "") or ""
        self.market_prioritizer = MarketPrioritizer(
            groq_api_key=groq_key,
            max_markets=min(20, settings.max_markets_monitored),
        )
        self.reattest_decider = ReattestDecider(
            groq_api_key=groq_key,
            gas_cost_usd=0.01,
        )
        console.print("[green]✅ LLM decision modules initialized (Market Prioritizer + Re-attest Decider)[/green]")

        # Initialize Treasurer
        self.treasurer = TreasurerAgent(
            arc_client=self.arc_client,
            settings=settings,
            groq_api_key=groq_key,
        )
        console.print("[green]✅ Treasurer agent initialized (autonomous capital management)[/green]")

        # Print startup summary
        self._print_config_summary()

    def _print_config_summary(self) -> None:
        table = Table(title="Oracle Sentinel Configuration", border_style="cyan")
        table.add_column("Setting", style="bold")
        table.add_column("Value")

        table.add_row("Arc Chain ID", str(settings.arc_chain_id))
        table.add_row("Max Markets", str(settings.max_markets_monitored))
        table.add_row("Scout Interval", f"{settings.scout_interval_seconds}s")
        table.add_row("Dispute Threshold", f"{settings.dispute_deviation_threshold*100:.0f}%")
        table.add_row("Judge Confidence Min", f"{settings.judge_confidence_threshold*100:.0f}%")
        table.add_row("USYC Deploy Threshold", f"${settings.usyc_deploy_threshold_usdc:.2f}")
        table.add_row("AttestationVault", settings.attestation_vault_address or "NOT DEPLOYED")
        table.add_row("SentinelRegistry", settings.sentinel_registry_address or "NOT DEPLOYED")

        console.print(table)

    async def scout_and_judge_market(self, market: dict) -> None:
        """Run all scouts on a market, then judge + commit attestation.

        The ReattestDecider (LLM) decides whether new evidence is significant
        enough to justify the gas cost of a new on-chain attestation — full autonomy.
        """
        market_id = market["id"]
        question = market["question"]
        resolution_date_str = market.get("resolution_date", "")

        try:
            resolution_date = datetime.fromisoformat(resolution_date_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            resolution_date = datetime.utcnow().replace(year=datetime.utcnow().year + 1)

        current_price = float(market.get("current_yes_price", 0.5))

        log.info(
            "scouting_market",
            market_id=market_id,
            question=question[:60],
            current_price=current_price,
        )

        # Run all scouts in parallel
        scout_tasks = [
            scout.safe_fetch(market_id, question, resolution_date)
            for scout in self.scouts
        ]
        evidences = await asyncio.gather(*scout_tasks, return_exceptions=False)

        # Filter out exceptions
        valid_evidences = [e for e in evidences if e is not None and not isinstance(e, Exception)]

        if not valid_evidences:
            log.warning("no_evidence_gathered", market_id=market_id)
            return

        # ── LLM Autonomy: Decide whether to re-attest ────────────────────
        if self.reattest_decider:
            with get_db() as session:
                from storage.database import get_latest_attestation
                last_att = get_latest_attestation(session, market_id)

            last_att_dict = None
            if last_att:
                from datetime import timezone as tz
                last_ts = getattr(last_att, "timestamp", None)
                if last_ts:
                    try:
                        last_dt = datetime.fromisoformat(str(last_ts).replace("Z", "+00:00"))
                        hours_since = (datetime.now(tz.utc) - last_dt).total_seconds() / 3600
                    except Exception:
                        hours_since = 99
                else:
                    hours_since = 99
                last_att_dict = {
                    "probability_estimate": getattr(last_att, "probability_estimate", 0.5),
                    "confidence": getattr(last_att, "confidence", 0),
                    "hours_since": hours_since,
                }

            decision = await self.reattest_decider.decide(
                market_id=market_id,
                market_question=question,
                last_attestation=last_att_dict,
                new_evidences=valid_evidences,
            )
            if not decision.should_reattest:
                log.info(
                    "reattest_skipped",
                    market_id=market_id,
                    reason=decision.reason,
                    significance=decision.significance_score,
                )
                return
            log.info(
                "reattest_approved",
                market_id=market_id,
                reason=decision.reason,
                significance=decision.significance_score,
            )
        # ── End LLM autonomy gate ─────────────────────────────────────────

        # Judge
        result = await self.judge_agent.judge_market(
            market_id=market_id,
            market_question=question,
            resolution_date=resolution_date,
            current_price=current_price,
            evidences=valid_evidences,
        )

        if result.get("error"):
            log.error("judgement_failed", market_id=market_id, error=result["error"])
            return

        # Persist attestation to DB
        if result.get("arc_attestation"):
            att = result["arc_attestation"]
            with get_db() as session:
                save_attestation(session, {
                    "market_id": market_id,
                    "trace_hash": att.trace_hash,
                    "ipfs_cid": att.ipfs_cid,
                    "arc_tx_hash": att.tx_hash,
                    "arc_scan_url": att.arc_scan_url,
                    "arc_block_number": att.block_number,
                    "confidence": result.get("confidence", 0),
                    "recommendation": result.get("recommendation", "UNCERTAIN"),
                    "probability_estimate": result.get("probability", 0.5),
                })

        # Update watchdog
        if self.watchdog:
            self.watchdog.update_market_estimate(
                market_id=market_id,
                estimate=result.get("probability", 0.5),
                confidence=result.get("confidence", 0) / 100.0,
                trace_hash=result.get("trace_hash_hex", ""),
            )

        log.info(
            "market_judged",
            market_id=market_id,
            recommendation=result.get("recommendation"),
            probability=result.get("probability"),
            confidence=result.get("confidence"),
            ipfs_cid=result.get("ipfs_cid"),
        )

    async def scout_loop(self) -> None:
        """Main scouting loop — LLM prioritizes which markets to investigate.

        The MarketPrioritizer (LLM) reads all 200 markets and autonomously
        decides which 15-20 deserve investigation RIGHT NOW. This is the core
        "full autonomy" behavior: compute budget allocation via AI reasoning,
        not a fixed schedule.
        """
        console.print("[bold cyan]🔭 Scout loop started (LLM-prioritized)[/bold cyan]")

        while self._running:
            try:
                # Fetch all active markets
                markets = await self.market_fetcher.get_active_markets(
                    limit=settings.max_markets_monitored
                )
                log.info("markets_fetched", count=len(markets))

                # Persist markets to DB
                with get_db() as session:
                    for m in markets:
                        upsert_market(session, m)

                # ── LLM Autonomy: Prioritize which markets to scout ───────
                if self.market_prioritizer and len(markets) > 0:
                    prioritized = await self.market_prioritizer.prioritize(markets)
                    console.print(
                        f"[cyan]🧠 LLM prioritized {len(prioritized)}/{len(markets)} markets[/cyan]"
                    )
                else:
                    prioritized = markets[:20]
                # ── End LLM priority selection ────────────────────────────

                # Process prioritized markets in batches of 5
                batch_size = 5
                for i in range(0, len(prioritized), batch_size):
                    if not self._running:
                        break
                    batch = prioritized[i:i + batch_size]
                    await asyncio.gather(*[
                        self.scout_and_judge_market(m) for m in batch
                    ], return_exceptions=True)
                    await asyncio.sleep(5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("scout_loop_error", error=str(e))

            await asyncio.sleep(settings.scout_interval_seconds)

    async def resolution_check_loop(self) -> None:
        """Checks for newly resolved markets and records calibration."""
        console.print("[bold cyan]📊 Resolution monitor started[/bold cyan]")

        while self._running:
            try:
                with get_db() as session:
                    # Get markets we're monitoring that aren't resolved yet
                    unresolved = get_markets(session, resolved=False, limit=200)
                    market_ids = [m.id for m in unresolved]

                if market_ids:
                    newly_resolved = await self.resolution_monitor.get_newly_resolved(market_ids)
                    for resolution in newly_resolved:
                        with get_db() as session:
                            record_market_outcome(
                                session,
                                market_id=resolution["market_id"],
                                actual_resolution=resolution["resolution"],
                            )
                            # Mark market as resolved
                            upsert_market(session, {
                                "id": resolution["market_id"],
                                "resolved": True,
                                "actual_resolution": resolution["resolution"],
                            })
                        log.info(
                            "market_resolved",
                            market_id=resolution["market_id"],
                            resolution=resolution["resolution"],
                        )

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("resolution_check_error", error=str(e))

            await asyncio.sleep(60)  # Check every minute

    async def watchdog_loop(self) -> None:
        """Runs watchdog manipulation detection."""
        console.print("[bold cyan]🐕 Watchdog started[/bold cyan]")
        if self.watchdog:
            await self.watchdog.run_forever()

    async def treasurer_loop(self) -> None:
        """Autonomous Treasurer — LLM manages capital allocation every 5 minutes.

        Replaces the simple USYC timer with genuine autonomous decision-making:
        the Treasurer reasons about the full treasury state (balances, bonds,
        insurance float) before deciding what actions to take.
        """
        console.print("[bold cyan]💰 Autonomous Treasurer started[/bold cyan]")
        if self.treasurer:
            await self.treasurer.run_forever()

    async def run(self) -> None:
        """Start all agent loops."""
        await self.startup()
        self._running = True

        # Register signal handlers for graceful shutdown (Unix only)
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self.shutdown)
            except (NotImplementedError, OSError):
                signal.signal(sig, lambda s, f: self.shutdown())

        console.print("\n[bold green]🚀 Oracle Sentinel is running![/bold green]")
        console.print("[dim]Press Ctrl+C to stop[/dim]\n")

        # Launch all loops
        self._tasks = [
            asyncio.create_task(self.scout_loop(), name="scout"),
            asyncio.create_task(self.resolution_check_loop(), name="resolution"),
            asyncio.create_task(self.watchdog_loop(), name="watchdog"),
            asyncio.create_task(self.treasurer_loop(), name="treasurer"),
        ]

        try:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        except asyncio.CancelledError:
            pass

    def shutdown(self) -> None:
        """Gracefully stop all agents."""
        console.print("\n[yellow]⚡ Shutting down Oracle Sentinel...[/yellow]")
        self._running = False
        for task in self._tasks:
            task.cancel()


# =========================================================================
# Entry Point
# =========================================================================

async def main() -> None:
    system = OracleSentinelSystem()
    await system.run()


if __name__ == "__main__":
    asyncio.run(main())
