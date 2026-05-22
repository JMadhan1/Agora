"""Monitors UMA OptimisticOracle V3 for active assertions in the challenge window."""
from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from typing import Callable
import structlog
from web3 import AsyncWeb3
from web3.providers import AsyncHTTPProvider

log = structlog.get_logger()

# UMA OptimisticOracle V3 on Polygon mainnet
UMA_OO_V3_ADDRESS = "0x9923D42eF695B5dd9911D05Ac944d4cAca3c4EAC"

# AssertionMade event signature
ASSERTION_MADE_TOPIC = AsyncWeb3.keccak(
    text="AssertionMade(bytes32,bytes32,address,bytes,address,address,address,uint64,address,uint256,bytes32)"
).hex()

ASSERTION_DISPUTED_TOPIC = AsyncWeb3.keccak(
    text="AssertionDisputed(bytes32,address)"
).hex()


class UMAMonitor:
    """Watches UMA OptimisticOracle V3 for new assertions that could be disputed."""

    def __init__(self, polygon_rpc_url: str = "https://polygon-rpc.com"):
        self.w3 = AsyncWeb3(AsyncHTTPProvider(polygon_rpc_url, request_kwargs={"timeout": 20}))
        self._last_block: int = 0
        self._seen_assertions: set[str] = set()

    async def _get_latest_block(self) -> int:
        try:
            return await self.w3.eth.block_number
        except Exception as e:
            log.warning("uma_block_fetch_failed", error=str(e))
            return self._last_block

    async def get_active_assertions(self) -> list[dict]:
        """
        Fetches AssertionMade events from the last 1000 blocks (≈30 min on Polygon).
        Returns assertions whose challenge window hasn't closed yet (expirationTime > now).
        """
        now = int(datetime.now(timezone.utc).timestamp())
        try:
            latest = await self._get_latest_block()
            from_block = max(0, latest - 1000)

            logs = await self.w3.eth.get_logs({
                "address": AsyncWeb3.to_checksum_address(UMA_OO_V3_ADDRESS),
                "topics": [ASSERTION_MADE_TOPIC],
                "fromBlock": from_block,
                "toBlock": latest,
            })

            active = []
            for entry in logs:
                # Decode basic fields from topics/data — assertionId is first topic after sig
                assertion_id = entry["topics"][1].hex() if len(entry["topics"]) > 1 else ""
                # expirationTime is in the data — parse last 8 bytes as uint64
                data = entry["data"].hex() if isinstance(entry["data"], bytes) else entry["data"].lstrip("0x")
                # Approximate: read last uint64 in the packed data
                expiration_time = 0
                try:
                    if len(data) >= 16:
                        expiration_time = int(data[-16:], 16)
                except Exception:
                    pass

                if expiration_time > now or expiration_time == 0:
                    active.append({
                        "assertion_id": assertion_id,
                        "tx_hash": entry["transactionHash"].hex(),
                        "block_number": entry["blockNumber"],
                        "expiration_time": expiration_time,
                        "expires_in_seconds": max(0, expiration_time - now),
                    })

            log.info("uma_assertions_fetched", count=len(active), from_block=from_block)
            return active

        except Exception as e:
            log.error("uma_assertions_fetch_failed", error=str(e))
            return []

    async def get_disputed_assertions(self) -> list[dict]:
        """Fetches recently disputed assertions."""
        try:
            latest = await self._get_latest_block()
            from_block = max(0, latest - 5000)
            logs = await self.w3.eth.get_logs({
                "address": AsyncWeb3.to_checksum_address(UMA_OO_V3_ADDRESS),
                "topics": [ASSERTION_DISPUTED_TOPIC],
                "fromBlock": from_block,
                "toBlock": latest,
            })
            return [
                {
                    "assertion_id": e["topics"][1].hex() if len(e["topics"]) > 1 else "",
                    "tx_hash": e["transactionHash"].hex(),
                    "block_number": e["blockNumber"],
                }
                for e in logs
            ]
        except Exception as e:
            log.error("uma_disputed_fetch_failed", error=str(e))
            return []

    async def watch_assertions(self, callback: Callable[[dict], None]) -> None:
        """Polls every 10 seconds for new AssertionMade events, calls callback for each new one."""
        self._last_block = await self._get_latest_block()
        while True:
            try:
                await asyncio.sleep(10)
                current_block = await self._get_latest_block()
                if current_block <= self._last_block:
                    continue

                logs = await self.w3.eth.get_logs({
                    "address": AsyncWeb3.to_checksum_address(UMA_OO_V3_ADDRESS),
                    "topics": [ASSERTION_MADE_TOPIC],
                    "fromBlock": self._last_block + 1,
                    "toBlock": current_block,
                })
                self._last_block = current_block

                for entry in logs:
                    assertion_id = entry["topics"][1].hex() if len(entry["topics"]) > 1 else ""
                    if assertion_id and assertion_id not in self._seen_assertions:
                        self._seen_assertions.add(assertion_id)
                        assertion = {
                            "assertion_id": assertion_id,
                            "tx_hash": entry["transactionHash"].hex(),
                            "block_number": entry["blockNumber"],
                        }
                        try:
                            await callback(assertion)
                        except Exception as e:
                            log.error("uma_callback_error", error=str(e))

            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error("uma_watch_error", error=str(e))
                await asyncio.sleep(30)
