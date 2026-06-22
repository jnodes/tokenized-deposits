"""
Settlement router — Cari Network cross-bank CDA settlement endpoints.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
DDA <-> CDA flow: fiat in DDA triggers CDA mint; CDA burn triggers fiat back to DDA.

the Issuing Bank | Cari Network | ZKsync Prividium.
"""

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from offchain.config import get_settings
from offchain.models.schemas import (
    ComplianceStatus,
    SettlementRequest,
    SettlementStatus,
    TransactionResponse,
    TransactionStatus,
    TransactionType,
)
from offchain.services import audit
from offchain.services.compliance import ComplianceService
from middleware.events import get_event_middleware

logger = logging.getLogger("cari.router.settlement")

router = APIRouter(prefix="/settlement", tags=["Settlement"])

# Rate limiter for settlement endpoints
limiter = Limiter(key_func=get_remote_address)


def _usd_to_tokens(usd: float) -> int:
    return int(usd * 1_000_000)


@router.post("/initiate", response_model=TransactionResponse)
@limiter.limit("30/minute")
async def initiate_settlement(request: Request, settlement_request: Annotated[SettlementRequest, Body(...)]) -> TransactionResponse:
    """Initiate a Cari Network cross-bank CDA settlement.

    Flow:
    1. Compliance screening (both parties)
    2. Compute Travel Rule hash (FinCEN >= $3,000)
    3. On-chain CDA settlement initiation (burn CDA at source)
    4. Event publication
    """
    settings = get_settings()
    tx_id = str(uuid.uuid4())
    correlation_id = f"settle-{tx_id[:8]}"
    token_amount = _usd_to_tokens(settlement_request.amount_usd)

    await audit.record(
        actor="API",
        action="settlement_initiate",
        resource=f"cari:{settlement_request.destination_bank}",
        details={
            "amount_usd": settlement_request.amount_usd,
            "originator": settlement_request.originator_address,
            "beneficiary": settlement_request.beneficiary_address,
        },
        correlation_id=correlation_id,
    )

    # 1. Compliance screening on both parties
    compliance = ComplianceService()
    tx_screening = await compliance.screen_transaction(
        from_addr=settlement_request.originator_address,
        to_addr=settlement_request.beneficiary_address,
        amount_usd=settlement_request.amount_usd,
    )
    if tx_screening.status == ComplianceStatus.BLOCKED:
        return TransactionResponse(
            transaction_id=tx_id,
            tx_type=TransactionType.SETTLEMENT_INITIATE,
            status=TransactionStatus.REJECTED,
            amount_usd=settlement_request.amount_usd,
            token_amount=token_amount,
            reference_id=f"SETTLE-{tx_id[:12]}",
            compliance_status=ComplianceStatus.BLOCKED,
            message=f"Settlement blocked by compliance: {tx_screening.details}",
        )

    # 2. Travel Rule hash
    travel_rule_hash = ""
    if settlement_request.amount_usd >= settings.travel_rule_threshold_usd:
        _, _, combined_hash = await compliance.compute_travel_rule_hash(
            originator_name=settlement_request.originator_name,
            originator_institution=settlement_request.originator_institution,
            beneficiary_name=settlement_request.beneficiary_name,
            beneficiary_institution=settlement_request.beneficiary_institution,
        )
        travel_rule_hash = combined_hash.hex()

    # 3. On-chain settlement initiation (stub)
    tx_hash = f"0x{uuid.uuid4().hex}"
    settlement_id_on_chain = f"SETTLE-{uuid.uuid4().hex[:12].upper()}"

    await audit.record(
        actor="BLOCKCHAIN",
        action="settlement_initiate_on_chain",
        resource=f"settlement:{settlement_id_on_chain}",
        details={
            "tx_hash": tx_hash,
            "destination_bank": settlement_request.destination_bank,
            "amount": token_amount,
            "travel_rule_hash": travel_rule_hash,
        },
        correlation_id=correlation_id,
    )

    # 4. Publish event
    middleware = get_event_middleware()
    await middleware.publish(
        topic=settings.kafka_topic_settlements,
        event_type="SETTLEMENT_INITIATED",
        payload={
            "settlement_id": settlement_id_on_chain,
            "tx_hash": tx_hash,
            "amount_usd": settlement_request.amount_usd,
            "destination_bank": settlement_request.destination_bank,
            "originator": settlement_request.originator_address,
            "beneficiary": settlement_request.beneficiary_address,
        },
        correlation_id=correlation_id,
    )

    return TransactionResponse(
        transaction_id=tx_id,
        tx_type=TransactionType.SETTLEMENT_INITIATE,
        status=TransactionStatus.CONFIRMED,
        amount_usd=settlement_request.amount_usd,
        token_amount=token_amount,
        reference_id=settlement_id_on_chain,
        tx_hash=tx_hash,
        compliance_status=ComplianceStatus.PASSED,
        message=f"Settlement initiated with {settlement_request.destination_bank}. "
                f"Settlement ID: {settlement_id_on_chain}",
    )
