"""
Core banking adapter — abstract interface and FIS/Symcor stub.
Connects to M&T Bank's general ledger for DDA deposit verification,
reserve tracking, and CDA settlement.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Core banking manages DDA balances that back CDA tokens.

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from offchain.services import audit

logger = logging.getLogger("cari.core_banking")


class GLEntryType(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"


class GLEntry(BaseModel):
    """General ledger entry for double-entry bookkeeping."""
    entry_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    account_number: str
    entry_type: GLEntryType
    amount_usd: float
    reference_id: str
    description: str = ""
    posted_at: datetime = Field(default_factory=datetime.utcnow)
    gl_code: str = ""


class DepositVerification(BaseModel):
    """Result of verifying a fiat deposit to DDA at M&T Bank (triggers CDA mint)."""
    verified: bool
    account_id: str
    amount_usd: float
    reference_id: str
    deposit_timestamp: Optional[datetime] = None
    payment_rail: str = ""
    message: str = ""


class CoreBankingAdapter(ABC):
    """Abstract adapter for M&T Bank's core banking system."""

    @abstractmethod
    async def verify_deposit(
        self, *, account_id: str, reference_id: str, amount_usd: float
    ) -> DepositVerification:
        """Verify that a fiat deposit to DDA has been received and cleared (for CDA mint)."""
        ...

    @abstractmethod
    async def post_gl_entries(self, entries: list[GLEntry]) -> bool:
        """Post general ledger entries for CDA reserve allocation / release."""
        ...

    @abstractmethod
    async def initiate_payout(
        self,
        *,
        account_id: str,
        amount_usd: float,
        reference_id: str,
        rail: str,
    ) -> str:
        """Initiate fiat payout to DDA on CDA redemption. Returns payout reference."""
        ...

    @abstractmethod
    async def get_reserve_balance(self) -> float:
        """Get the current DDA reserve account balance (for CDA oracle sync)."""
        ...


class StubCoreBankingAdapter(CoreBankingAdapter):
    """Stub implementation for dev/test — simulates M&T core banking (FIS/Symcor).

    In production, replace with real API calls to M&T's core banking platform.
    """

    def __init__(self) -> None:
        self._deposits: dict[str, DepositVerification] = {}
        self._gl_entries: list[GLEntry] = []
        self._reserve_balance: float = 10_000_000.00  # $10M initial
        self._payouts: list[dict] = []

    async def verify_deposit(
        self, *, account_id: str, reference_id: str, amount_usd: float
    ) -> DepositVerification:
        result = DepositVerification(
            verified=True,
            account_id=account_id,
            amount_usd=amount_usd,
            reference_id=reference_id,
            deposit_timestamp=datetime.utcnow(),
            message="Deposit verified (stub)",
        )
        self._deposits[reference_id] = result

        await audit.record(
            actor="CORE_BANKING",
            action="verify_deposit",
            resource=f"account:{account_id}",
            details={
                "reference_id": reference_id,
                "amount_usd": amount_usd,
                "verified": True,
            },
        )
        logger.info("Deposit verified: ref=%s, amount=$%.2f", reference_id, amount_usd)
        return result

    async def post_gl_entries(self, entries: list[GLEntry]) -> bool:
        self._gl_entries.extend(entries)
        for entry in entries:
            if entry.entry_type == GLEntryType.DEBIT:
                self._reserve_balance -= entry.amount_usd
            else:
                self._reserve_balance += entry.amount_usd
            logger.info(
                "GL posted: %s %s $%.2f ref=%s",
                entry.entry_type, entry.gl_code, entry.amount_usd, entry.reference_id,
            )
        await audit.record(
            actor="CORE_BANKING",
            action="post_gl_entries",
            resource="general_ledger",
            details={"count": len(entries), "total_usd": sum(e.amount_usd for e in entries)},
        )
        return True

    async def initiate_payout(
        self,
        *,
        account_id: str,
        amount_usd: float,
        reference_id: str,
        rail: str,
    ) -> str:
        payout_ref = f"PAYOUT-{uuid.uuid4().hex[:12].upper()}"
        self._payouts.append({
            "payout_ref": payout_ref,
            "account_id": account_id,
            "amount_usd": amount_usd,
            "reference_id": reference_id,
            "rail": rail,
            "timestamp": datetime.utcnow().isoformat(),
        })
        await audit.record(
            actor="CORE_BANKING",
            action="initiate_payout",
            resource=f"account:{account_id}",
            details={
                "payout_ref": payout_ref,
                "amount_usd": amount_usd,
                "rail": rail,
            },
        )
        logger.info(
            "Payout initiated: %s -> %s $%.2f via %s",
            payout_ref, account_id, amount_usd, rail,
        )
        return payout_ref

    async def get_reserve_balance(self) -> float:
        return self._reserve_balance


