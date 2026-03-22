"""
Tests for reconciliation engine and router.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from offchain.main import create_app
from offchain.models.schemas import ReconciliationStatus
from offchain.services import audit
from reconciliation.engine import (
    OffChainRecord,
    OnChainRecord,
    ReconciliationEngine,
)


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestReconciliationEngine:
    """Unit tests for the reconciliation engine."""

    @pytest.mark.asyncio
    async def test_matched_records(self):
        audit.clear_log()
        engine = ReconciliationEngine()

        await engine.add_on_chain_record(
            OnChainRecord(
                tx_hash="0xabc123",
                tx_type="MINT",
                amount=1_000_000_000,  # $1000 in 6-dec
                reference_id="REF-001",
            )
        )
        await engine.add_off_chain_record(
            OffChainRecord(
                entry_id="GL-001",
                reference_id="REF-001",
                amount_usd=1000.00,
                gl_account="1010-RESERVE",
                entry_type="DEBIT",
            )
        )

        entries = await engine.reconcile()
        assert len(entries) == 1
        assert entries[0].status == ReconciliationStatus.MATCHED
        assert entries[0].reference_id == "REF-001"

    @pytest.mark.asyncio
    async def test_unmatched_on_chain(self):
        audit.clear_log()
        engine = ReconciliationEngine()

        await engine.add_on_chain_record(
            OnChainRecord(
                tx_hash="0xorphan",
                tx_type="MINT",
                amount=500_000_000,
                reference_id="ORPHAN-001",
            )
        )

        entries = await engine.reconcile()
        assert len(entries) == 1
        assert entries[0].status == ReconciliationStatus.UNMATCHED
        assert "No off-chain" in entries[0].exception_reason

    @pytest.mark.asyncio
    async def test_unmatched_off_chain(self):
        audit.clear_log()
        engine = ReconciliationEngine()

        await engine.add_off_chain_record(
            OffChainRecord(
                entry_id="GL-ORPHAN",
                reference_id="MISSING-ON-CHAIN",
                amount_usd=2000.00,
                gl_account="2010-LIABILITY",
                entry_type="CREDIT",
            )
        )

        entries = await engine.reconcile()
        assert len(entries) == 1
        assert entries[0].status == ReconciliationStatus.UNMATCHED
        assert "No on-chain" in entries[0].exception_reason

    @pytest.mark.asyncio
    async def test_amount_mismatch_exception(self):
        audit.clear_log()
        engine = ReconciliationEngine()

        await engine.add_on_chain_record(
            OnChainRecord(
                tx_hash="0xmismatch",
                tx_type="MINT",
                amount=1_000_000_000,  # $1000
                reference_id="MISMATCH-001",
            )
        )
        await engine.add_off_chain_record(
            OffChainRecord(
                entry_id="GL-MISMATCH",
                reference_id="MISMATCH-001",
                amount_usd=999.00,  # $1 off
                gl_account="1010-RESERVE",
                entry_type="DEBIT",
            )
        )

        entries = await engine.reconcile()
        assert len(entries) == 1
        assert entries[0].status == ReconciliationStatus.EXCEPTION
        assert "Amount mismatch" in entries[0].exception_reason

    @pytest.mark.asyncio
    async def test_summary(self):
        audit.clear_log()
        engine = ReconciliationEngine()

        # Add 2 matched, 1 unmatched
        for i in range(2):
            await engine.add_on_chain_record(
                OnChainRecord(
                    tx_hash=f"0xhash_{i}",
                    tx_type="MINT",
                    amount=100_000_000,
                    reference_id=f"REF-{i}",
                )
            )
            await engine.add_off_chain_record(
                OffChainRecord(
                    entry_id=f"GL-{i}",
                    reference_id=f"REF-{i}",
                    amount_usd=100.00,
                    gl_account="1010",
                    entry_type="DEBIT",
                )
            )
        await engine.add_on_chain_record(
            OnChainRecord(tx_hash="0xorphan", tx_type="BURN", amount=50_000_000, reference_id="ORPHAN")
        )

        await engine.reconcile()
        summary = await engine.get_summary()
        assert summary.matched == 2
        assert summary.unmatched == 1
        assert summary.total_entries == 3


class TestReconciliationRouter:
    """Integration tests for reconciliation API endpoints."""

    @pytest.mark.asyncio
    async def test_run_reconciliation(self, client: AsyncClient):
        response = await client.post("/api/v1/reconciliation/run")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_summary(self, client: AsyncClient):
        response = await client.get("/api/v1/reconciliation/summary")
        assert response.status_code == 200
        data = response.json()
        assert "matched" in data
        assert "unmatched" in data
        assert "total_entries" in data
