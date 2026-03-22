"""
Tests for the transaction (mint/burn) router endpoints.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from offchain.main import create_app
from offchain.services import audit
from offchain.services.reserves import get_reserve_service


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestMintEndpoint:
    """Tests for POST /api/v1/transactions/mint."""

    @pytest.mark.asyncio
    async def test_mint_success(self, client: AsyncClient):
        audit.clear_log()
        # Initialize reserve monitor with sufficient reserves
        reserve_svc = get_reserve_service()
        await reserve_svc.get_reserve_status(
            total_reserves=10_000_000_000_000,  # $10M in 6-dec
            total_supply=0,
            attestation_fresh=True,
        )
        response = await client.post(
            "/api/v1/transactions/mint",
            json={
                "to_address": "0x1234567890abcdef1234567890abcdef12345678",
                "amount_usd": 1000.0,
                "reference_id": "DEP-001",
                "payment_rail": "ACH",
                "depositor_account_id": "ACCT-12345",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tx_type"] == "MINT"
        assert data["status"] == "CONFIRMED"
        assert data["amount_usd"] == 1000.0
        assert data["token_amount"] == 1_000_000_000  # $1000 * 1e6
        assert data["tx_hash"] is not None
        assert data["compliance_status"] == "PASSED"

    @pytest.mark.asyncio
    async def test_mint_invalid_amount(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/transactions/mint",
            json={
                "to_address": "0xabc",
                "amount_usd": -100.0,
                "reference_id": "BAD-001",
                "payment_rail": "ACH",
                "depositor_account_id": "ACCT-99",
            },
        )
        assert response.status_code == 422  # Pydantic validation error

    @pytest.mark.asyncio
    async def test_mint_creates_audit_entries(self, client: AsyncClient):
        audit.clear_log()
        await client.post(
            "/api/v1/transactions/mint",
            json={
                "to_address": "0xAUDIT_TEST",
                "amount_usd": 500.0,
                "reference_id": "AUD-001",
                "payment_rail": "FEDWIRE",
                "depositor_account_id": "ACCT-AUDIT",
            },
        )
        log = audit.get_full_log()
        assert len(log) > 0
        actions = [e.action for e in log]
        assert "mint_request" in actions


class TestBurnEndpoint:
    """Tests for POST /api/v1/transactions/burn."""

    @pytest.mark.asyncio
    async def test_burn_success(self, client: AsyncClient):
        audit.clear_log()
        response = await client.post(
            "/api/v1/transactions/burn",
            json={
                "from_address": "0xBURN_ADDR",
                "amount_usd": 500.0,
                "reference_id": "RED-001",
                "destination_account_id": "ACCT-DEST",
                "payment_rail": "FEDNOW",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tx_type"] == "BURN"
        assert data["status"] == "CONFIRMED"
        assert data["amount_usd"] == 500.0
        assert data["token_amount"] == 500_000_000
        assert "RTP" in data["message"] or "FEDNOW" in data["message"] or "Par redemption" in data["message"]

    @pytest.mark.asyncio
    async def test_burn_missing_fields(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/transactions/burn",
            json={"from_address": "0xABC"},
        )
        assert response.status_code == 422
