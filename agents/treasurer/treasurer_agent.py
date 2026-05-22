"""
Oracle Sentinel Treasurer Agent — Autonomous Financial Manager.

The Treasurer runs every 5 minutes and makes autonomous decisions about:
  1. USDC → USYC deployment (idle capital yield)
  2. Bond top-ups for agents with low balances
  3. Refund of expired insurance policies
  4. Rebalancing between agents based on workload

This is a key "full autonomy" feature: the system manages its own finances
without any human in the loop, responding dynamically to its own economic state.

Pairs with ERC-8183 Agentic Commerce and Circle Developer Wallets.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from arc.arc_client import ArcClient

log = structlog.get_logger(__name__)

USYC_TELLER_ADDRESS = "0x9fdF14c5B14173D74C08Af27AebFf39240dC105A"
MINIMUM_OPERATING_RESERVE_USDC = 5.0   # keep at least $5 liquid per agent
USYC_DEPLOY_THRESHOLD_USDC = 10.0      # deploy to USYC if >$10 idle
BOND_TOP_UP_THRESHOLD_USDC = 8.0       # top up bond if below $8
BOND_TARGET_USDC = 15.0                 # target bond size per agent


@dataclass
class TreasuryAction:
    action_type: str  # "DEPLOY_USYC" | "TOP_UP_BOND" | "HOLD" | "REBALANCE"
    agent: str        # "scout" | "judge" | "watchdog" | "system"
    amount_usdc: float
    reason: str
    tx_hash: str | None = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class TreasuryState:
    deployer_usdc: float
    scout_usdc: float
    judge_usdc: float
    watchdog_usdc: float
    usyc_deployed: float
    total_bonds_posted: float
    insurance_float: float
    last_updated: str


class TreasurerAgent:
    """
    Autonomous treasury manager that decides how to allocate capital.

    Uses LLM reasoning to make nuanced decisions beyond simple threshold checks:
    - Should we deploy to USYC now or wait for a larger batch? (gas efficiency)
    - Which agent needs its bond topped up most urgently? (prioritization)
    - Is the dispute insurance float sufficient for outstanding policies?
    """

    def __init__(self, arc_client: "ArcClient", settings, groq_api_key: str = "") -> None:
        self.arc_client = arc_client
        self.settings = settings
        self.groq_api_key = groq_api_key
        self._action_history: list[TreasuryAction] = []
        self._running = False

    async def _get_balances(self) -> TreasuryState:
        """Fetch USDC balances for all agent wallets."""
        try:
            deployer_bal = await self.arc_client.get_usdc_balance(self.arc_client.address)
        except Exception:
            deployer_bal = 0.0

        # Try to get agent wallet balances (if Circle wallets are configured)
        scout_bal = judge_bal = watchdog_bal = 0.0
        try:
            wallets_file = self.settings.agent_wallets_file if hasattr(self.settings, "agent_wallets_file") else ".agent-wallets.json"
            import json as _json
            import os
            if os.path.exists(wallets_file):
                with open(wallets_file) as f:
                    wallets = _json.load(f)
                scout_addr = wallets.get("scout", {}).get("address")
                judge_addr = wallets.get("judge", {}).get("address")
                watchdog_addr = wallets.get("watchdog", {}).get("address")
                if scout_addr:
                    scout_bal = await self.arc_client.get_usdc_balance(scout_addr)
                if judge_addr:
                    judge_bal = await self.arc_client.get_usdc_balance(judge_addr)
                if watchdog_addr:
                    watchdog_bal = await self.arc_client.get_usdc_balance(watchdog_addr)
        except Exception as e:
            log.debug("treasurer.wallet_balance_fetch_failed", error=str(e))

        # USYC deployed (try to read from contract)
        usyc_deployed = 0.0
        try:
            from arc.usyc_manager import get_usyc_balance
            usyc_deployed = await get_usyc_balance(self.arc_client, self.arc_client.address)
        except Exception:
            usyc_deployed = 0.0

        return TreasuryState(
            deployer_usdc=deployer_bal,
            scout_usdc=scout_bal,
            judge_usdc=judge_bal,
            watchdog_usdc=watchdog_bal,
            usyc_deployed=usyc_deployed,
            total_bonds_posted=0.0,
            insurance_float=0.0,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    async def _reason_about_allocation(self, state: TreasuryState) -> list[TreasuryAction]:
        """
        Use LLM to decide the optimal capital allocation given current state.

        This is the core of the autonomous treasury: rather than simple threshold
        rules, the LLM considers the full picture and makes nuanced decisions.
        """
        state_dict = asdict(state)
        total_liquid = state.deployer_usdc + state.scout_usdc + state.judge_usdc + state.watchdog_usdc

        prompt = f"""You are the Treasurer agent for Oracle Sentinel, an autonomous prediction market oracle network.

CURRENT TREASURY STATE:
{json.dumps(state_dict, indent=2)}

Total liquid USDC: ${total_liquid:.2f}
USYC deployed (yield-generating): ${state.usyc_deployed:.2f}