class HoganCoreBankingAdapter(CoreBankingAdapter):
    """
    M&T Bank Hogan mainframe adapter via IBM Z Data Integration Hub (DIH).
    
    Architecture:
        FastAPI -> IBM Z DIH (MQ/REST gateway) -> Hogan CIF/DDA System
    
    Hogan CIF (Customer Information File) manages customer/account data.
    Hogan DDA (Demand Deposit Accounts) manages fiat deposit accounts.
    IBM Z DIH provides the middleware bridge between modern APIs and COBOL/CICS transactions.
    
    CDA Flow:
        - Mint (DDA->CDA): Hogan DDA debit -> GL posting -> on-chain CDA mint
        - Burn (CDA->DDA): on-chain CDA burn -> GL posting -> Hogan DDA credit
    
    GL Account Mapping (M&T post-2025 format):
        - 1010: Reserve Cash (FDIC-insured deposits backing CDA)
        - 2010: CDA Token Liability (on-chain CDA outstanding)
        - 1510: Settlement Receivable (interbank net settlement)
        - 2510: Settlement Payable (interbank net settlement)
    
    NOTE: Stub implementation — replace with IBM Z DIH MQ Series / REST API calls.
    """
    
    def __init__(self) -> None:
        self._reserve_balance: float = 10_000_000.0
        self._dda_accounts: dict[str, float] = {}  # account_id -> balance
        self._gl_journal: list[dict] = []  # Posted GL entries log
        self._hogan_connected = False
    
    async def connect_hogan(self) -> bool:
        """Establish connection to Hogan via IBM Z DIH middleware.
        
        In production: connects to IBM MQ Series queue manager or Z DIH REST endpoint.
        Validates Hogan CIF availability and DDA system readiness.
        """
        logger.info("Connecting to Hogan CIF/DDA via IBM Z DIH middleware...")
        self._hogan_connected = True
        await audit.record(
            actor="HOGAN_DIH", action="connect", resource="hogan_mainframe",
            details={"status": "connected", "middleware": "IBM_Z_DIH"}
        )
        return True
    
    async def verify_deposit(
        self, *, account_id: str, reference_id: str, amount_usd: float
    ) -> DepositVerification:
        """Verify DDA deposit via Hogan CIF/DDA lookup through IBM Z DIH.
        
        Production flow:
        1. Send CICS transaction to Hogan DDA system via Z DIH
        2. Hogan validates account exists, is active, and has sufficient balance
        3. Returns verification with Hogan transaction reference
        """
        logger.info("Hogan DDA verification: account=%s, amount=$%.2f via IBM Z DIH", account_id, amount_usd)
        
        hogan_ref = f"HGN-{reference_id[:8].upper()}"
        
        await audit.record(
            actor="HOGAN_DIH", action="verify_deposit", resource=f"dda:{account_id}",
            details={"amount_usd": amount_usd, "reference_id": reference_id, "hogan_ref": hogan_ref}
        )
        
        return DepositVerification(
            verified=True,
            account_id=account_id,
            reference_id=reference_id,
            amount_usd=amount_usd,
            deposit_timestamp=datetime.now(timezone.utc),
            message=f"Hogan DDA verified via IBM Z DIH — ref: {hogan_ref}"
        )
    
    async def post_gl_entries(self, entries: list[GLEntry]) -> bool:
        """Post GL entries to M&T's post-2025 General Ledger via Hogan.
        
        Production flow:
        1. Format entries in M&T post-2025 GL format (ISO 20022 aligned)
        2. Submit batch to Hogan GL subsystem via IBM Z DIH
        3. Hogan validates double-entry balance and posts to GL
        4. Returns posting confirmation with Hogan journal ID
        
        M&T Post-2025 GL Format:
        - GL codes use 4-digit classification (1010, 2010, 1510, 2510)
        - Journal entries include CDA reference for on-chain/off-chain reconciliation
        - ISO 20022 message format for interoperability
        """
        logger.info("Posting %d GL entries to Hogan via IBM Z DIH (post-2025 format)", len(entries))
        
        for entry in entries:
            self._gl_journal.append({
                "entry_id": entry.entry_id,
                "gl_code": entry.gl_code,
                "account": entry.account_number,
                "type": entry.entry_type.value,
                "amount": entry.amount_usd,
                "reference": entry.reference_id,
                "description": entry.description,
                "posted_at": entry.posted_at.isoformat() if entry.posted_at else datetime.now(timezone.utc).isoformat(),
                "format": "MT_POST_2025_ISO20022",
            })
            
            if entry.entry_type == GLEntryType.DEBIT:
                self._reserve_balance -= entry.amount_usd
            else:
                self._reserve_balance += entry.amount_usd
        
        await audit.record(
            actor="HOGAN_DIH", action="post_gl_entries", resource="general_ledger",
            details={"entry_count": len(entries), "format": "MT_POST_2025_ISO20022", "gl_codes": [e.gl_code for e in entries]}
        )
        return True
    
    async def initiate_payout(
        self,
        *,
        account_id: str,
        amount_usd: float,
        reference_id: str,
        rail: str = "ACH",
    ) -> str:
        """Initiate fiat payout to DDA via Hogan payment processing.
        
        Production flow:
        1. Submit payment instruction to Hogan via IBM Z DIH
        2. Hogan routes to appropriate payment rail (ACH/Fedwire/RTP)
        3. Returns Hogan payment reference for tracking
        """
        payout_ref = f"HGN-PAY-{reference_id[:8].upper()}"
        logger.info("Hogan payout: $%.2f to %s via %s (ref: %s)", amount_usd, account_id, rail, payout_ref)
        
        await audit.record(
            actor="HOGAN_DIH", action="initiate_payout", resource=f"dda:{account_id}",
            details={"amount_usd": amount_usd, "rail": rail, "hogan_ref": payout_ref}
        )
        return payout_ref
    
    async def get_reserve_balance(self) -> float:
        """Query aggregate reserve balance from Hogan GL."""
        return self._reserve_balance
    
    def get_gl_journal(self) -> list[dict]:
        """Return posted GL journal entries (for reconciliation/audit)."""
        return list(self._gl_journal)


_adapters: dict[str, CoreBankingAdapter] = {}


def get_core_banking_adapter(provider: str = "stub") -> CoreBankingAdapter:
    """Factory for core banking adapters.
    
    Args:
        provider: "stub" for development/test, "hogan" for M&T Bank Hogan mainframe via IBM Z DIH.
    
    Returns:
        Cached CoreBankingAdapter instance for the requested provider.
    """
    if provider not in _adapters:
        if provider == "hogan":
            _adapters[provider] = HoganCoreBankingAdapter()
        else:
            _adapters[provider] = StubCoreBankingAdapter()
    return _adapters[provider]
