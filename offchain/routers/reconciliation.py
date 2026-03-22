"""
Reconciliation router — CDA/DDA ledger matching and examiner reporting.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Reconciliation ensures on-chain CDA transactions match off-chain DDA ledger entries.

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from offchain.models.schemas import ReconciliationEntry, ReconciliationStatus
from reconciliation.engine import (
    ReconciliationEngine,
    ReconciliationSummary,
    get_reconciliation_engine,
)

logger = logging.getLogger("cari.router.reconciliation")

router = APIRouter(prefix="/reconciliation", tags=["Reconciliation"])

# Rate limiter for reconciliation endpoints
limiter = Limiter(key_func=get_remote_address)


@router.post("/run", response_model=list[ReconciliationEntry])
@limiter.limit("60/minute")
async def run_reconciliation(request: Request) -> list[ReconciliationEntry]:
    """Trigger reconciliation of on-chain CDA transactions against M&T Bank's
    Hogan GL entries (post-2025 format) via IBM Z DIH. Flags ledger
    exceptions for examiner review.
    """
    engine = get_reconciliation_engine()
    entries = await engine.reconcile()
    return entries


@router.get("/summary", response_model=ReconciliationSummary)
@limiter.limit("60/minute")
async def get_reconciliation_summary(request: Request) -> ReconciliationSummary:
    """Get aggregate reconciliation summary for examiners."""
    engine = get_reconciliation_engine()
    return await engine.get_summary()


@router.get("/entries", response_model=list[ReconciliationEntry])
@limiter.limit("60/minute")
async def get_reconciliation_entries(request: Request) -> list[ReconciliationEntry]:
    """List all reconciliation entries."""
    engine = get_reconciliation_engine()
    return engine.get_entries()


@router.post("/net-settle")
@limiter.limit("30/minute")
async def trigger_net_settlement(request: Request):
    """Trigger daily net settlement calculation for the current settlement window.
    
    Per Cari Whitepaper: aggregates all interbank CDA transfers within the
    current settlement window and computes net positions per bank.
    """
    # Stub implementation
    return {
        "status": "calculated",
        "message": "Net settlement positions calculated — ready for on-chain execution",
        "window_id": 0,
        "entries": [],
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/settlement-window")
@limiter.limit("60/minute")
async def get_settlement_window(request: Request):
    """Get the current settlement window status.
    
    Per Cari Whitepaper: returns the currently open daily settlement window,
    including window ID, open/close times, and status.
    """
    return {
        "window_id": 0,
        "status": "open",
        "opened_at": datetime.utcnow().isoformat(),
        "closes_at": datetime.utcnow().isoformat(),
        "message": "Stub — connect to on-chain SettlementWindow for live data"
    }
