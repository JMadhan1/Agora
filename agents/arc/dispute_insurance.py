"""
DisputeInsuranceManager — on-chain interaction layer for DisputeInsurance.sol.

Provides helpers for:
  - Buying a policy (buyer → contract)
  - Triggering payouts after a won dispute (Watchdog → contract)
  - Reading pool stats and policy status
"""
from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

DISPUTE_INSURANCE_ABI = [
    {
        "inputs": [
            {"name": "marketId", "type": "string"},
            {"name": "coverageAmount", "type": "uint256"},
        ],
        "name": "buyPolicy",
        "outputs": [{"name": "policyId", "type": "uint256"}],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "marketId", "type": "string"}],
        "name": "triggerMarketPayout",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "policyId", "type": "uint256"}],
        "name": "triggerSinglePayout",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [{"name": "policyId", "type": "uint256"}],
        "name": "refundExpired",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function",
    },
    {
        "inputs": [],
        "name": "getPoolStats",
        "outputs": [
            {"name": "balance", "type": "uint256"},
            {"name": "totalPremiums", "type": "uint256"},
            {"name": "totalPayouts", "type": "uint256"},
            {"name": "totalPolicies", "type": "uint256"},
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "policyId", "type": "uint256"}],
        "name": "getPolicy",
        "outputs": [
            {
                "components": [
                    {"name": "buyer", "type": "address"},
                    {"name": "marketId", "type": "string"},
                    {"name": "premium", "type": "uint256"},
                    {"name": "coverageAmount", "type": "uint256"},
                    {"name": "payout", "type": "uint256"},
                    {"name": "purchasedAt", "type": "uint256"},
                    {"name": "expiresAt", "type": "uint256"},
                    {"name": "active", "type": "bool"},
                    {"name": "paid", "type": "bool"},
                ],
                "name": "",
                "type": "tuple",
            }
        ],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"name": "coverageAmount", "type": "uint256"}],
        "name": "calculatePremium",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "pure",
        "type": "function",
    },
]

USDC_DECIMALS = 6


class DisputeInsuranceManager:
    """Wrapper around the on-chain DisputeInsurance contract."""

    def __init__(self, arc_client, contract_address: str) -> None:
        self.arc_client = arc_client
        self.contract_address = contract_address

    async def buy_policy(self, market_id: str, coverage_usdc: float) -> str | None:
        """Buy an insurance policy for a market. Returns tx hash or None on failure."""
        coverage_raw = int(coverage_usdc * 10**USDC_DECIMALS)
        try:
            tx = await self.arc_client.call_contract_write(
                self.contract_address,
                DISPUTE_INSURANCE_ABI,
                "buyPolicy",
                [market_id, coverage_raw],
            )
            log.info("insurance.policy_bought", market_id=market_id, coverage_usdc=coverage_usdc, tx=tx)
            return tx
        except Exception as exc:
            log.error("insurance.buy_policy_failed", market_id=market_id, error=str(exc))
            return None

    async def trigger_market_payout(self, market_id: str) -> str | None:
        """Trigger payout for all active policies on a market after a dispute win."""
        try:
            tx = await self.arc_client.call_contract_write(
                self.contract_address,
                DISPUTE_INSURANCE_ABI,
                "triggerMarketPayout",
                [market_id],
            )
            log.info("insurance.payout_triggered", market_id=market_id, tx=tx)
            return tx
        except Exception as exc:
            log.error("insurance.trigger_payout_failed", market_id=market_id, error=str(exc))
            return None

    async def get_pool_stats(self) -> dict:
        """Read on-chain pool stats. Returns balances in USDC (float)."""
        try:
            result = await self.arc_client.call_contract_read(
                self.contract_address,
                DISPUTE_INSURANCE_ABI,
                "getPoolStats",
                [],
            )
            balance, total_premiums, total_payouts, total_policies = result
            return {
                "pool_balance_usdc": balance / 10**USDC_DECIMALS,
                "total_premiums_usdc": total_premiums / 10**USDC_DECIMALS,
                "total_payouts_usdc": total_payouts / 10**USDC_DECIMALS,
                "total_policies": total_policies,
            }
        except Exception as exc:
            log.warning("insurance.get_pool_stats_failed", error=str(exc))
            return {
                "pool_balance_usdc": 0.0,
                "total_premiums_usdc": 0.0,
                "total_payouts_usdc": 0.0,
                "total_policies": 0,
            }

    async def get_policy(self, policy_id: int) -> dict | None:
        """Read a single policy from chain."""
        try:
            result = await self.arc_client.call_contract_read(
                self.contract_address,
                DISPUTE_INSURANCE_ABI,
                "getPolicy",
                [policy_id],
            )
            buyer, market_id, premium, coverage, payout, purchased_at, expires_at, active, paid = result
            return {
                "policy_id": policy_id,
                "buyer": buyer,
                "market_id": market_id,
                "premium_usdc": premium / 10**USDC_DECIMALS,
                "coverage_usdc": coverage / 10**USDC_DECIMALS,
                "payout_usdc": payout / 10**USDC_DECIMALS,
                "purchased_at": purchased_at,
                "expires_at": expires_at,
                "active": active,
                "paid": paid,
            }
        except Exception as exc:
            log.warning("insurance.get_policy_failed", policy_id=policy_id, error=str(exc))
            return None
