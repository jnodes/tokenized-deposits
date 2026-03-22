"""
Reserve & Custody router — reserve status, custody balances, treasury ops.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Reserves ensure 1:1 backing of CDA tokens by qualifying assets (GENIUS Act S4).

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Query, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from offchain.models.schemas import CustodyTier, ReserveStatusResponse
from offchain.services.reserves import get_reserve_service
from integration.custody.adapter import (
    CustodyBalance,
    CustodyTransferResult,
    get_custody_adapter,
)

logger = logging.getLogger("cari.router.reserves")

router = APIRouter(prefix="/reserves", tags=["Reserves & Custody"])

# Rate limiter for reserves endpoints
limiter = Limiter(key_func=get_remote_address)


@router.get("/status", response_model=ReserveStatusResponse)
@limiter.limit("60/minute")
async def get_reserve_status(request: Request) -> ReserveStatusResponse:
    """Get current reserve backing status for CDA tokens (GENIUS Act Section 4 & 6)."""
    reserve_svc = get_reserve_service()
    return await reserve_svc.get_reserve_status()


@router.get("/custody/balances", response_model=list[CustodyBalance])
@limiter.limit("60/minute")
async def get_custody_balances(request: Request) -> list[CustodyBalance]:
    """Get balances across all custody tiers (hot/warm/cold)."""
    custody = get_custody_adapter()
    return await custody.get_all_balances()


@router.get("/custody/{tier}", response_model=CustodyBalance)
@limiter.limit("60/minute")
async def get_custody_tier_balance(request: Request, tier: CustodyTier) -> CustodyBalance:
    """Get balance for a specific custody tier."""
    custody = get_custody_adapter()
    return await custody.get_balance(tier)


@router.post("/custody/rebalance", response_model=CustodyTransferResult)
@limiter.limit("60/minute")
async def rebalance_custody(
    request: Request,
    from_tier: CustodyTier = Query(...),
    to_tier: CustodyTier = Query(...),
    amount_usd: float = Query(..., gt=0),
) -> CustodyTransferResult:
    """Rebalance funds between custody tiers (e.g., cold -> hot for liquidity)."""
    custody = get_custody_adapter()
    return await custody.rebalance(
        from_tier=from_tier,
        to_tier=to_tier,
        amount_usd=amount_usd,
    )
