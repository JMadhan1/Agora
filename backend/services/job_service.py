"""Job and earnings service."""
from __future__ import annotations

import structlog

log = structlog.get_logger()


class JobService:
    async def get_job_earnings_summary(self, db_session) -> dict:
        try:
            from storage.database import AgentJobRecord
            jobs = db_session.query(AgentJobRecord).filter(AgentJobRecord.status == "COMPLETED").all()
            total = sum(j.usdc_earned or 0 for j in jobs)
            return {
                "completed_jobs": len(jobs),
                "total_usdc_earned": round(total, 4),
            }
        except Exception as e:
            log.warning("earnings_summary_failed", error=str(e))
            return {"completed_jobs": 0, "total_usdc_earned": 0.0}

    async def get_usyc_balance(self, wallet_address: str) -> float:
        """Hits Arc RPC to get USYC balance — returns 0 if not connected."""
        try:
            import os
            from web3 import AsyncWeb3
            from web3.providers import AsyncHTTPProvider

            rpc_key = os.getenv("ARC_RPC_KEY", "")
            rpc_url = os.getenv("ARC_RPC_URL") or f"https://rpc.testnet.arc-node.thecanteenapp.com/v1/{rpc_key}"
            if not rpc_key and not rpc_url:
                return 0.0

            USYC_TOKEN = "0xe9185F0c5F296Ed1797AaE4238D26CCaBEadb86C"
            ABI = [{"inputs": [{"name": "account", "type": "address"}], "name": "balanceOf", "outputs": [{"name": "", "type": "uint256"}], "stateMutability": "view", "type": "function"}]

            w3 = AsyncWeb3(AsyncHTTPProvider(rpc_url))
            contract = w3.eth.contract(address=AsyncWeb3.to_checksum_address(USYC_TOKEN), abi=ABI)
            raw = await contract.functions.balanceOf(AsyncWeb3.to_checksum_address(wallet_address)).call()
            return raw / 1e18
        except Exception:
            return 0.0
