"""
Tests for AML/OFAC screening, Travel Rule, and reserve proof engines.
"""

from __future__ import annotations

import pytest

from offchain.models.schemas import ComplianceStatus
from offchain.services import audit
from compliance.aml_screening.engine import AMLScreeningEngine, AlertType
from compliance.travel_rule.engine import (
    BeneficiaryInfo,
    OriginatorInfo,
    TravelRuleEngine,
    TravelRuleStatus,
)
from compliance.reserve_proof.engine import ProofStatus, ReserveProofEngine


class TestAMLScreeningEngine:
    """Tests for BSA/AML/OFAC real-time + batch screening."""

    @pytest.mark.asyncio
    async def test_clean_address_passes(self):
        audit.clear_log()
        engine = AMLScreeningEngine()
        result = await engine.screen_address_realtime("0xCLEAN_ADDRESS")
        assert result.status == ComplianceStatus.PASSED
        assert not result.ofac_match

    @pytest.mark.asyncio
    async def test_ofac_blocked_address(self):
        audit.clear_log()
        engine = AMLScreeningEngine()
        result = await engine.screen_address_realtime("0xOFAC_BLOCKED_001")
        assert result.status == ComplianceStatus.BLOCKED
        assert result.ofac_match is True
        assert AlertType.OFAC_MATCH in result.alerts

    @pytest.mark.asyncio
    async def test_sanctions_blocked(self):
        audit.clear_log()
        engine = AMLScreeningEngine()
        result = await engine.screen_address_realtime("0xSANCTIONED_ENTITY")
        assert result.status == ComplianceStatus.BLOCKED

    @pytest.mark.asyncio
    async def test_ctr_threshold_detection(self):
        audit.clear_log()
        engine = AMLScreeningEngine()
        result = await engine.screen_transaction(
            from_addr="0xSENDER", to_addr="0xRECEIVER", amount_usd=15_000.0
        )
        assert result.ctr_required is True
        assert AlertType.CTR_THRESHOLD in result.alerts

    @pytest.mark.asyncio
    async def test_below_ctr_no_alert(self):
        audit.clear_log()
        engine = AMLScreeningEngine()
        result = await engine.screen_transaction(
            from_addr="0xSENDER", to_addr="0xRECEIVER", amount_usd=5_000.0
        )
        assert result.ctr_required is False

    @pytest.mark.asyncio
    async def test_batch_screening(self):
        audit.clear_log()
        engine = AMLScreeningEngine()
        addresses = ["0xADDR_1", "0xADDR_2", "0xOFAC_BLOCKED_001", "0xADDR_3"]
        report = await engine.batch_screen(addresses)
        assert report.total_addresses == 4
        assert report.passed == 3
        assert report.blocked == 1

    @pytest.mark.asyncio
    async def test_ofac_blocks_transaction(self):
        audit.clear_log()
        engine = AMLScreeningEngine()
        result = await engine.screen_transaction(
            from_addr="0xOFAC_BLOCKED_001", to_addr="0xINNOCENT", amount_usd=1_000.0
        )
        assert result.status == ComplianceStatus.BLOCKED
        assert result.ofac_match is True


