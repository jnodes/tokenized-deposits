"""
Travel Rule Compliance Engine — FinCEN CDD / Travel Rule for >= $3,000 CDA transfers.
Manages originator/beneficiary data collection, hashing, and VASP notification.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Travel Rule applies to CDA transfers between Cari member banks.

Implements:
- Originator/beneficiary PII collection and validation
- SHA-256 hashing for on-chain storage (PII stays off-chain)
- VASP-to-VASP notification via Notabene adapter (stub)
- Travel Rule threshold detection ($3,000 FinCEN / $1,000 FATF)
- Integration with Quest 1 CariSettlement contract (travel_rule_hash for CDA transfers)

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from offchain.services import audit

logger = logging.getLogger("cari.compliance.travel_rule")


class TravelRuleStatus(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


class OriginatorInfo(BaseModel):
    """Originator data for Travel Rule compliance."""
    full_name: str
    account_number: str = ""
    institution_name: str = "M&T Bank"
    institution_lei: str = ""  # Legal Entity Identifier
    address: str = ""
    date_of_birth: str = ""
    national_id: str = ""
    wallet_address: str = ""


class BeneficiaryInfo(BaseModel):
    """Beneficiary data for Travel Rule compliance."""
    full_name: str
    account_number: str = ""
    institution_name: str = ""
    institution_lei: str = ""
    address: str = ""
    wallet_address: str = ""


class TravelRuleRecord(BaseModel):
    """Complete Travel Rule compliance record for a transaction."""
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    transaction_ref: str = ""
    amount_usd: float
    originator: OriginatorInfo
    beneficiary: BeneficiaryInfo
    originator_hash: str = ""
    beneficiary_hash: str = ""
    combined_hash: str = ""
    status: TravelRuleStatus = TravelRuleStatus.PENDING
    vasp_notification_id: str = ""
    threshold_usd: float = 3_000.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None


class TravelRuleEngine:
    """Travel Rule compliance processing engine."""

    FINCEN_THRESHOLD = 3_000.0
    FATF_THRESHOLD = 1_000.0

    def __init__(self, threshold_usd: float = 3_000.0) -> None:
        self._threshold = threshold_usd
        self._records: list[TravelRuleRecord] = []

    def requires_travel_rule(self, amount_usd: float) -> bool:
        """Check if a transaction requires Travel Rule data."""
        return amount_usd >= self._threshold

    def compute_hashes(
        self, originator: OriginatorInfo, beneficiary: BeneficiaryInfo
    ) -> tuple[str, str, str]:
        """Compute SHA-256 hashes for on-chain storage.

        Returns (originator_hash, beneficiary_hash, combined_hash) as hex strings.
        PII is never stored on-chain — only hashes for verification.
        """
        orig_data = f"{originator.full_name}|{originator.institution_name}|{originator.wallet_address}".encode()
        benef_data = f"{beneficiary.full_name}|{beneficiary.institution_name}|{beneficiary.wallet_address}".encode()

        orig_hash = hashlib.sha256(orig_data).hexdigest()
        benef_hash = hashlib.sha256(benef_data).hexdigest()
        combined_hash = hashlib.sha256(orig_data + benef_data).hexdigest()

        return orig_hash, benef_hash, combined_hash

    async def process_transfer(
        self,
        *,
        amount_usd: float,
        originator: OriginatorInfo,
        beneficiary: BeneficiaryInfo,
        transaction_ref: str = "",
    ) -> TravelRuleRecord:
        """Process a transfer for Travel Rule compliance."""
        if not self.requires_travel_rule(amount_usd):
            record = TravelRuleRecord(
                transaction_ref=transaction_ref,
                amount_usd=amount_usd,
                originator=originator,
                beneficiary=beneficiary,
                status=TravelRuleStatus.NOT_REQUIRED,
                threshold_usd=self._threshold,
            )
            self._records.append(record)
            return record

        # Compute hashes
        orig_hash, benef_hash, combined_hash = self.compute_hashes(originator, beneficiary)

        # Submit to Notabene VASP network (stub)
        vasp_id = f"NTB-{uuid.uuid4().hex[:12].upper()}"

        record = TravelRuleRecord(
            transaction_ref=transaction_ref,
            amount_usd=amount_usd,
            originator=originator,
            beneficiary=beneficiary,
            originator_hash=orig_hash,
            beneficiary_hash=benef_hash,
            combined_hash=combined_hash,
            status=TravelRuleStatus.SUBMITTED,
            vasp_notification_id=vasp_id,
            threshold_usd=self._threshold,
            submitted_at=datetime.now(timezone.utc),
        )
        self._records.append(record)

        await audit.record(
            actor="TRAVEL_RULE",
            action="process_transfer",
            resource=f"transaction:{transaction_ref}",
            details={
                "amount_usd": amount_usd,
                "originator_institution": originator.institution_name,
                "beneficiary_institution": beneficiary.institution_name,
                "combined_hash": combined_hash[:16],
                "vasp_id": vasp_id,
            },
        )
        logger.info(
            "Travel Rule submitted: $%.2f %s -> %s (VASP: %s)",
            amount_usd, originator.institution_name,
            beneficiary.institution_name, vasp_id,
        )
        return record

    async def confirm_receipt(self, record_id: str) -> TravelRuleRecord:
        """Confirm that the beneficiary VASP acknowledged Travel Rule data."""
        record = next((r for r in self._records if r.record_id == record_id), None)
        if not record:
            raise ValueError(f"Travel Rule record not found: {record_id}")
        record.status = TravelRuleStatus.CONFIRMED
        record.confirmed_at = datetime.now(timezone.utc)

        await audit.record(
            actor="TRAVEL_RULE",
            action="confirm_receipt",
            resource=f"record:{record_id}",
            details={"vasp_id": record.vasp_notification_id},
        )
        return record

    def get_records(self, transaction_ref: str | None = None) -> list[TravelRuleRecord]:
        if transaction_ref:
            return [r for r in self._records if r.transaction_ref == transaction_ref]
        return list(self._records)

    def get_pending(self) -> list[TravelRuleRecord]:
        return [r for r in self._records if r.status == TravelRuleStatus.PENDING]


_engine: TravelRuleEngine | None = None


def get_travel_rule_engine() -> TravelRuleEngine:
    global _engine
    if _engine is None:
        _engine = TravelRuleEngine()
    return _engine