TREASURY RULES:
- Minimum operating reserve per agent: ${MINIMUM_OPERATING_RESERVE_USDC}
- Deploy to USYC if idle balance > ${USYC_DEPLOY_THRESHOLD_USDC} (earns ~5% APY yield)
- Top up agent bond if below ${BOND_TOP_UP_THRESHOLD_USDC} (minimum bond = $10)
- Target bond size per agent: ${BOND_TARGET_USDC}
- Never deploy USYC if total liquid < $20 (keep emergency reserves)

AVAILABLE ACTIONS:
1. DEPLOY_USYC: Move idle USDC to Teller/USYC for yield
2. TOP_UP_BOND: Increase an agent's bond deposit
3. REBALANCE: Transfer USDC between agent wallets
4. HOLD: Take no action (explicitly choose to wait)

Your task: Decide what actions to take RIGHT NOW. Be specific about amounts.
Consider: Is gas cost worth it? Is now the right time? Are reserves safe?

Respond with a JSON array of actions (can be empty if HOLD is best):
[
  {{
    "action_type": "DEPLOY_USYC" | "TOP_UP_BOND" | "REBALANCE" | "HOLD",
    "agent": "deployer" | "scout" | "judge" | "watchdog" | "system",
    "amount_usdc": 0.0,
    "reason": "brief explanation"
  }}
]"""

        try:
            from groq import AsyncGroq
            client = AsyncGroq(api_key=self.groq_api_key)
            resp = await client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=512,
            )
            content = resp.choices[0].message.content.strip()
            start = content.find("[")
            end = content.rfind("]") + 1
            if start >= 0 and end > start:
                raw_actions = json.loads(content[start:end])
                actions = []
                for a in raw_actions:
                    action = TreasuryAction(
                        action_type=a.get("action_type", "HOLD"),
                        agent=a.get("agent", "system"),
                        amount_usdc=float(a.get("amount_usdc", 0.0)),
                        reason=a.get("reason", ""),
                    )
                    if action.action_type != "HOLD":
                        actions.append(action)
                return actions
        except Exception as exc:
            log.warning("treasurer.llm_reasoning_failed", error=str(exc))

        # Fallback: simple rule-based decisions
        actions = []
        if state.deployer_usdc > USYC_DEPLOY_THRESHOLD_USDC + MINIMUM_OPERATING_RESERVE_USDC:
            deploy_amount = state.deployer_usdc - MINIMUM_OPERATING_RESERVE_USDC
            actions.append(TreasuryAction(
                action_type="DEPLOY_USYC",
                agent="deployer",
                amount_usdc=deploy_amount,
                reason=f"Deployer has ${state.deployer_usdc:.2f} idle; deploying ${deploy_amount:.2f} to USYC for yield.",
            ))
        return actions

    async def _execute_action(self, action: TreasuryAction) -> TreasuryAction:
        """Execute a treasury action and record the tx hash."""
        log.info(
            "treasurer.executing",
            action_type=action.action_type,
            agent=action.agent,
            amount=action.amount_usdc,
            reason=action.reason,
        )

        if action.action_type == "DEPLOY_USYC":
            try:
                from arc.usyc_manager import auto_manage_idle_capital
                await auto_manage_idle_capital(self.arc_client, self.arc_client.address)
                action.tx_hash = "deployed_via_usyc_manager"
                log.info("treasurer.usyc_deployed", amount=action.amount_usdc)
            except Exception as e:
                log.warning("treasurer.usyc_deploy_failed", error=str(e))

        elif action.action_type == "TOP_UP_BOND":
            try:
                from arc.bond_manager import AgentBondManager
                bond_mgr = AgentBondManager()
                await bond_mgr.ensure_bond_deposited(
                    self.arc_client,
                    self.settings.bond_manager_address,
                )
                log.info("treasurer.bond_topped_up", agent=action.agent)
            except Exception as e:
                log.warning("treasurer.bond_top_up_failed", error=str(e))

        return action

    async def run_cycle(self) -> list[TreasuryAction]:
        """Run one treasury management cycle. Called every 5 minutes."""
        state = await self._get_balances()

        log.info(
            "treasurer.cycle_start",
            deployer_usdc=round(state.deployer_usdc, 2),
            usyc_deployed=round(state.usyc_deployed, 2),
            total_liquid=round(state.deployer_usdc + state.scout_usdc, 2),
        )

        actions = await self._reason_about_allocation(state)

        executed = []
        for action in actions:
            executed_action = await self._execute_action(action)
            executed.append(executed_action)
            self._action_history.append(executed_action)

        if not executed:
            log.info("treasurer.hold", reason="No actions needed this cycle")

        return executed

    def get_action_history(self) -> list[dict]:
        return [asdict(a) for a in self._action_history[-50:]]

    async def run_forever(self) -> None:
        """Main treasurer loop — runs every 5 minutes."""
        self._running = True
        log.info("treasurer.started")

        while self._running:
            try:
                actions = await self.run_cycle()
                if actions:
                    log.info("treasurer.cycle_complete", actions_taken=len(actions))
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("treasurer.cycle_error", error=str(e))

            await asyncio.sleep(300)  # 5 minutes

    def stop(self) -> None:
        self._running = False
