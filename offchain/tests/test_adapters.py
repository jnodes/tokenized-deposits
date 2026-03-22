"""
Tests for core banking and payment rails adapters.
"""

from __future__ import annotations

import pytest

from offchain.models.schemas import PaymentRail
from offchain.services import audit
from integration.core_banking.adapter import StubCoreBankingAdapter, GLEntry, GLEntryType
from integration.payments_rails.adapter import get_payment_adapter


class TestCoreBankingAdapter:
    """Tests for the stub core banking adapter."""

    @pytest.mark.asyncio
    async def test_verify_deposit(self):
        audit.clear_log()
        adapter = StubCoreBankingAdapter()
        result = await adapter.verify_deposit(
            account_id="ACCT-001",
            reference_id="DEP-001",
            amount_usd=5000.0,
        )
        assert result.verified is True
        assert result.amount_usd == 5000.0

    @pytest.mark.asyncio
    async def test_post_gl_entries(self):
        audit.clear_log()
        adapter = StubCoreBankingAdapter()
        initial = await adapter.get_reserve_balance()

        entries = [
            GLEntry(
                account_number="1010-RESERVE",
                entry_type=GLEntryType.CREDIT,
                amount_usd=1000.0,
                reference_id="GL-001",
                gl_code="1010",
            ),
        ]
        result = await adapter.post_gl_entries(entries)
        assert result is True
        new_balance = await adapter.get_reserve_balance()
        assert new_balance == initial + 1000.0

    @pytest.mark.asyncio
    async def test_initiate_payout(self):
        audit.clear_log()
        adapter = StubCoreBankingAdapter()
        ref = await adapter.initiate_payout(
            account_id="ACCT-DEST",
            amount_usd=2500.0,
            reference_id="PAY-001",
            rail="FEDNOW",
        )
        assert ref.startswith("PAYOUT-")

    @pytest.mark.asyncio
    async def test_reserve_balance(self):
        adapter = StubCoreBankingAdapter()
        balance = await adapter.get_reserve_balance()
        assert balance == 10_000_000.0


class TestPaymentRailAdapters:
    """Tests for payment rail adapter factory and stubs."""

    @pytest.mark.asyncio
    async def test_ach_adapter(self):
        audit.clear_log()
        adapter = get_payment_adapter(PaymentRail.ACH)
        result = await adapter.send_payment(
            destination_account="ACCT-001",
            amount_usd=1000.0,
            reference_id="ACH-001",
        )
        assert result.rail == PaymentRail.ACH
        assert result.trace_number.startswith("ACH-")

    @pytest.mark.asyncio
    async def test_fedwire_adapter(self):
        audit.clear_log()
        adapter = get_payment_adapter(PaymentRail.FEDWIRE)
        result = await adapter.send_payment(
            destination_account="ACCT-002",
            amount_usd=50000.0,
            reference_id="FW-001",
        )
        assert result.rail == PaymentRail.FEDWIRE
        assert result.trace_number.startswith("FW-")

    @pytest.mark.asyncio
    async def test_rtp_adapter(self):
        audit.clear_log()
        adapter = get_payment_adapter(PaymentRail.RTP)
        result = await adapter.send_payment(
            destination_account="ACCT-003",
            amount_usd=500.0,
            reference_id="RTP-001",
        )
        assert result.rail == PaymentRail.RTP

    @pytest.mark.asyncio
    async def test_fednow_uses_rtp_adapter(self):
        audit.clear_log()
        adapter = get_payment_adapter(PaymentRail.FEDNOW)
        result = await adapter.send_payment(
            destination_account="ACCT-004",
            amount_usd=200.0,
            reference_id="FN-001",
        )
        # FedNow shares the RTP adapter
        assert result.rail == PaymentRail.RTP

    @pytest.mark.asyncio
    async def test_book_transfer(self):
        audit.clear_log()
        adapter = get_payment_adapter(PaymentRail.BOOK_TRANSFER)
        result = await adapter.send_payment(
            destination_account="ACCT-005",
            amount_usd=10000.0,
            reference_id="BK-001",
        )
        assert result.rail == PaymentRail.BOOK_TRANSFER
        assert result.trace_number.startswith("BK-")
