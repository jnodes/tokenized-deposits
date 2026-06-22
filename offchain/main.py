"""
the Issuing Bank Cari Deposit Orchestrator — FastAPI Application.
Connects Quest 1 smart contracts to the Issuing Bank's core banking, custody, and compliance stack.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
DDA <-> CDA flow: fiat in DDA triggers CDA mint; CDA burn triggers fiat back to DDA.

the Issuing Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from offchain.config import Environment, Settings, get_settings
from offchain.routers import compliance, health, reconciliation, reserves, settlement, transactions
from middleware.events import get_event_middleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("cari.app")

# Global rate limiter instance
limiter = Limiter(key_func=get_remote_address)


def _validate_production_readiness(settings: Settings) -> None:
    """Prevent stub implementations from running in production.
    
    Checks for:
    - HSM provider configuration (not stub/local_dev)
    - Raw private keys (must use HSM in production)
    - CORS configuration (must be explicitly set)
    """
    issues: list[str] = []
    
    if settings.environment == Environment.PRODUCTION:
        # Check HSM provider
        if not settings.hsm_provider or settings.hsm_provider == "local_dev":
            issues.append("HSM provider not configured (stub HSM detected)")
        
        # Check that raw private keys are not being used
        if settings.minter_private_key:
            issues.append("Raw minter private key set — must use HSM in production")
        if settings.burner_private_key:
            issues.append("Raw burner private key set — must use HSM in production")
        if settings.attestor_private_key:
            issues.append("Raw attestor private key set — must use HSM in production")
        if settings.compliance_private_key:
            issues.append("Raw compliance private key set — must use HSM in production")
        if settings.settlement_private_key:
            issues.append("Raw settlement private key set — must use HSM in production")
        
        # Check Operator configuration
        if not settings.operator_address:
            issues.append("Operator address not configured — required per Cari Whitepaper")
        
        # Check CORS
        if not settings.cors_allowed_origins:
            issues.append("CORS allowed origins not configured for production")
        
        if issues:
            for issue in issues:
                logger.critical("PRODUCTION SAFETY CHECK FAILED: %s", issue)
            raise RuntimeError(
                f"Cannot start in production — {len(issues)} safety check(s) failed: "
                + "; ".join(issues)
            )
    
    elif settings.environment == Environment.STAGING:
        # Warnings only for staging
        if not settings.hsm_provider or settings.hsm_provider == "local_dev":
            logger.warning("STAGING WARNING: HSM provider not configured — using stub")
        if settings.minter_private_key:
            logger.warning("STAGING WARNING: Raw minter private key detected — use HSM for production")
        if settings.burner_private_key:
            logger.warning("STAGING WARNING: Raw burner private key detected — use HSM for production")
        if settings.attestor_private_key:
            logger.warning("STAGING WARNING: Raw attestor private key detected — use HSM for production")
        if settings.compliance_private_key:
            logger.warning("STAGING WARNING: Raw compliance private key detected — use HSM for production")
        if settings.settlement_private_key:
            logger.warning("STAGING WARNING: Raw settlement private key detected — use HSM for production")
        if not settings.cors_allowed_origins:
            logger.warning("STAGING WARNING: CORS allowed origins not configured — configure for production")
        if not settings.operator_address:
            logger.warning("STAGING WARNING: Operator address not configured")


def _validate_cors_configuration(settings: Settings) -> None:
    """Validate CORS configuration for production environments.
    
    Prevents the application from starting if CORS is misconfigured in production.
    """
    if settings.environment == Environment.PRODUCTION:
        # In production, CORS origins must be explicitly configured
        if not settings.cors_allowed_origins:
            raise RuntimeError(
                "SECURITY: Cannot start production without explicit CORS origins configured. "
                "Set CARI_CORS_ALLOWED_ORIGINS environment variable."
            )
        # Ensure wildcard is not in the allowed origins
        if "*" in settings.cors_allowed_origins:
            raise RuntimeError(
                "SECURITY: Cannot start production with wildcard CORS origins. "
                "Configure specific allowed origins in CARI_CORS_ALLOWED_ORIGINS."
            )
    elif settings.environment == Environment.STAGING:
        if not settings.cors_allowed_origins:
            logger.warning(
                "STAGING: CORS origins not configured — using empty list. "
                "Configure CARI_CORS_ALLOWED_ORIGINS for production-like testing."
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hooks."""
    settings = get_settings()
    logger.info("Starting %s [%s]", settings.app_name, settings.environment.value)

    # Production safety checks — prevent stub implementations in production
    _validate_production_readiness(settings)
    
    # CORS configuration validation
    _validate_cors_configuration(settings)

    # Start event middleware (Kafka + Redis)
    middleware = get_event_middleware()
    await middleware.startup()

    logger.info("All services initialized")
    yield

    # Shutdown
    logger.info("Shutting down...")
    await middleware.shutdown()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Off-chain orchestration platform for the Issuing Bank's Cari deposit product (CDA/DDA). "
            "Connects ZKsync Prividium smart contracts to core banking, custody, payments, "
            "and regulatory compliance infrastructure. GENIUS Act compliant."
        ),
        version="1.0.0",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    # Rate limiting middleware
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS — environment-specific configuration
    if settings.environment == Environment.DEV:
        # Development: allow all origins for local testing
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    else:
        # Staging/Production: use explicitly configured origins
        allowed_origins = settings.cors_allowed_origins if settings.cors_allowed_origins else []
        app.add_middleware(
            CORSMiddleware,
            allow_origins=allowed_origins,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Correlation-ID"],
        )
        if settings.environment == Environment.STAGING and not allowed_origins:
            logger.warning("CORS configured with empty origins list for staging environment")

    # Mount routers under api prefix
    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(transactions.router, prefix=settings.api_prefix)
    app.include_router(settlement.router, prefix=settings.api_prefix)
    app.include_router(reconciliation.router, prefix=settings.api_prefix)
    app.include_router(reserves.router, prefix=settings.api_prefix)
    app.include_router(compliance.router, prefix=settings.api_prefix)

    # Root health endpoint (no prefix — for load balancers)
    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
