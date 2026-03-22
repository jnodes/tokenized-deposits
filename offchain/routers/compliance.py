"""
Compliance & Audit router — screening endpoints and examiner audit trail.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
All CDA/DDA operations are screened for BSA/AML/OFAC compliance.

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from offchain.models.schemas import AuditLogEntry, ComplianceScreeningResult
from offchain.services import audit
from offchain.services.compliance import ComplianceService

logger = logging.getLogger("cari.router.compliance")

router = APIRouter(prefix="/compliance", tags=["Compliance & Audit"])

# Rate limiter for compliance endpoints
limiter = Limiter(key_func=get_remote_address)


@router.get("/screen/{address}", response_model=ComplianceScreeningResult)
@limiter.limit("60/minute")
async def screen_address(request: Request, address: str) -> ComplianceScreeningResult:
    """Screen a wallet address against OFAC/sanctions lists."""
    compliance = ComplianceService()
    return await compliance.screen_address(address)


@router.get("/screen-transaction", response_model=ComplianceScreeningResult)
@limiter.limit("60/minute")
async def screen_transaction(
    request: Request,
    from_address: str = Query(...),
    to_address: str = Query(...),
    amount_usd: float = Query(..., gt=0),
) -> ComplianceScreeningResult:
    """Screen a transaction (both parties) for BSA/AML/OFAC compliance."""
    compliance = ComplianceService()
    return await compliance.screen_transaction(
        from_addr=from_address,
        to_addr=to_address,
        amount_usd=amount_usd,
    )


@router.get("/audit", response_model=list[AuditLogEntry])
@limiter.limit("60/minute")
async def get_audit_log(
    request: Request,
    actor: Optional[str] = Query(None),
    action: Optional[str] = Query(None),
    resource: Optional[str] = Query(None),
    since: Optional[datetime] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
) -> list[AuditLogEntry]:
    """Query the immutable audit trail (OCC/Fed/NYDFS examiner access)."""
    return await audit.query(
        actor=actor,
        action=action,
        resource=resource,
        since=since,
        limit=limit,
    )


@router.get("/audit/full", response_model=list[AuditLogEntry])
@limiter.limit("60/minute")
async def get_full_audit_log(request: Request) -> list[AuditLogEntry]:
    """Export the complete audit trail."""
    return audit.get_full_log()
