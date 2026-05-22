"""Attestation service — Arc Testnet on-chain data."""
from __future__ import annotations

ARC_EXPLORER = "https://testnet.arcscan.app"


class AttestationService:
    async def get_arc_scan_url(self, tx_hash: str) -> str:
        if not tx_hash:
            return ""
        return f"{ARC_EXPLORER}/tx/{tx_hash}"

    async def get_arc_scan_address_url(self, address: str) -> str:
        if not address:
            return ""
        return f"{ARC_EXPLORER}/address/{address}"
