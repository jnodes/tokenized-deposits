"""
Tests for risk matrix, control matrix, resilience, and incident response.
"""

from __future__ import annotations

import pytest

from offchain.models.schemas import CustodyTier
from offchain.services import audit
from risk.risk_matrix_generator.generator import (
    RiskCategory,
    RiskLevel,
    RiskMatrixGenerator,
)
from risk.control_matrix.matrix import ControlMatrix, ControlStatus, TestResult
from risk.incident_response.manager import IncidentResponseManager
from security.resilience.dr_manager import (
    CircuitBreaker,
    CircuitState,
    IncidentSeverity,
    IncidentStatus,
    ResilienceManager,
)
from security.wallet_tiering.strategy import WalletTieringEngine, RebalanceAction


class TestRiskMatrix:
    """Tests for risk register and scoring."""

    def test_baseline_risks_populated(self):
        matrix = RiskMatrixGenerator()
        risks = matrix.get_all_risks()
        assert len(risks) == 8

    def test_risk_scoring(self):
        matrix = RiskMatrixGenerator()
        risks = matrix.get_all_risks()
        for risk in risks:
            assert risk.inherent_score == risk.inherent_likelihood.value * risk.inherent_impact.value
            assert risk.residual_score == risk.residual_likelihood.value * risk.residual_impact.value
            assert risk.inherent_score >= risk.residual_score

    def test_risk_by_category(self):
        matrix = RiskMatrixGenerator()
        compliance_risks = matrix.get_risks_by_category(RiskCategory.COMPLIANCE)
        assert len(compliance_risks) >= 2
        cyber_risks = matrix.get_risks_by_category(RiskCategory.CYBERSECURITY)
        assert len(cyber_risks) >= 1

    def test_risk_summary(self):
        matrix = RiskMatrixGenerator()
        summary = matrix.get_risk_summary()
        assert summary["total_risks"] == 8
        assert summary["avg_control_effectiveness"] > 80.0

    @pytest.mark.asyncio
    async def test_csv_export(self):
        audit.clear_log()
        matrix = RiskMatrixGenerator()
        csv_data = await matrix.export_csv()
        assert "Risk ID" in csv_data
        assert "Private Key Compromise" in csv_data
        assert "CYBERSECURITY" in csv_data
        lines = csv_data.strip().split("\n")
        assert len(lines) == 9  # header + 8 risks


class TestControlMatrix:
    """Tests for regulatory control matrix."""

    def test_controls_populated(self):
        matrix = ControlMatrix()
        controls = matrix.get_all_controls()
        assert len(controls) == 16

    def test_all_controls_implemented(self):
        matrix = ControlMatrix()
        controls = matrix.get_all_controls()
        for ctrl in controls:
            assert ctrl.status == ControlStatus.IMPLEMENTED

    def test_all_controls_tested(self):
        matrix = ControlMatrix()
        controls = matrix.get_all_controls()
        for ctrl in controls:
            assert ctrl.test_result == TestResult.PASSED

    def test_genius_act_controls(self):
        matrix = ControlMatrix()
        genius = matrix.get_controls_by_regulation("GENIUS")
        assert len(genius) == 5  # S4, S5, S6, S7, S8

    def test_nydfs_controls(self):
        matrix = ControlMatrix()
        nydfs = matrix.get_controls_by_regulation("NYDFS")
        assert len(nydfs) >= 7

    def test_control_summary(self):
        matrix = ControlMatrix()
        summary = matrix.get_control_summary()
        assert summary["total_controls"] == 16
        assert summary["implemented"] == 16
        assert summary["implementation_rate_pct"] == 100.0
        assert summary["test_pass_rate_pct"] == 100.0
        assert summary["avg_effectiveness_pct"] > 85.0

    @pytest.mark.asyncio
    async def test_csv_export(self):
        audit.clear_log()
        matrix = ControlMatrix()
        csv_data = await matrix.export_csv()
        assert "Regulation" in csv_data
        assert "GENIUS Act" in csv_data
        assert "NYDFS" in csv_data


