"""
Tests for custody service adapters.
"""

from __future__ import annotations

import pytest

from offchain.models.schemas import CustodyTier
from offchain.services import audit
from integration.custody.adapter import (
    StubCoinbaseCustodyAdapter,
    StubFireblocksCustodyAdapter,
)


class TestFireblocksCustodyAdapter:
    """Tests for the Fireblocks custody stub."""

    @pytest.mark.asyncio
    async def test_initial_balances(self):
        adapter = StubFireblocksCustodyAdapter()
        balances = await adapter.get_all_balances()
        assert len(balances) == 3
        hot = next(b for b in balances if b.tier == CustodyTier.HOT)
        assert hot.balance_usd == 500_000.0

    @pytest.mark.asyncio
    async def test_deposit(self):
        audit.clear_log()
        adapter = StubFireblocksCustodyAdapter()
        result = await adapter.deposit(
            tier=CustodyTier.HOT, amount_usd=100_000.0, reference_id="DEP-001"
        )
        assert result.status == "COMPLETED"
        assert result.direction == "DEPOSIT"
        balance = await adapter.get_balance(CustodyTier.HOT)
        assert balance.balance_usd == 600_000.0

    @pytest.mark.asyncio
    async def test_withdraw_success(self):
        audit.clear_log()
        adapter = StubFireblocksCustodyAdapter()
        result = await adapter.withdraw(
            tier=CustodyTier.HOT, amount_usd=100_000.0, reference_id="WD-001"
        )
        assert result.status == "COMPLETED"
        balance = await adapter.get_balance(CustodyTier.HOT)
        assert balance.balance_usd == 400_000.0

    @pytest.mark.asyncio
    async def test_withdraw_insufficient(self):
        audit.clear_log()
        adapter = StubFireblocksCustodyAdapter()
        result = await adapter.withdraw(
            tier=CustodyTier.HOT, amount_usd=999_999.0, reference_id="WD-FAIL"
        )
        assert result.status == "FAILED"
        assert "Insufficient" in result.message

    @pytest.mark.asyncio
    async def test_rebalance(self):
        audit.clear_log()
        adapter = StubFireblocksCustodyAdapter()
        result = await adapter.rebalance(
            from_tier=CustodyTier.COLD,
            to_tier=CustodyTier.HOT,
            amount_usd=500_000.0,
        )
        assert result.status == "COMPLETED"
        hot = await adapter.get_balance(CustodyTier.HOT)
        cold = await adapter.get_balance(CustodyTier.COLD)
        assert hot.balance_usd == 1_000_000.0
        assert cold.balance_usd == 7_000_000.0

    @pytest.mark.asyncio
    async def test_rebalance_insufficient(self):
        audit.clear_log()
        adapter = StubFireblocksCustodyAdapter()
        result = await adapter.rebalance(
            from_tier=CustodyTier.HOT,
            to_tier=CustodyTier.COLD,
            amount_usd=999_999_999.0,
        )
        assert result.status == "FAILED"


class TestCoinbaseCustodyAdapter:
    """Tests for the Coinbase custody stub."""

    @pytest.mark.asyncio
    async def test_initial_balances(self):
        adapter = StubCoinbaseCustodyAdapter()
        balances = await adapter.get_all_balances()
        assert len(balances) == 3

    @pytest.mark.asyncio
    async def test_deposit_and_withdraw(self):
        audit.clear_log()
        adapter = StubCoinbaseCustodyAdapter()
        await adapter.deposit(tier=CustodyTier.WARM, amount_usd=50_000.0, reference_id="CB-001")
        balance = await adapter.get_balance(CustodyTier.WARM)
        assert balance.balance_usd == 1_050_000.0

        await adapter.withdraw(tier=CustodyTier.WARM, amount_usd=50_000.0, reference_id="CB-002")
        balance = await adapter.get_balance(CustodyTier.WARM)
        assert balance.balance_usd == 1_000_000.0
