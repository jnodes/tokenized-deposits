"""
Tests for the settlement router endpoints.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from offchain.main import create_app
from offchain.services import audit


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestSettlementEndpoint:
    """Tests for POST /api/v1/settlement/initiate."""

    @pytest.mark.asyncio
    async def test_settlement_initiate_success(self, client: AsyncClient):
        audit.clear_log()
        response = await client.post(
            "/api/v1/settlement/initiate",
            json={
                "destination_bank": "JPM-CARI-001",
                "originator_address": "0xORIGINATOR",
                "beneficiary_address": "0xBENEFICIARY",
                "amount_usd": 50000.0,
                "originator_name": "John Doe",
                "beneficiary_name": "Jane Smith",
                "originator_institution": "M&T Bank",
                "beneficiary_institution": "JPMorgan Chase",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["tx_type"] == "SETTLEMENT_INITIATE"
        assert data["status"] == "CONFIRMED"
        assert data["amount_usd"] == 50000.0
        assert "SETTLE-" in data["reference_id"]
        assert data["tx_hash"] is not None

    @pytest.mark.asyncio
    async def test_settlement_below_travel_rule_threshold(self, client: AsyncClient):
        """Settlement below $3,000 should still succeed (no Travel Rule hash needed)."""
        audit.clear_log()
        response = await client.post(
            "/api/v1/settlement/initiate",
            json={
                "destination_bank": "WF-CARI-002",
                "originator_address": "0xSMALL_ORIG",
                "beneficiary_address": "0xSMALL_BENEF",
                "amount_usd": 1500.0,
                "originator_name": "Alice",
                "beneficiary_name": "Bob",
                "originator_institution": "M&T Bank",
                "beneficiary_institution": "Wells Fargo",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "CONFIRMED"

    @pytest.mark.asyncio
    async def test_settlement_missing_beneficiary_institution(self, client: AsyncClient):
        response = await client.post(
            "/api/v1/settlement/initiate",
            json={
                "destination_bank": "XYZ",
                "originator_address": "0xA",
                "beneficiary_address": "0xB",
                "amount_usd": 100.0,
                "originator_name": "A",
                "beneficiary_name": "B",
            },
        )
        assert response.status_code == 422  # Missing required field
