"""
Tests for Cari Network Rulebook compliance engine.

Verifies that the RulebookComplianceEngine stub implementation correctly
returns PASS results for all compliance checks per the Cari Network Whitepaper.
"""

import pytest

from compliance.rulebook.engine import (
    RulebookComplianceEngine,
    RulebookCheckStatus,
    RulebookCheckResult,
    get_rulebook_engine,
)


class TestRulebookComplianceEngine:
    """Test suite for the RulebookComplianceEngine class."""

    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.engine = RulebookComplianceEngine()

    def test_check_member_obligations(self):
        """Test member obligations compliance check returns PASS."""
        result = self.engine.check_member_obligations()
        
        assert isinstance(result, RulebookCheckResult)
        assert result.status == RulebookCheckStatus.PASS
        assert result.check_name == "member_obligations"
        assert "STUB" in result.details
        assert result.checked_at is not None

    def test_check_governance_compliance(self):
        """Test governance compliance check returns PASS."""
        result = self.engine.check_governance_compliance()
        
        assert isinstance(result, RulebookCheckResult)
        assert result.status == RulebookCheckStatus.PASS
        assert result.check_name == "governance_compliance"
        assert "STUB" in result.details

    def test_check_data_sharing_standards(self):
        """Test data sharing standards check returns PASS."""
        result = self.engine.check_data_sharing_standards()
        
        assert isinstance(result, RulebookCheckResult)
        assert result.status == RulebookCheckStatus.PASS
        assert result.check_name == "data_sharing_standards"
        assert "STUB" in result.details

    def test_check_dispute_resolution_readiness(self):
        """Test dispute resolution readiness check returns PASS."""
        result = self.engine.check_dispute_resolution_readiness()
        
        assert isinstance(result, RulebookCheckResult)
        assert result.status == RulebookCheckStatus.PASS
        assert result.check_name == "dispute_resolution"
        assert "STUB" in result.details

    def test_check_onboarding_offboarding(self):
        """Test onboarding/offboarding procedures check returns PASS."""
        result = self.engine.check_onboarding_offboarding()
        
        assert isinstance(result, RulebookCheckResult)
        assert result.status == RulebookCheckStatus.PASS
        assert result.check_name == "onboarding_offboarding"
        assert "STUB" in result.details

    def test_run_all_checks(self):
        """Test run_all_checks returns 5 PASS results."""
        results = self.engine.run_all_checks()
        
        assert len(results) == 5
        assert all(isinstance(r, RulebookCheckResult) for r in results)
        assert all(r.status == RulebookCheckStatus.PASS for r in results)
        
        # Verify all expected checks are included
        check_names = {r.check_name for r in results}
        expected_checks = {
            "member_obligations",
            "governance_compliance",
            "data_sharing_standards",
            "dispute_resolution",
            "onboarding_offboarding",
        }
        assert check_names == expected_checks

    def test_run_all_checks_includes_timestamps(self):
        """Test that all results include valid timestamps."""
        results = self.engine.run_all_checks()
        
        for result in results:
            assert result.checked_at is not None
            # ISO format timestamp should contain 'T' separator
            assert "T" in result.checked_at or "-" in result.checked_at


class TestRulebookEngineSingleton:
    """Test suite for the singleton factory function."""

    def test_singleton_factory(self):
        """Test get_rulebook_engine returns the same instance."""
        # Clear cache to ensure fresh test
        get_rulebook_engine.cache_clear()
        
        engine1 = get_rulebook_engine()
        engine2 = get_rulebook_engine()
        
        assert engine1 is engine2
        assert isinstance(engine1, RulebookComplianceEngine)

    def test_singleton_returns_valid_engine(self):
        """Test singleton engine can run all checks."""
        get_rulebook_engine.cache_clear()
        
        engine = get_rulebook_engine()
        results = engine.run_all_checks()
        
        assert len(results) == 5
        assert all(r.status == RulebookCheckStatus.PASS for r in results)


class TestRulebookCheckStatus:
    """Test suite for RulebookCheckStatus enum."""

    def test_status_values(self):
        """Test all expected status values exist."""
        assert RulebookCheckStatus.PASS.value == "pass"
        assert RulebookCheckStatus.FAIL.value == "fail"
        assert RulebookCheckStatus.PENDING.value == "pending"

    def test_status_is_string_enum(self):
        """Test that status can be used as string."""
        assert str(RulebookCheckStatus.PASS) == "RulebookCheckStatus.PASS"
        assert RulebookCheckStatus.PASS == "pass"


class TestRulebookCheckResult:
    """Test suite for RulebookCheckResult dataclass."""

    def test_result_dataclass_creation(self):
        """Test RulebookCheckResult can be created with all fields."""
        result = RulebookCheckResult(
            check_name="test_check",
            status=RulebookCheckStatus.PASS,
            details="Test details",
            checked_at="2026-03-22T12:00:00Z",
        )
        
        assert result.check_name == "test_check"
        assert result.status == RulebookCheckStatus.PASS
        assert result.details == "Test details"
        assert result.checked_at == "2026-03-22T12:00:00Z"
