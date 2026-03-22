"""
Reserve monitoring and treasury service.
Tracks 1:1 reserve backing of CDA tokens (GENIUS Act Section 4), alerts on deviations,
and coordinates rebalancing.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Reserves ensure 1:1 backing of CDA tokens by qualifying assets.

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from offchain.config import Settings, get_settings
from offchain.models.schemas import ReserveStatusResponse
from offchain.services import audit

logger = logging.getLogger("cari.reserves")


class ReserveMonitorService:
    """Real-time reserve monitoring and 1:1 CDA backing enforcement."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # In-memory cache for dev/test. Production uses Redis or DB.
        self._last_reserves: int = 0
        self._last_supply: int = 0
        self._attestation_fresh: bool = False
        self._last_attested_at: datetime | None = None
        self._attestation_hash: str | None = None

    async def get_reserve_status(
        self,
        *,
        total_reserves: int | None = None,
        total_supply: int | None = None,
        attestation_fresh: bool | None = None,
        last_attested_at: datetime | None = None,
        attestation_hash: str | None = None,
    ) -> ReserveStatusResponse:
        """Build the current reserve status report.

        If args are passed, they override cached values (used when fresh
        data is read from the blockchain).
        """
        reserves = total_reserves if total_reserves is not None else self._last_reserves
        supply = total_supply if total_supply is not None else self._last_supply
        fresh = attestation_fresh if attestation_fresh is not None else self._attestation_fresh

        # Update cache
        self._last_reserves = reserves
        self._last_supply = supply
        self._attestation_fresh = fresh
        if last_attested_at is not None:
            self._last_attested_at = last_attested_at
        if attestation_hash is not None:
            self._attestation_hash = attestation_hash

        reserves_usd = reserves / 1e6
        supply_usd = supply / 1e6
        ratio = reserves_usd / supply_usd if supply_usd > 0 else float("inf")
        compliant = ratio >= 1.0 and fresh

        status = ReserveStatusResponse(
            total_reserves_usd=reserves_usd,
            total_supply_tokens=supply,
            total_supply_usd=supply_usd,
            backing_ratio=round(ratio, 6) if ratio != float("inf") else 999.0,
            attestation_fresh=fresh,
            last_attested_at=self._last_attested_at,
            attestation_hash=self._attestation_hash,
            max_staleness_seconds=self._settings.reserve_staleness_seconds,
            compliant=compliant,
        )

        # Alert if backing ratio deviates
        if supply > 0 and ratio < 1.0:
            logger.critical(
                "RESERVE BACKING VIOLATION: ratio=%.4f (reserves=%d, supply=%d)",
                ratio, reserves, supply,
            )
            await audit.record(
                actor="RESERVE_MONITOR",
                action="backing_violation",
                resource="ReserveOracle",
                details={"ratio": ratio, "reserves": reserves, "supply": supply},
            )

        deviation_pct = abs(1.0 - ratio) * 100 if ratio != float("inf") else 0
        if 0 < deviation_pct > self._settings.reserve_rebalance_threshold_pct:
            logger.warning(
                "Reserve deviation %.2f%% exceeds threshold %.2f%%",
                deviation_pct, self._settings.reserve_rebalance_threshold_pct,
            )

        return status

    async def check_mint_allowed(self, mint_amount: int) -> tuple[bool, str]:
        """Check if a CDA mint of `mint_amount` (6-decimal) is allowed by reserves."""
        new_supply = self._last_supply + mint_amount
        if new_supply > self._last_reserves:
            return False, (
                f"Mint would violate 1:1 backing: "
                f"supply_after={new_supply}, reserves={self._last_reserves}"
            )
        if not self._attestation_fresh:
            return False, "Reserve attestation is stale — minting blocked"
        return True, "OK"


_reserve_service: ReserveMonitorService | None = None


def get_reserve_service() -> ReserveMonitorService:
    global _reserve_service
    if _reserve_service is None:
        _reserve_service = ReserveMonitorService()
    return _reserve_service
