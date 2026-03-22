"""
Reconciliation engine — matches on-chain CDA transactions to off-chain DDA GL entries.
Ensures ledger integrity for examiner audits (OCC/Fed/NYDFS).

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Reconciliation ensures CDA supply matches DDA reserve allocations.

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from offchain.models.schemas import ReconciliationEntry, ReconciliationStatus
from offchain.services import audit

logger = logging.getLogger("cari.reconciliation")


# =============================================================================
#                M&T Bank Post-2025 GL Account Structure
#      Aligned with Hogan mainframe GL subsystem and ISO 20022 classification
# =============================================================================

MT_GL_ACCOUNTS = {
    "1010": "Reserve Cash — FDIC-insured deposits backing CDA",
    "1015": "Reserve T-Bills — Short-term Treasury bills (GENIUS Act S4)",
    "1020": "Reserve Fed Deposits — Federal Reserve Bank deposits",
    "1510": "Settlement Receivable — Interbank net settlement (CDA inflow)",
    "2010": "CDA Token Liability — Outstanding Cari Deposit Accounts",
    "2510": "Settlement Payable — Interbank net settlement (CDA outflow)",
    "3010": "CDA Fee Revenue — Transaction fees on CDA operations",
    "4010": "CDA Operating Expense — Platform operational costs",
}


@dataclass
class HoganGLMapping:
    """Maps CDA operations to M&T's post-2025 Hogan GL entries.
    
    Each CDA operation generates a double-entry GL posting through
    Hogan's GL subsystem via IBM Z DIH.
    
    Format: ISO 20022 aligned, with Hogan journal reference.
    """
    operation: str  # MINT, BURN, SETTLEMENT_NET_RECEIVE, SETTLEMENT_NET_PAY
    debit_gl: str   # GL code to debit
    credit_gl: str  # GL code to credit
    description: str


# Standard CDA operation -> GL mapping for M&T post-2025 format
CDA_GL_MAPPINGS = {
    "MINT": HoganGLMapping(
        operation="MINT",
        debit_gl="1010",   # Reserve Cash (increase asset)
        credit_gl="2010",  # CDA Token Liability (increase liability)
        description="CDA mint: DDA -> CDA (debit reserve cash, credit token liability)",
    ),
    "BURN": HoganGLMapping(
        operation="BURN",
        debit_gl="2010",   # CDA Token Liability (decrease liability)
        credit_gl="1010",  # Reserve Cash (decrease asset)
        description="CDA burn: CDA -> DDA (debit token liability, credit reserve cash)",
    ),
    "SETTLEMENT_NET_RECEIVE": HoganGLMapping(
        operation="SETTLEMENT_NET_RECEIVE",
        debit_gl="1510",   # Settlement Receivable
        credit_gl="2010",  # CDA Token Liability
        description="Net settlement receive: mint CDA for net inflow",
    ),
    "SETTLEMENT_NET_PAY": HoganGLMapping(
        operation="SETTLEMENT_NET_PAY",
        debit_gl="2010",   # CDA Token Liability
        credit_gl="2510",  # Settlement Payable
        description="Net settlement pay: burn CDA for net outflow",
    ),
}


class ReconciliationSummary(BaseModel):
    """Aggregate reconciliation report."""
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    total_entries: int = 0
    matched: int = 0
    unmatched: int = 0
    exceptions: int = 0
    pending: int = 0
    net_on_chain_usd: float = 0.0
    net_off_chain_usd: float = 0.0
    discrepancy_usd: float = 0.0
    gl_format: str = "MT_POST_2025"  # M&T Bank GL format version
    gl_system: str = "Hogan/IBM_Z_DIH"  # GL integration system


class OnChainRecord(BaseModel):
    """Representation of an on-chain CDA transaction for reconciliation."""
    tx_hash: str
    tx_type: str  # MINT, BURN, TRANSFER
    amount: int  # 6-decimal CDA token units
    from_address: str = ""
    to_address: str = ""
    reference_id: str = ""
    block_number: int = 0
    timestamp: Optional[datetime] = None


class OffChainRecord(BaseModel):
    """Representation of an off-chain DDA GL entry for reconciliation."""
    entry_id: str
    reference_id: str
    amount_usd: float
    gl_account: str
    entry_type: str  # DEBIT, CREDIT
    posted_at: Optional[datetime] = None
    hogan_journal_id: str = ""       # Hogan GL journal reference
    gl_format: str = "MT_POST_2025"  # GL format version
    iso20022_msg_id: str = ""        # ISO 20022 message identifier


class ReconciliationEngine:
    """Matches on-chain CDA and off-chain DDA records, flags exceptions."""

    def __init__(self) -> None:
        self._entries: list[ReconciliationEntry] = []
        self._on_chain: list[OnChainRecord] = []
        self._off_chain: list[OffChainRecord] = []

    async def add_on_chain_record(self, record: OnChainRecord) -> None:
        """Register an on-chain CDA transaction for reconciliation."""
        self._on_chain.append(record)
        logger.debug("On-chain record added: %s (%s)", record.tx_hash[:16], record.tx_type)

    async def add_off_chain_record(self, record: OffChainRecord) -> None:
        """Register an off-chain DDA GL entry for reconciliation."""
        self._off_chain.append(record)
        logger.debug("Off-chain record added: %s (%s)", record.entry_id[:12], record.reference_id)

    async def reconcile(self) -> list[ReconciliationEntry]:
        """Run reconciliation: match on-chain CDA txs to off-chain DDA GL entries by reference_id."""
        results: list[ReconciliationEntry] = []

        # Index off-chain records by reference_id
        off_chain_by_ref: dict[str, list[OffChainRecord]] = {}
        for rec in self._off_chain:
            off_chain_by_ref.setdefault(rec.reference_id, []).append(rec)

        matched_off_chain_refs: set[str] = set()

        # Match each on-chain record
        for on_rec in self._on_chain:
            ref = on_rec.reference_id
            off_matches = off_chain_by_ref.get(ref, [])
            on_chain_usd = on_rec.amount / 1e6

            if off_matches:
                off_rec = off_matches[0]
                matched_off_chain_refs.add(ref)

                # Check amount match (within $0.01 tolerance)
                diff = abs(on_chain_usd - off_rec.amount_usd)
                if diff <= 0.01:
                    status = ReconciliationStatus.MATCHED
                    reason = ""
                else:
                    status = ReconciliationStatus.EXCEPTION
                    reason = (
                        f"Amount mismatch: on-chain=${on_chain_usd:.2f} "
                        f"vs off-chain=${off_rec.amount_usd:.2f} (diff=${diff:.2f})"
                    )

                entry = ReconciliationEntry(
                    reference_id=ref,
                    on_chain_tx_hash=on_rec.tx_hash,
                    on_chain_amount=on_rec.amount,
                    off_chain_amount_usd=off_rec.amount_usd,
                    gl_account=off_rec.gl_account,
                    status=status,
                    matched_at=datetime.utcnow() if status == ReconciliationStatus.MATCHED else None,
                    exception_reason=reason,
                    hogan_journal_id=off_rec.hogan_journal_id,
                )
            else:
                # On-chain with no off-chain match
                entry = ReconciliationEntry(
                    reference_id=ref,
                    on_chain_tx_hash=on_rec.tx_hash,
                    on_chain_amount=on_rec.amount,
                    status=ReconciliationStatus.UNMATCHED,
                    exception_reason=f"No off-chain GL entry for reference {ref}",
                )

            results.append(entry)

        # Find off-chain entries with no on-chain match
        for ref, off_recs in off_chain_by_ref.items():
            if ref not in matched_off_chain_refs:
                for off_rec in off_recs:
                    entry = ReconciliationEntry(
                        reference_id=ref,
                        off_chain_amount_usd=off_rec.amount_usd,
                        gl_account=off_rec.gl_account,
                        status=ReconciliationStatus.UNMATCHED,
                        exception_reason=f"No on-chain transaction for reference {ref}",
                        hogan_journal_id=off_rec.hogan_journal_id,
                    )
                    results.append(entry)

        self._entries = results

        # Audit log
        summary = await self.get_summary()
        await audit.record(
            actor="RECONCILIATION",
            action="reconcile",
            resource="ledger",
            details={
                "total": summary.total_entries,
                "matched": summary.matched,
                "unmatched": summary.unmatched,
                "exceptions": summary.exceptions,
                "discrepancy_usd": summary.discrepancy_usd,
            },
        )

        if summary.exceptions > 0 or summary.unmatched > 0:
            logger.warning(
                "Reconciliation issues: %d unmatched, %d exceptions, discrepancy=$%.2f",
                summary.unmatched, summary.exceptions, summary.discrepancy_usd,
            )
        else:
            logger.info("Reconciliation complete: %d entries all matched", summary.matched)

        return results

    async def get_summary(self) -> ReconciliationSummary:
        """Generate aggregate reconciliation summary."""
        matched = sum(1 for e in self._entries if e.status == ReconciliationStatus.MATCHED)
        unmatched = sum(1 for e in self._entries if e.status == ReconciliationStatus.UNMATCHED)
        exceptions = sum(1 for e in self._entries if e.status == ReconciliationStatus.EXCEPTION)
        pending = sum(1 for e in self._entries if e.status == ReconciliationStatus.PENDING)

        net_on = sum((e.on_chain_amount or 0) / 1e6 for e in self._entries)
        net_off = sum(e.off_chain_amount_usd or 0 for e in self._entries)

        return ReconciliationSummary(
            total_entries=len(self._entries),
            matched=matched,
            unmatched=unmatched,
            exceptions=exceptions,
            pending=pending,
            net_on_chain_usd=round(net_on, 2),
            net_off_chain_usd=round(net_off, 2),
            discrepancy_usd=round(abs(net_on - net_off), 2),
        )

    def get_entries(self) -> list[ReconciliationEntry]:
        """Return all reconciliation entries."""
        return list(self._entries)

    def clear(self) -> None:
        """Reset engine state (testing only)."""
        self._entries.clear()
        self._on_chain.clear()
        self._off_chain.clear()

    def validate_gl_mapping(self, operation: str, entries: list[OffChainRecord]) -> list[str]:
        """Validate that GL entries follow M&T's post-2025 GL mapping rules.
        
        Checks that the correct GL codes are used for each CDA operation type
        and that double-entry bookkeeping is maintained.
        
        Returns list of validation issues (empty if valid).
        """
        issues = []
        mapping = CDA_GL_MAPPINGS.get(operation)
        if not mapping:
            issues.append(f"Unknown CDA operation: {operation}")
            return issues
        
        debit_found = False
        credit_found = False
        for entry in entries:
            if entry.entry_type == "DEBIT" and entry.gl_account == mapping.debit_gl:
                debit_found = True
            if entry.entry_type == "CREDIT" and entry.gl_account == mapping.credit_gl:
                credit_found = True
        
        if not debit_found:
            issues.append(f"Missing debit to GL {mapping.debit_gl} for {operation}")
        if not credit_found:
            issues.append(f"Missing credit to GL {mapping.credit_gl} for {operation}")
        
        return issues


_engine: ReconciliationEngine | None = None


def get_reconciliation_engine() -> ReconciliationEngine:
    global _engine
    if _engine is None:
        _engine = ReconciliationEngine()
    return _engine
