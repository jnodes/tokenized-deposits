"""
Tests for compliance service and health endpoints.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from offchain.main import create_app
from offchain.models.schemas import ComplianceStatus
from offchain.services import audit
from offchain.services.compliance import ComplianceService


@pytest.fixture
def app():
    return create_app()


@pytest.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestComplianceService:
    """Unit tests for the compliance service."""

    @pytest.mark.asyncio
    async def test_screen_address_passed(self):
        audit.clear_log()
        svc = ComplianceService()
        result = await svc.screen_address("0xCLEAN_ADDRESS")
        assert result.status == ComplianceStatus.PASSED

    @pytest.mark.asyncio
    async def test_screen_transaction(self):
        audit.clear_log()
        svc = ComplianceService()
        result = await svc.screen_transaction(
            from_addr="0xSENDER",
            to_addr="0xRECEIVER",
            amount_usd=5000.0,
        )
        assert result.status == ComplianceStatus.PASSED
        assert result.travel_rule_required is True  # >= $3000

    @pytest.mark.asyncio
    async def test_screen_below_travel_rule(self):
        audit.clear_log()
        svc = ComplianceService()
        result = await svc.screen_transaction(
            from_addr="0xA",
            to_addr="0xB",
            amount_usd=1000.0,
        )
        assert result.travel_rule_required is False

    @pytest.mark.asyncio
    async def test_travel_rule_hash(self):
        svc = ComplianceService()
        orig_hash, benef_hash, combined = await svc.compute_travel_rule_hash(
            originator_name="John Doe",
            originator_institution="the Issuing Bank",
            beneficiary_name="Jane Smith",
            beneficiary_institution="JPMorgan Chase",
        )
        assert len(orig_hash) == 32  # SHA-256 raw bytes
        assert len(benef_hash) == 32
        assert len(combined) == 32
        # Deterministic
        _, _, combined2 = await svc.compute_travel_rule_hash(
            originator_name="John Doe",
            originator_institution="the Issuing Bank",
            beneficiary_name="Jane Smith",
            beneficiary_institution="JPMorgan Chase",
        )
        assert combined == combined2


class TestHealthEndpoint:
    """Tests for system health check."""

    @pytest.mark.asyncio
    async def test_health(self, client: AsyncClient):
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "1.0.0"

    @pytest.mark.asyncio
    async def test_healthz(self, client: AsyncClient):
        response = await client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_root(self, client: AsyncClient):
        response = await client.get("/api/v1/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data


class TestComplianceRouter:
    """Integration tests for compliance API endpoints."""

    @pytest.mark.asyncio
    async def test_screen_address_endpoint(self, client: AsyncClient):
        audit.clear_log()
        response = await client.get("/api/v1/compliance/screen/0xTEST_ADDR")
        assert response.status_code == 200
        data = response.json()
        assert data["address"] == "0xTEST_ADDR"
        assert data["status"] == "PASSED"

    @pytest.mark.asyncio
    async def test_audit_endpoint(self, client: AsyncClient):
        audit.clear_log()
        # Generate some audit entries
        await audit.record(actor="TEST", action="test_action", resource="test_resource")
        response = await client.get("/api/v1/compliance/audit")
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
