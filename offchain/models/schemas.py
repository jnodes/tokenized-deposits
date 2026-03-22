"""
Pydantic v2 models for the off-chain orchestration platform.
M&T Bank | Cari Network | ZKsync Prividium.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
DDA <-> CDA flow: fiat in DDA triggers CDA mint; CDA burn triggers fiat back to DDA.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# =============================================================================
#                           ENUMS
# =============================================================================


class TransactionType(str, Enum):
    MINT = "MINT"
    BURN = "BURN"
    TRANSFER = "TRANSFER"
    SETTLEMENT_INITIATE = "SETTLEMENT_INITIATE"
    SETTLEMENT_EXECUTE = "SETTLEMENT_EXECUTE"
    SETTLEMENT_REVERT = "SETTLEMENT_REVERT"
    FORCE_TRANSFER = "FORCE_TRANSFER"


class TransactionStatus(str, Enum):
    PENDING = "PENDING"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    REJECTED = "REJECTED"


class PaymentRail(str, Enum):
    ACH = "ACH"
    FEDWIRE = "FEDWIRE"
    RTP = "RTP"
    BOOK_TRANSFER = "BOOK_TRANSFER"
    FEDNOW = "FEDNOW"


class CustodyTier(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"


class ComplianceStatus(str, Enum):
    PENDING = "PENDING"
    PASSED = "PASSED"
    FLAGGED = "FLAGGED"
    BLOCKED = "BLOCKED"


class SettlementStatus(str, Enum):
    PENDING = "PENDING"
    EXECUTED = "EXECUTED"
    REVERTED = "REVERTED"
    EXPIRED = "EXPIRED"


class ReconciliationStatus(str, Enum):
    MATCHED = "MATCHED"
    UNMATCHED = "UNMATCHED"
    EXCEPTION = "EXCEPTION"
    PENDING = "PENDING"


# =============================================================================
#                      REQUEST / RESPONSE MODELS
# =============================================================================


class MintRequest(BaseModel):
    """Request to mint Cari deposits (CDA) after fiat deposit to DDA at M&T Bank."""
    to_address: str = Field(..., description="Whitelisted recipient wallet address (CDA holder)")
    amount_usd: float = Field(..., gt=0, description="USD amount to mint (will be converted to 6-decimal CDA token units)")
    reference_id: str = Field(..., description="M&T core banking reference ID for DDA->CDA reconciliation")
    payment_rail: PaymentRail = Field(..., description="How the fiat deposit arrived at DDA")
    depositor_account_id: str = Field(..., description="M&T Bank DDA account number")


class BurnRequest(BaseModel):
    """Request to burn (redeem) Cari deposits (CDA) at par — GENIUS Act Section 5.
    
    CDA burn triggers fiat settlement back to depositor's DDA.
    """
    from_address: str = Field(..., description="Address holding CDA tokens to redeem")
    amount_usd: float = Field(..., gt=0, description="USD amount to redeem at par")
    reference_id: str = Field(..., description="M&T core banking reference for CDA->DDA settlement")
    destination_account_id: str = Field(..., description="M&T Bank DDA to credit USD")
    payment_rail: PaymentRail = Field(PaymentRail.FEDNOW, description="Settlement rail for fiat payout to DDA")


class SettlementRequest(BaseModel):
    """Request to initiate a Cari cross-bank CDA settlement."""
    destination_bank: str = Field(..., description="Cari member bank identifier")
    originator_address: str = Field(..., description="Sender CDA wallet (source bank)")
    beneficiary_address: str = Field(..., description="Receiver CDA wallet (destination bank)")
    amount_usd: float = Field(..., gt=0)
    originator_name: str = Field(..., description="Originator full name (Travel Rule)")
    beneficiary_name: str = Field(..., description="Beneficiary full name (Travel Rule)")
    originator_institution: str = Field(default="M&T Bank")
    beneficiary_institution: str = Field(...)


class TransactionResponse(BaseModel):
    """Standard response for all CDA transaction operations."""
    transaction_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tx_type: TransactionType
    status: TransactionStatus
    amount_usd: float
    token_amount: int = Field(description="Amount in 6-decimal CDA token units")
    reference_id: str
    tx_hash: Optional[str] = None
    compliance_status: ComplianceStatus = ComplianceStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    message: str = ""


class ReserveStatusResponse(BaseModel):
    """Current reserve status — GENIUS Act Section 4 & 6 transparency.
    
    Ensures 1:1 backing of CDA tokens by DDA reserves.
    """
    total_reserves_usd: float
    total_supply_tokens: int = Field(description="Total CDA tokens in circulation")
    total_supply_usd: float
    backing_ratio: float = Field(description="reserves / CDA supply — must be >= 1.0")
    attestation_fresh: bool
    last_attested_at: Optional[datetime] = None
    attestation_hash: Optional[str] = None
    max_staleness_seconds: int
    compliant: bool = Field(description="True if backing_ratio >= 1.0 and attestation fresh")


class ReconciliationEntry(BaseModel):
    """A single reconciliation record matching on-chain CDA to off-chain DDA."""
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    reference_id: str
    on_chain_tx_hash: Optional[str] = None
    on_chain_amount: Optional[int] = None
    off_chain_amount_usd: Optional[float] = None
    gl_account: str = ""
    status: ReconciliationStatus = ReconciliationStatus.PENDING
    matched_at: Optional[datetime] = None
    exception_reason: str = ""
    hogan_journal_id: str = ""  # Hogan GL journal reference for cross-system tracing


class ComplianceScreeningResult(BaseModel):
    """Result of BSA/AML/OFAC screening."""
    screening_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    address: str
    status: ComplianceStatus
    risk_score: Optional[float] = None
    ofac_match: bool = False
    sanctions_match: bool = False
    travel_rule_required: bool = False
    screened_at: datetime = Field(default_factory=datetime.utcnow)
    provider: str = ""  # "chainalysis" | "trm_labs"
    details: str = ""


class AuditLogEntry(BaseModel):
    """Immutable audit log entry for examiner transparency (OCC/Fed/NYDFS).
    
    Tracks all CDA/DDA operations for regulatory compliance.
    """
    log_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str = Field(description="Role or service that initiated the action")
    action: str
    resource: str
    details: dict = Field(default_factory=dict)
    ip_address: str = ""
    correlation_id: str = ""


class HealthResponse(BaseModel):
    """System health check."""
    status: str = "healthy"
    version: str = "1.0.0"
    environment: str = "dev"
    blockchain_connected: bool = False
    kafka_connected: bool = False
    redis_connected: bool = False
    database_connected: bool = False
    reserve_oracle_fresh: bool = False