class TestCircuitBreaker:
    """Tests for circuit breaker pattern."""

    @pytest.mark.asyncio
    async def test_starts_closed(self):
        cb = CircuitBreaker("test_service")
        assert cb.state == CircuitState.CLOSED
        assert cb.is_available() is True

    @pytest.mark.asyncio
    async def test_opens_after_threshold(self):
        audit.clear_log()
        cb = CircuitBreaker("test_service", failure_threshold=3)
        for _ in range(3):
            await cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.is_available() is False

    @pytest.mark.asyncio
    async def test_resets_on_success(self):
        cb = CircuitBreaker("test_service", failure_threshold=3)
        await cb.record_failure()
        await cb.record_failure()
        await cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestResilienceManager:
    """Tests for DR playbooks and incident management."""

    def test_playbooks_initialized(self):
        manager = ResilienceManager()
        playbooks = manager.get_all_playbooks()
        assert len(playbooks) == 4
        scenarios = {p.scenario for p in playbooks}
        assert "HSM Primary Failure" in scenarios
        assert "Private Key Compromise Suspected" in scenarios

    @pytest.mark.asyncio
    async def test_create_incident(self):
        audit.clear_log()
        manager = ResilienceManager()
        incident = await manager.create_incident(
            title="Test Incident",
            severity=IncidentSeverity.P3_MEDIUM,
            component="test",
            reported_by="test_user",
        )
        assert incident.status == IncidentStatus.OPEN
        assert incident.regulatory_notification_required is False

    @pytest.mark.asyncio
    async def test_critical_incident_flags_notification(self):
        audit.clear_log()
        manager = ResilienceManager()
        incident = await manager.create_incident(
            title="Key Compromise",
            severity=IncidentSeverity.P1_CRITICAL,
            component="hsm",
        )
        assert incident.regulatory_notification_required is True

    @pytest.mark.asyncio
    async def test_incident_lifecycle(self):
        audit.clear_log()
        manager = ResilienceManager()
        incident = await manager.create_incident(
            title="Test",
            severity=IncidentSeverity.P4_LOW,
        )
        updated = await manager.update_incident(
            incident.incident_id,
            status=IncidentStatus.INVESTIGATING,
            notes="Looking into it",
            by="analyst",
        )
        assert updated.status == IncidentStatus.INVESTIGATING
        resolved = await manager.update_incident(
            incident.incident_id,
            status=IncidentStatus.RESOLVED,
            by="analyst",
        )
        assert resolved.status == IncidentStatus.RESOLVED
        assert resolved.resolved_at is not None


class TestIncidentResponseManager:
    """Tests for extended incident response with playbook execution."""

    @pytest.mark.asyncio
    async def test_create_and_respond(self):
        audit.clear_log()
        manager = IncidentResponseManager()
        incident, execution = await manager.create_and_respond(
            title="HSM Down",
            severity=IncidentSeverity.P2_HIGH,
            component="hsm",
            playbook_scenario="hsm_failure",
            reported_by="monitoring",
        )
        assert incident is not None
        assert execution is not None
        assert execution.steps_total == 6

    @pytest.mark.asyncio
    async def test_p1_creates_regulatory_notification(self):
        audit.clear_log()
        manager = IncidentResponseManager()
        await manager.create_and_respond(
            title="Key Compromise",
            severity=IncidentSeverity.P1_CRITICAL,
            component="keys",
        )
        notifications = manager.get_notifications(status="PENDING")
        assert len(notifications) >= 1
        assert notifications[0].regulator == "NYDFS"


class TestWalletTiering:
    """Tests for wallet tiering strategy engine."""

    @pytest.mark.asyncio
    async def test_hot_below_watermark_triggers_refill(self):
        audit.clear_log()
        engine = WalletTieringEngine()
        recommendations = await engine.evaluate({
            CustodyTier.HOT: 100_000.0,  # Below low watermark (200K)
            CustodyTier.WARM: 5_000_000.0,
            CustodyTier.COLD: 50_000_000.0,
        })
        assert len(recommendations) >= 1
        refill = recommendations[0]
        assert refill.to_tier == CustodyTier.HOT

    @pytest.mark.asyncio
    async def test_hot_above_watermark_triggers_drain(self):
        audit.clear_log()
        engine = WalletTieringEngine()
        recommendations = await engine.evaluate({
            CustodyTier.HOT: 900_000.0,  # Above high watermark (800K)
            CustodyTier.WARM: 5_000_000.0,
            CustodyTier.COLD: 50_000_000.0,
        })
        drain = [r for r in recommendations if r.from_tier == CustodyTier.HOT]
        assert len(drain) >= 1

    @pytest.mark.asyncio
    async def test_balanced_no_action(self):
        audit.clear_log()
        engine = WalletTieringEngine()
        recommendations = await engine.evaluate({
            CustodyTier.HOT: 500_000.0,
            CustodyTier.WARM: 5_000_000.0,
            CustodyTier.COLD: 50_000_000.0,
        })
        assert len(recommendations) == 0

    @pytest.mark.asyncio
    async def test_record_rebalance(self):
        audit.clear_log()
        engine = WalletTieringEngine()
        event = await engine.record_rebalance(
            from_tier=CustodyTier.COLD,
            to_tier=CustodyTier.HOT,
            amount_usd=100_000.0,
            reason="Low watermark trigger",
            approved_by=["ops_1"],
        )
        assert event.from_tier == CustodyTier.COLD
        assert engine.get_history()
