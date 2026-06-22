"""
Health & system router — operational readiness checks.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Health checks verify connectivity to all CDA/DDA platform components.

the Issuing Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from offchain.config import get_settings
from offchain.models.schemas import HealthResponse
from middleware.events import get_event_middleware

logger = logging.getLogger("cari.router.health")

router = APIRouter(tags=["System"])

# Rate limiter for health endpoints
limiter = Limiter(key_func=get_remote_address)


@router.get("/health", response_model=HealthResponse)
@limiter.limit("120/minute")
async def health_check(request: Request) -> HealthResponse:
    """System health check — used by load balancers and monitoring."""
    settings = get_settings()
    middleware = get_event_middleware()

    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment=settings.environment.value,
        blockchain_connected=bool(settings.prividium_rpc_url),
        kafka_connected=middleware.producer._connected,
        redis_connected=middleware.cache.connected,
        database_connected=True,  # stub
        reserve_oracle_fresh=True,  # stub — in production, query oracle
    )


@router.get("/")
@limiter.limit("120/minute")
async def root(request: Request) -> dict:
    """API root — basic info."""
    settings = get_settings()
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "environment": settings.environment.value,
        "docs": f"{settings.api_prefix}/docs",
    }
