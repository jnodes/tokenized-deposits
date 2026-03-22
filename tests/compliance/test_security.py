"""
Tests for HSM key management and signing policy engine.
"""

from __future__ import annotations

import pytest

from offchain.services import audit
from security.key_management.hsm import (
    KeyLifecycleManager,
    KeyRole,
    KeyStatus,
    StubHSMBackend,
)
from security.signing.policy_engine import (
    ApprovalStatus,
    RiskTier,
    SigningPolicyEngine,
)


class TestHSMKeyManagement:
    """Tests for HSM key lifecycle."""

    @pytest.mark.asyncio
    async def test_generate_key(self):
        audit.clear_log()
        backend = StubHSMBackend()
        meta = await backend.generate_key(KeyRole.MINTER)
        assert meta.role == KeyRole.MINTER
        assert meta.status == KeyStatus.ACTIVE
        assert len(meta.public_key_hash) == 64

    @pytest.mark.asyncio
    async def test_provision_all_roles(self):
        audit.clear_log()
        manager = KeyLifecycleManager()
        keys = await manager.provision_all_roles()
        assert len(keys) == len(KeyRole)
        roles = {k.value for k in keys.keys()}
        assert "MINTER" in roles
        assert "BURNER" in roles
        assert "ATTESTOR" in roles

    @pytest.mark.asyncio
    async def test_sign_with_key(self):
        audit.clear_log()
        backend = StubHSMBackend()
        meta = await backend.generate_key(KeyRole.MINTER)
        sig = await backend.sign(meta.key_id, b"test_message_hash")
        assert len(sig) == 32  # HMAC-SHA256

    @pytest.mark.asyncio
    async def test_sign_revoked_key_fails(self):
        audit.clear_log()
        backend = StubHSMBackend()
        meta = await backend.generate_key(KeyRole.MINTER)
        await backend.revoke_key(meta.key_id, "test revocation")
        with pytest.raises(ValueError, match="REVOKED"):
            await backend.sign(meta.key_id, b"should_fail")

    @pytest.mark.asyncio
    async def test_rotate_key(self):
        audit.clear_log()
        backend = StubHSMBackend()
        old_meta = await backend.generate_key(KeyRole.BURNER)
        new_meta = await backend.rotate_key(old_meta.key_id, approved_by=["admin_1"])
        assert new_meta.role == KeyRole.BURNER
        assert new_meta.rotation_count == 1
        assert new_meta.key_id != old_meta.key_id

    @pytest.mark.asyncio
    async def test_destroy_key_requires_dual_control(self):
        audit.clear_log()
        backend = StubHSMBackend()
        meta = await backend.generate_key(KeyRole.ADMIN)
        with pytest.raises(ValueError, match="2 approvals"):
            await backend.destroy_key(meta.key_id, approved_by=["single_admin"])

    @pytest.mark.asyncio
    async def test_destroy_key_with_dual_control(self):
        audit.clear_log()
        backend = StubHSMBackend()
        meta = await backend.generate_key(KeyRole.ADMIN)
        await backend.destroy_key(meta.key_id, approved_by=["admin_1", "admin_2"])
        assert meta.status == KeyStatus.DESTROYED


class TestSigningPolicyEngine:
    """Tests for signing policy and dual control."""

    @pytest.mark.asyncio
    async def test_risk_classification(self):
        engine = SigningPolicyEngine()
        assert engine.classify_risk(5_000, "MINT") == RiskTier.LOW
        assert engine.classify_risk(50_000, "MINT") == RiskTier.MEDIUM
        assert engine.classify_risk(5_000_000, "MINT") == RiskTier.HIGH
        assert engine.classify_risk(50_000_000, "MINT") == RiskTier.CRITICAL

    @pytest.mark.asyncio
    async def test_critical_operations_always_high(self):
        engine = SigningPolicyEngine()
        assert engine.classify_risk(100, "PAUSE") == RiskTier.HIGH
        assert engine.classify_risk(0, "UPGRADE") == RiskTier.HIGH
        assert engine.classify_risk(0, "KEY_ROTATION") == RiskTier.HIGH

    @pytest.mark.asyncio
    async def test_single_approval_low_risk(self):
        audit.clear_log()
        engine = SigningPolicyEngine()
        request = await engine.create_signing_request(
            operation="MINT",
            role_required=KeyRole.MINTER,
            amount_usd=5_000,
            requestor="operator_1",
        )
        assert request.approvals_required == 1
        assert request.time_lock_until is None

        # Approve
        approved = await engine.approve(request.request_id, "approver_1")
        assert approved.status == ApprovalStatus.APPROVED

        # Execute
        executed = await engine.execute(request.request_id)
        assert executed.status == ApprovalStatus.EXECUTED

    @pytest.mark.asyncio
    async def test_dual_approval_medium_risk(self):
        audit.clear_log()
        engine = SigningPolicyEngine()
        request = await engine.create_signing_request(
            operation="MINT",
            role_required=KeyRole.MINTER,
            amount_usd=500_000,
            requestor="operator_1",
        )
        assert request.approvals_required == 2

        # Single approval not enough
        await engine.approve(request.request_id, "approver_1")
        assert request.status == ApprovalStatus.PENDING

        # Second approval completes
        await engine.approve(request.request_id, "approver_2")
        assert request.status == ApprovalStatus.APPROVED

    @pytest.mark.asyncio
    async def test_self_approval_blocked(self):
        audit.clear_log()
        engine = SigningPolicyEngine()
        request = await engine.create_signing_request(
            operation="BURN",
            role_required=KeyRole.BURNER,
            amount_usd=1_000,
            requestor="operator_1",
        )
        with pytest.raises(ValueError, match="Self-approval is prohibited"):
            await engine.approve(request.request_id, "operator_1")

    @pytest.mark.asyncio
    async def test_duplicate_approval_blocked(self):
        audit.clear_log()
        engine = SigningPolicyEngine()
        request = await engine.create_signing_request(
            operation="MINT",
            role_required=KeyRole.MINTER,
            amount_usd=500_000,
            requestor="operator_1",
        )
        await engine.approve(request.request_id, "approver_1")
        with pytest.raises(ValueError, match="already approved"):
            await engine.approve(request.request_id, "approver_1")

    @pytest.mark.asyncio
    async def test_rejection(self):
        audit.clear_log()
        engine = SigningPolicyEngine()
        request = await engine.create_signing_request(
            operation="SETTLEMENT",
            role_required=KeyRole.SETTLEMENT,
            amount_usd=10_000,
            requestor="operator_1",
        )
        rejected = await engine.reject(request.request_id, "compliance_officer", "Suspicious")
        assert rejected.status == ApprovalStatus.REJECTED

    @pytest.mark.asyncio
    async def test_time_lock_enforcement(self):
        audit.clear_log()
        engine = SigningPolicyEngine()
        request = await engine.create_signing_request(
            operation="MINT",
            role_required=KeyRole.MINTER,
            amount_usd=5_000_000,  # HIGH risk -> 1h time-lock
            requestor="operator_1",
        )
        assert request.time_lock_until is not None

        # Approve
        await engine.approve(request.request_id, "approver_1")
        await engine.approve(request.request_id, "approver_2")

        # Execute should fail due to time-lock
        with pytest.raises(ValueError, match="Time-lock active"):
            await engine.execute(request.request_id)
