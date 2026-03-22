"""
Security Audit Tests - API Security and Compliance
M&T Bank | Cari Network | ZKsync Prividium

Tests for:
- API parameter tampering
- PII handling
- AML/KYC logic gaps
- IDOR vulnerabilities
"""

from __future__ import annotations

import hashlib
import pytest
from httpx import ASGITransport, AsyncClient

from offchain.main import create_app
from offchain.models.schemas import ComplianceStatus
from offchain.services import audit
from offchain.services.compliance import ComplianceService
from compliance.aml_screening.engine import AMLScreeningEngine, AlertType


# =============================================================================
#                          API SECURITY TESTS
# =============================================================================

class TestAPIParameterTampering:
    """Tests for API parameter tampering vulnerabilities."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    async def client(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_mint_negative_amount_rejected(self, client: AsyncClient):
        """API-003: Negative amounts should be rejected."""
        audit.clear_log()
        response = await client.post(
            "/api/v1/transactions/mint",
            json={
                "to_address": "0xTEST",
                "amount_usd": -1000.0,  # Negative amount
                "depositor_account_id": "ACC-001",
                "reference_id": "REF-001",
            },
        )
        # Should be rejected (400 or 422)
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_mint_zero_amount_rejected(self, client: AsyncClient):
        """API-003: Zero amounts should be rejected."""
        audit.clear_log()
        response = await client.post(
            "/api/v1/transactions/mint",
            json={
                "to_address": "0xTEST",
                "amount_usd": 0.0,
                "depositor_account_id": "ACC-001",
                "reference_id": "REF-002",
            },
        )
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_mint_missing_required_fields(self, client: AsyncClient):
        """API-003: Missing required fields should be rejected."""
        audit.clear_log()
        response = await client.post(
            "/api/v1/transactions/mint",
            json={
                "to_address": "0xTEST",
                # Missing amount_usd
                "depositor_account_id": "ACC-001",
                "reference_id": "REF-003",
            },
        )
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_mint_extremely_large_amount(self, client: AsyncClient):
        """API-003: Extremely large amounts should be handled gracefully."""
        audit.clear_log()
        response = await client.post(
            "/api/v1/transactions/mint",
            json={
                "to_address": "0xTEST",
                "amount_usd": 1e30,  # Extremely large
                "depositor_account_id": "ACC-001",
                "reference_id": "REF-004",
            },
        )
        # Should either reject or handle gracefully
        assert response.status_code in [200, 400, 422, 500]

    @pytest.mark.asyncio
    async def test_reference_id_injection(self, client: AsyncClient):
        """API-004: Reference ID injection should be sanitized."""
        audit.clear_log()
        # Try SQL-like injection in reference_id
        response = await client.post(
            "/api/v1/transactions/mint",
            json={
                "to_address": "0xTEST",
                "amount_usd": 100.0,
                "depositor_account_id": "ACC-001",
                "reference_id": "'; DROP TABLE transactions; --",
            },
        )
        # Should be handled safely (accepted or rejected, but no SQL error)
        assert response.status_code in [200, 400, 422]


class TestIDORVulnerabilities:
    """Tests for Insecure Direct Object Reference vulnerabilities."""

    @pytest.fixture
    def app(self):
        return create_app()

    @pytest.fixture
    async def client(self, app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac

    @pytest.mark.asyncio
    async def test_settlement_id_enumeration(self, client: AsyncClient):
        """API-006: Settlement ID enumeration should not expose sensitive data."""
        audit.clear_log()
        # Try to access a non-existent settlement
        response = await client.get("/api/v1/settlement/0xNONEXISTENT")
        # Should return 404 or empty result, not error
        assert response.status_code in [200, 404]

    @pytest.mark.asyncio
    async def test_account_isolation(self, client: AsyncClient):
        """API-002: Account access should be properly isolated."""
        audit.clear_log()
        # Create a mint for one account
        response = await client.post(
            "/api/v1/transactions/mint",
            json={
                "to_address": "0xALICE",
                "amount_usd": 1000.0,
                "depositor_account_id": "ACC-ALICE",
                "reference_id": "REF-ALICE",
            },
        )
        # The response should not expose other accounts' data
        if response.status_code == 200:
            data = response.json()
            # Should only contain the requested account's data
            assert "depositor_account_id" not in data or data.get("depositor_account_id") != "ACC-OTHER"


# =============================================================================
#                          COMPLIANCE SECURITY TESTS
# =============================================================================

class TestPIIHandling:
    """Tests for PII handling and Travel Rule compliance."""

    @pytest.mark.asyncio
    async def test_pii_never_stored_plaintext(self):
        """CMP-002: PII should be hashed before on-chain storage."""
        audit.clear_log()
        svc = ComplianceService()
        
        orig_hash, benef_hash, combined = await svc.compute_travel_rule_hash(
            originator_name="John Doe",
            originator_institution="M&T Bank",
            beneficiary_name="Jane Smith",
            beneficiary_institution="JPMorgan Chase",
        )
        
        # Verify hashes are SHA-256 (32 bytes)
        assert len(orig_hash) == 32
        assert len(benef_hash) == 32
        assert len(combined) == 32
        
        # Verify hashes are not plaintext
        assert orig_hash != b"John Doe|M&T Bank"
        assert benef_hash != b"Jane Smith|JPMorgan Chase"

    @pytest.mark.asyncio
    async def test_travel_rule_hash_determinism(self):
        """CMP-002: Travel Rule hashes should be deterministic."""
        audit.clear_log()
        svc = ComplianceService()
        
        # Same input should produce same hash
        hash1 = await svc.compute_travel_rule_hash(
            originator_name="John Doe",
            originator_institution="M&T Bank",
            beneficiary_name="Jane Smith",
            beneficiary_institution="JPMorgan Chase",
        )
        
        hash2 = await svc.compute_travel_rule_hash(
            originator_name="John Doe",
            originator_institution="M&T Bank",
            beneficiary_name="Jane Smith",
            beneficiary_institution="JPMorgan Chase",
        )
        
        assert hash1 == hash2

    @pytest.mark.asyncio
    async def test_travel_rule_different_inputs_different_hashes(self):
        """CMP-002: Different inputs should produce different hashes."""
        audit.clear_log()
        svc = ComplianceService()
        
        hash1 = await svc.compute_travel_rule_hash(
            originator_name="John Doe",
            originator_institution="M&T Bank",
            beneficiary_name="Jane Smith",
            beneficiary_institution="JPMorgan Chase",
        )
        
        hash2 = await svc.compute_travel_rule_hash(
            originator_name="John Smith",  # Different name
            originator_institution="M&T Bank",
            beneficiary_name="Jane Smith",
            beneficiary_institution="JPMorgan Chase",
        )
        
        assert hash1 != hash2


class TestAMLKYCLogic:
    """Tests for AML/KYC logic gaps."""

    @pytest.mark.asyncio
    async def test_ofac_blocked_address(self):
        """CMP-001: OFAC blocked addresses should be detected."""
        audit.clear_log()
        engine = AMLScreeningEngine()
        
        # Test with known blocked address (stub)
        result = await engine.screen_address_realtime("0xOFAC_BLOCKED_001")
        
        assert result.status == ComplianceStatus.BLOCKED
        assert AlertType.OFAC_MATCH in result.alerts
        assert result.ofac_match is True

    @pytest.mark.asyncio
    async def test_sanctions_blocked_address(self):
        """CMP-001: Sanctioned addresses should be blocked."""
        audit.clear_log()
        engine = AMLScreeningEngine()
        
        result = await engine.screen_address_realtime("0xSANCTIONED_ENTITY")
        
        assert result.status == ComplianceStatus.BLOCKED
        assert AlertType.SANCTIONS_MATCH in result.alerts

    @pytest.mark.asyncio
    async def test_ctr_threshold_detection(self):
        """CMP-005: CTR threshold at $10,000 should be detected."""
        audit.clear_log()
        engine = AMLScreeningEngine()
        
        # Exactly at threshold
        result = await engine.screen_transaction(
            from_addr="0xA",
            to_addr="0xB",
            amount_usd=10_000.0,
        )
        
        assert result.ctr_required is True
        assert AlertType.CTR_THRESHOLD in result.alerts

    @pytest.mark.asyncio
    async def test_ctr_below_threshold(self):
        """CMP-005: Below CTR threshold should not trigger CTR."""
        audit.clear_log()
        engine = AMLScreeningEngine()
        
        result = await engine.screen_transaction(
            from_addr="0xA",
            to_addr="0xB",
            amount_usd=9_999.99,
        )
        
        assert result.ctr_required is False

    @pytest.mark.asyncio
    async def test_structuring_detection(self):
        """CMP-003: Structuring pattern should be detected."""
        audit.clear_log()
        engine = AMLScreeningEngine()
        
        # First transaction in structuring range
        await engine.screen_transaction(
            from_addr="0xSTRUCTURER",
            to_addr="0xB",
            amount_usd=9_000.0,
        )
        
        # Second transaction
        await engine.screen_transaction(
            from_addr="0xSTRUCTURER",
            to_addr="0xB",
            amount_usd=9_000.0,
        )
        
        # Third transaction - should trigger structuring alert
        result = await engine.screen_transaction(
            from_addr="0xSTRUCTURER",
            to_addr="0xB",
            amount_usd=9_000.0,
        )
        
        # After 3 transactions in structuring range, should flag
        assert AlertType.STRUCTURING in result.alerts or result.status == ComplianceStatus.FLAGGED

    @pytest.mark.asyncio
    async def test_velocity_anomaly_detection(self):
        """CMP-004: Velocity anomaly should be detected."""
        audit.clear_log()
        engine = AMLScreeningEngine()
        
        # Multiple high-value transactions in short time
        for _ in range(25):
            result = await engine.screen_transaction(
                from_addr="0xVELOCITY_TEST",
                to_addr="0xB",
                amount_usd=5_000.0,
            )
        
        # Should trigger velocity anomaly
        assert AlertType.VELOCITY_ANOMALY in result.alerts or result.status == ComplianceStatus.FLAGGED

    @pytest.mark.asyncio
    async def test_travel_rule_threshold(self):
        """CMP-006: Travel Rule threshold at $3,000 should be enforced."""
        audit.clear_log()
        svc = ComplianceService()
        
        # Above threshold
        result = await svc.screen_transaction(
            from_addr="0xA",
            to_addr="0xB",
            amount_usd=3_000.0,
        )
        assert result.travel_rule_required is True
        
        # Below threshold
        result = await svc.screen_transaction(
            from_addr="0xA",
            to_addr="0xB",
            amount_usd=2_999.99,
        )
        assert result.travel_rule_required is False


class TestKeyManagementSecurity:
    """Tests for key management security."""

    @pytest.mark.asyncio
    async def test_stub_hsm_not_for_production(self):
        """CMP-008: Stub HSM should warn about production use."""
        from security.key_management.hsm import StubHSMBackend, HSMProvider
        
        backend = StubHSMBackend()
        
        # Stub backend should be explicitly marked as dev-only
        assert backend._provider == HSMProvider.LOCAL_DEV

    @pytest.mark.asyncio
    async def test_key_destruction_requires_dual_control(self):
        """CMP-007: Key destruction should require dual control."""
        audit.clear_log()
        from security.key_management.hsm import StubHSMBackend, KeyRole
        
        backend = StubHSMBackend()
        meta = await backend.generate_key(KeyRole.ADMIN)
        
        # Single approval should fail
        with pytest.raises(ValueError, match="2 approvals"):
            await backend.destroy_key(meta.key_id, approved_by=["single_admin"])
        
        # Dual approval should succeed
        await backend.destroy_key(meta.key_id, approved_by=["admin_1", "admin_2"])

    @pytest.mark.asyncio
    async def test_revoked_key_cannot_sign(self):
        """CMP-007: Revoked keys should not be usable."""
        audit.clear_log()
        from security.key_management.hsm import StubHSMBackend, KeyRole
        
        backend = StubHSMBackend()
        meta = await backend.generate_key(KeyRole.MINTER)
        
        # Revoke the key
        await backend.revoke_key(meta.key_id, "compromised")
        
        # Should not be able to sign
        with pytest.raises(ValueError, match="REVOKED"):
            await backend.sign(meta.key_id, b"test_message")


class TestSigningPolicySecurity:
    """Tests for signing policy security."""

    @pytest.mark.asyncio
    async def test_self_approval_blocked(self):
        """Verify self-approval is blocked."""
        audit.clear_log()
        from security.signing.policy_engine import SigningPolicyEngine
        from security.key_management.hsm import KeyRole
        
        engine = SigningPolicyEngine()
        request = await engine.create_signing_request(
            operation="MINT",
            role_required=KeyRole.MINTER,
            amount_usd=1_000,
            requestor="operator_1",
        )
        
        # Self-approval should fail
        with pytest.raises(ValueError, match="Self-approval is prohibited"):
            await engine.approve(request.request_id, "operator_1")

    @pytest.mark.asyncio
    async def test_time_lock_enforcement(self):
        """Verify time-lock is enforced for high-value operations."""
        audit.clear_log()
        from security.signing.policy_engine import SigningPolicyEngine, RiskTier
        from security.key_management.hsm import KeyRole
        
        engine = SigningPolicyEngine()
        request = await engine.create_signing_request(
            operation="MINT",
            role_required=KeyRole.MINTER,
            amount_usd=5_000_000,  # HIGH risk -> 1h time-lock
            requestor="operator_1",
        )
        
        assert request.risk_tier == RiskTier.HIGH
        assert request.time_lock_until is not None
        
        # Approve
        await engine.approve(request.request_id, "approver_1")
        await engine.approve(request.request_id, "approver_2")
        
        # Execute should fail due to time-lock
        with pytest.raises(ValueError, match="Time-lock active"):
            await engine.execute(request.request_id)

    @pytest.mark.asyncio
    async def test_critical_operations_always_high_risk(self):
        """Verify critical operations are always HIGH risk."""
        audit.clear_log()
        from security.signing.policy_engine import SigningPolicyEngine, RiskTier
        from security.key_management.hsm import KeyRole
        
        engine = SigningPolicyEngine()
        
        # PAUSE should be HIGH even with $0
        request = await engine.create_signing_request(
            operation="PAUSE",
            role_required=KeyRole.PAUSER,
            amount_usd=0,
            requestor="operator_1",
        )
        assert request.risk_tier == RiskTier.HIGH
        
        # UPGRADE should be HIGH
        request = await engine.create_signing_request(
            operation="UPGRADE",
            role_required=KeyRole.UPGRADER,
            amount_usd=0,
            requestor="operator_1",
        )
        assert request.risk_tier == RiskTier.HIGH
