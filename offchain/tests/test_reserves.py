"""
Tests for reserve monitoring service.
"""

from __future__ import annotations

import pytest

from offchain.services import audit
from offchain.services.reserves import ReserveMonitorService


class TestReserveMonitor:
    """Tests for the reserve monitoring service."""

    @pytest.mark.asyncio
    async def test_compliant_status(self):
        audit.clear_log()
        svc = ReserveMonitorService()
        status = await svc.get_reserve_status(
            total_reserves=10_000_000_000,  # $10,000 in 6-dec
            total_supply=10_000_000_000,
            attestation_fresh=True,
        )
        assert status.backing_ratio == 1.0
        assert status.compliant is True

    @pytest.mark.asyncio
    async def test_over_backed(self):
        audit.clear_log()
        svc = ReserveMonitorService()
        status = await svc.get_reserve_status(
            total_reserves=15_000_000_000,
            total_supply=10_000_000_000,
            attestation_fresh=True,
        )
        assert status.backing_ratio == 1.5
        assert status.compliant is True

    @pytest.mark.asyncio
    async def test_under_backed_violation(self):
        audit.clear_log()
        svc = ReserveMonitorService()
        status = await svc.get_reserve_status(
            total_reserves=9_000_000_000,
            total_supply=10_000_000_000,
            attestation_fresh=True,
        )
        assert status.backing_ratio == 0.9
        assert status.compliant is False

    @pytest.mark.asyncio
    async def test_stale_attestation(self):
        audit.clear_log()
        svc = ReserveMonitorService()
        status = await svc.get_reserve_status(
            total_reserves=10_000_000_000,
            total_supply=10_000_000_000,
            attestation_fresh=False,
        )
        assert status.compliant is False

    @pytest.mark.asyncio
    async def test_mint_allowed(self):
        audit.clear_log()
        svc = ReserveMonitorService()
        # Set initial state
        await svc.get_reserve_status(
            total_reserves=10_000_000_000,
            total_supply=5_000_000_000,
            attestation_fresh=True,
        )
        allowed, msg = await svc.check_mint_allowed(3_000_000_000)
        assert allowed is True
        assert msg == "OK"

    @pytest.mark.asyncio
    async def test_mint_blocked_exceeds_reserves(self):
        audit.clear_log()
        svc = ReserveMonitorService()
        await svc.get_reserve_status(
            total_reserves=10_000_000_000,
            total_supply=9_000_000_000,
            attestation_fresh=True,
        )
        allowed, msg = await svc.check_mint_allowed(2_000_000_000)
        assert allowed is False
        assert "1:1 backing" in msg

    @pytest.mark.asyncio
    async def test_mint_blocked_stale_attestation(self):
        audit.clear_log()
        svc = ReserveMonitorService()
        await svc.get_reserve_status(
            total_reserves=10_000_000_000,
            total_supply=5_000_000_000,
            attestation_fresh=False,
        )
        allowed, msg = await svc.check_mint_allowed(1_000_000_000)
        assert allowed is False
        assert "stale" in msg.lower()

    @pytest.mark.asyncio
    async def test_zero_supply(self):
        audit.clear_log()
        svc = ReserveMonitorService()
        status = await svc.get_reserve_status(
            total_reserves=10_000_000_000,
            total_supply=0,
            attestation_fresh=True,
        )
        # No supply means infinite ratio (capped to 999.0)
        assert status.backing_ratio == 999.0
        assert status.compliant is True