class TestTravelRuleEngine:
    """Tests for FinCEN Travel Rule compliance."""

    @pytest.mark.asyncio
    async def test_below_threshold_not_required(self):
        audit.clear_log()
        engine = TravelRuleEngine()
        record = await engine.process_transfer(
            amount_usd=1_000.0,
            originator=OriginatorInfo(full_name="John Doe"),
            beneficiary=BeneficiaryInfo(full_name="Jane Smith"),
            transaction_ref="TX-001",
        )
        assert record.status == TravelRuleStatus.NOT_REQUIRED

    @pytest.mark.asyncio
    async def test_above_threshold_submitted(self):
        audit.clear_log()
        engine = TravelRuleEngine()
        record = await engine.process_transfer(
            amount_usd=5_000.0,
            originator=OriginatorInfo(
                full_name="John Doe",
                institution_name="the Issuing Bank",
                wallet_address="0xORIG",
            ),
            beneficiary=BeneficiaryInfo(
                full_name="Jane Smith",
                institution_name="JPMorgan Chase",
                wallet_address="0xBENEF",
            ),
            transaction_ref="TX-002",
        )
        assert record.status == TravelRuleStatus.SUBMITTED
        assert len(record.originator_hash) == 64
        assert len(record.beneficiary_hash) == 64
        assert len(record.combined_hash) == 64
        assert record.vasp_notification_id.startswith("NTB-")

    @pytest.mark.asyncio
    async def test_hash_determinism(self):
        engine = TravelRuleEngine()
        orig = OriginatorInfo(full_name="Alice", institution_name="Bank A", wallet_address="0x1")
        benef = BeneficiaryInfo(full_name="Bob", institution_name="Bank B", wallet_address="0x2")

        h1 = engine.compute_hashes(orig, benef)
        h2 = engine.compute_hashes(orig, benef)
        assert h1 == h2

    @pytest.mark.asyncio
    async def test_confirm_receipt(self):
        audit.clear_log()
        engine = TravelRuleEngine()
        record = await engine.process_transfer(
            amount_usd=10_000.0,
            originator=OriginatorInfo(full_name="Alice"),
            beneficiary=BeneficiaryInfo(full_name="Bob", institution_name="Chase"),
            transaction_ref="TX-003",
        )
        confirmed = await engine.confirm_receipt(record.record_id)
        assert confirmed.status == TravelRuleStatus.CONFIRMED

    def test_threshold_detection(self):
        engine = TravelRuleEngine()
        assert engine.requires_travel_rule(3_000.0) is True
        assert engine.requires_travel_rule(2_999.99) is False
        assert engine.requires_travel_rule(100_000.0) is True


class TestReserveProofEngine:
    """Tests for cryptographic reserve proof generation."""

    @pytest.mark.asyncio
    async def test_verified_proof(self):
        audit.clear_log()
        engine = ReserveProofEngine()
        proof = await engine.generate_proof(
            total_supply_tokens=10_000_000_000,  # $10,000
            total_reserves_usd=10_000.0,
            block_number=12345,
            attestation_fresh=True,
            attestor="ISSUING_BANK_ATTESTOR"
        )
        assert proof.status == ProofStatus.VERIFIED
        assert proof.fully_backed is True
        assert proof.backing_ratio == 1.0
        assert proof.genius_s4_compliant is True
        assert proof.genius_s6_compliant is True
        assert len(proof.proof_hash) == 64
        assert len(proof.reserve_components) == 3

    @pytest.mark.asyncio
    async def test_under_backed_fails(self):
        audit.clear_log()
        engine = ReserveProofEngine()
        proof = await engine.generate_proof(
            total_supply_tokens=10_000_000_000,
            total_reserves_usd=9_000.0,  # Under-backed
            attestation_fresh=True,
        )
        assert proof.status == ProofStatus.FAILED
        assert proof.fully_backed is False
        assert proof.genius_s4_compliant is False

    @pytest.mark.asyncio
    async def test_stale_attestation_fails(self):
        audit.clear_log()
        engine = ReserveProofEngine()
        proof = await engine.generate_proof(
            total_supply_tokens=10_000_000_000,
            total_reserves_usd=10_000.0,
            attestation_fresh=False,  # Stale
        )
        assert proof.status == ProofStatus.FAILED
        assert proof.genius_s6_compliant is False

    @pytest.mark.asyncio
    async def test_reserve_composition(self):
        audit.clear_log()
        engine = ReserveProofEngine()
        proof = await engine.generate_proof(
            total_supply_tokens=10_000_000_000,
            total_reserves_usd=10_000.0,
            attestation_fresh=True,
        )
        components = proof.reserve_components
        assert len(components) == 3
        types = {c.asset_type for c in components}
        assert "US_TREASURY_BILL" in types
        assert "FDIC_INSURED_DEPOSIT" in types
        assert "FED_REVERSE_REPO" in types
        total = sum(c.amount_usd for c in components)
        assert abs(total - 10_000.0) < 0.01

    @pytest.mark.asyncio
    async def test_proof_history(self):
        audit.clear_log()
        engine = ReserveProofEngine()
        await engine.generate_proof(
            total_supply_tokens=1_000_000, total_reserves_usd=1.0, attestation_fresh=True
        )
        await engine.generate_proof(
            total_supply_tokens=2_000_000, total_reserves_usd=2.0, attestation_fresh=True
        )
        assert len(engine.get_all_proofs()) == 2
        latest = engine.get_latest_proof()
        assert latest is not None
        assert latest.total_supply_usd == 2.0
