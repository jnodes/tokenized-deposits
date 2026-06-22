"""
Compliance screening service — BSA/AML/OFAC + Travel Rule.
Integrates with Chainalysis KYT and Notabene for Travel Rule.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
All CDA/DDA operations are screened for BSA/AML/OFAC compliance.

the Issuing Bank | Cari Network | ZKsync Prividium.

SECURITY GUARDIAN NOTE:
- All screening results are immutably logged for examiner access.
- OFAC matches trigger immediate CDA freeze via the on-chain COMPLIANCE_ROLE.
- Travel Rule data is stored off-chain (Notabene); only hashes go on-chain.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime

from offchain.config import Settings, get_settings
from offchain.models.schemas import ComplianceScreeningResult, ComplianceStatus
from offchain.services import audit

logger = logging.getLogger("cari.compliance")


class ComplianceService:
    """BSA/AML/OFAC screening and Travel Rule coordination."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    async def screen_address(self, address: str) -> ComplianceScreeningResult:
        """Screen a wallet address against OFAC/sanctions/AML databases.

        In production, this calls Chainalysis KYT API or TRM Labs.
        For dev/test, returns a stub PASSED result.
        """
        # --- Stub: in production, call Chainalysis API ---
        # POST {chainalysis_base_url}/users/{address}/transfers
        result = ComplianceScreeningResult(
            address=address,
            status=ComplianceStatus.PASSED,
            risk_score=0.1,
            ofac_match=False,
            sanctions_match=False,
            travel_rule_required=False,
            provider="chainalysis_stub",
            details="Stub screening — no real API call in dev mode",
        )

        await audit.record(
            actor="COMPLIANCE_SERVICE",
            action="screen_address",
            resource=f"address:{address}",
            details={
                "status": result.status.value,
                "risk_score": result.risk_score,
                "ofac_match": result.ofac_match,
                "provider": result.provider,
            },
        )

        logger.info("Screening %s: %s (risk=%.2f)", address, result.status, result.risk_score or 0)
        return result

    async def screen_transaction(
        self, *, from_addr: str, to_addr: str, amount_usd: float
    ) -> ComplianceScreeningResult:
        """Screen a transaction for BSA/AML compliance.

        Checks both sender and receiver. Flags if amount >= CTR threshold ($10,000).
        """
        # Screen both parties
        sender_result = await self.screen_address(from_addr)
        receiver_result = await self.screen_address(to_addr)

        # Determine overall status
        if sender_result.ofac_match or receiver_result.ofac_match:
            status = ComplianceStatus.BLOCKED
        elif sender_result.sanctions_match or receiver_result.sanctions_match:
            status = ComplianceStatus.FLAGGED
        else:
            status = ComplianceStatus.PASSED

        # Check Travel Rule threshold
        travel_rule_required = amount_usd >= self._settings.travel_rule_threshold_usd

        # Check CTR threshold ($10,000)
        ctr_required = amount_usd >= 10_000

        return ComplianceScreeningResult(
            address=f"{from_addr}->{to_addr}",
            status=status,
            risk_score=max(sender_result.risk_score or 0, receiver_result.risk_score or 0),
            ofac_match=sender_result.ofac_match or receiver_result.ofac_match,
            sanctions_match=sender_result.sanctions_match or receiver_result.sanctions_match,
            travel_rule_required=travel_rule_required,
            provider="chainalysis_stub",
            details=f"CTR required: {ctr_required}, Travel Rule: {travel_rule_required}",
        )

    async def compute_travel_rule_hash(
        self,
        *,
        originator_name: str,
        originator_institution: str,
        beneficiary_name: str,
        beneficiary_institution: str,
    ) -> tuple[bytes, bytes, bytes]:
        """Compute Travel Rule hashes for on-chain storage.

        Returns (originator_hash, beneficiary_hash, combined_hash).
        In production, full PII is submitted to Notabene via their API;
        only keccak hashes are stored on-chain.
        """
        originator_data = f"{originator_name}|{originator_institution}".encode()
        beneficiary_data = f"{beneficiary_name}|{beneficiary_institution}".encode()

        originator_hash = hashlib.sha256(originator_data).digest()
        beneficiary_hash = hashlib.sha256(beneficiary_data).digest()
        combined_hash = hashlib.sha256(originator_data + beneficiary_data).digest()

        await audit.record(
            actor="COMPLIANCE_SERVICE",
            action="compute_travel_rule_hash",
            resource="travel_rule",
            details={
                "originator_institution": originator_institution,
                "beneficiary_institution": beneficiary_institution,
            },
        )

        return originator_hash, beneficiary_hash, combined_hash


_compliance_service: ComplianceService | None = None


def get_compliance_service() -> ComplianceService:
    global _compliance_service
    if _compliance_service is None:
        _compliance_service = ComplianceService()
    return _compliance_service
