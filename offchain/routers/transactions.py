"""
Mint & Burn router — Cari deposit (CDA) issuance and redemption.
Handles the full lifecycle: compliance check -> core banking -> on-chain -> audit.

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
    BurnRequest,
    ComplianceStatus,
    MintRequest,
    PaymentRail,
    TransactionResponse,
    TransactionStatus,
    TransactionType,
)
from offchain.services import audit
from offchain.services.compliance import ComplianceService
from offchain.services.reserves import get_reserve_service
from integration.core_banking.adapter import get_core_banking_adapter, GLEntry, GLEntryType
from integration.payments_rails.adapter import get_payment_adapter
from middleware.events import get_event_middleware

logger = logging.getLogger("cari.router.transactions")

router = APIRouter(prefix="/transactions", tags=["Transactions"])

# Rate limiter for transactions endpoints
limiter = Limiter(key_func=get_remote_address)


def _usd_to_tokens(usd: float) -> int:
    """Convert USD to 6-decimal CDA token units."""
    return int(usd * 1_000_000)


# TODO: Add Operator authorization middleware — verify request originates from
# authenticated Operator entity per Cari Whitepaper governance requirements.


@router.post("/mint", response_model=TransactionResponse)
@limiter.limit("30/minute")
async def mint_tokenized_deposit(request: Request, mint_request: Annotated[MintRequest, Body(...)]) -> TransactionResponse:
    """Operator-initiated CDA mint: converts DDA (fiat) deposit to CDA (on-chain).
    
    Per Cari Whitepaper, only the designated Operator (the Issuing Bank) can mint CDA.

    Flow:
    1. Compliance screening (BSA/AML/OFAC)
    2. Core banking DDA deposit verification
    3. Reserve pre-check (GENIUS Act S4)
    4. On-chain CDA mint
    5. GL entry posting
    6. Event publication
    """
    settings = get_settings()
    tx_id = str(uuid.uuid4())
    correlation_id = f"mint-{tx_id[:8]}"
    token_amount = _usd_to_tokens(mint_request.amount_usd)

    await audit.record(
        actor="API",
        action="mint_request",
        resource=f"address:{mint_request.to_address}",
        details={"amount_usd": mint_request.amount_usd, "reference_id": mint_request.reference_id},
        correlation_id=correlation_id,
    )

    # 1. Compliance screening
    compliance = ComplianceService()
    screening = await compliance.screen_address(mint_request.to_address)
    if screening.status in (ComplianceStatus.BLOCKED, ComplianceStatus.FLAGGED):
        return TransactionResponse(
            transaction_id=tx_id,
            tx_type=TransactionType.MINT,
            status=TransactionStatus.REJECTED,
            amount_usd=mint_request.amount_usd,
            token_amount=token_amount,
            reference_id=mint_request.reference_id,
            compliance_status=screening.status,
            message=f"Compliance rejected: {screening.details}",
        )

    # 2. Verify fiat deposit at the Issuing Bank core banking
    core_banking = get_core_banking_adapter()
    deposit_check = await core_banking.verify_deposit(
        account_id=mint_request.depositor_account_id,
        reference_id=mint_request.reference_id,
        amount_usd=mint_request.amount_usd,
    )
    if not deposit_check.verified:
        return TransactionResponse(
            transaction_id=tx_id,
            tx_type=TransactionType.MINT,
            status=TransactionStatus.FAILED,
            amount_usd=mint_request.amount_usd,
            token_amount=token_amount,
            reference_id=mint_request.reference_id,
            message=f"Deposit verification failed: {deposit_check.message}",
        )

    # 3. Reserve pre-check
    reserve_svc = get_reserve_service()
    allowed, reason = await reserve_svc.check_mint_allowed(token_amount)
    if not allowed:
        return TransactionResponse(
            transaction_id=tx_id,
            tx_type=TransactionType.MINT,
            status=TransactionStatus.FAILED,
            amount_usd=mint_request.amount_usd,
            token_amount=token_amount,
            reference_id=mint_request.reference_id,
            message=f"Reserve check failed: {reason}",
        )

    # 4. On-chain mint (stub — in production uses BlockchainService)
    tx_hash = f"0x{uuid.uuid4().hex}"
    await audit.record(
        actor="BLOCKCHAIN",
        action="mint",
        resource=f"token:{mint_request.to_address}",
        details={
            "tx_hash": tx_hash,
            "amount": token_amount,
            "reference_id": mint_request.reference_id,
        },
        correlation_id=correlation_id,
    )

    # 5. Post GL entries (double-entry: debit cash, credit liability)
    gl_entries = [
        GLEntry(
            account_number="1010-RESERVE-CASH",
            entry_type=GLEntryType.DEBIT,
            amount_usd=mint_request.amount_usd,
            reference_id=mint_request.reference_id,
            description=f"CDA mint (DDA->CDA) — {mint_request.reference_id} [MT-GL-POST2025]",
            gl_code="1010",
        ),
        GLEntry(
            account_number="2010-TOKEN-LIABILITY",
            entry_type=GLEntryType.CREDIT,
            amount_usd=mint_request.amount_usd,
            reference_id=mint_request.reference_id,
            description=f"CDA liability — {mint_request.reference_id} [MT-GL-POST2025]",
            gl_code="2010",
        ),
    ]
    await core_banking.post_gl_entries(gl_entries)

    # 6. Publish event
    middleware = get_event_middleware()
    await middleware.publish(
        topic=settings.kafka_topic_transactions,
        event_type="MINT_COMPLETED",
        payload={
            "tx_hash": tx_hash,
            "amount_usd": mint_request.amount_usd,
            "to_address": mint_request.to_address,
            "reference_id": mint_request.reference_id,
        },
        correlation_id=correlation_id,
    )

    return TransactionResponse(
        transaction_id=tx_id,
        tx_type=TransactionType.MINT,
        status=TransactionStatus.CONFIRMED,
        amount_usd=mint_request.amount_usd,
        token_amount=token_amount,
        reference_id=mint_request.reference_id,
        tx_hash=tx_hash,
        compliance_status=ComplianceStatus.PASSED,
        message="Cari deposit (CDA) minted successfully",
    )


@router.post("/burn", response_model=TransactionResponse)
@limiter.limit("30/minute")
async def burn_tokenized_deposit(request: Request, burn_request: Annotated[BurnRequest, Body(...)]) -> TransactionResponse:
    """Operator-initiated CDA burn: redeems CDA (on-chain) back to DDA (fiat).
    
    Per Cari Whitepaper, only the designated Operator (the Issuing Bank) can burn CDA.

    CDA burn triggers fiat settlement back to depositor's DDA.

    Flow:
    1. Compliance screening
    2. On-chain CDA burn
    3. GL entry posting (reverse mint entries)
    4. Initiate fiat payout to DDA via selected rail
    5. Event publication
    """
    settings = get_settings()
    tx_id = str(uuid.uuid4())
    correlation_id = f"burn-{tx_id[:8]}"
    token_amount = _usd_to_tokens(burn_request.amount_usd)

    await audit.record(
        actor="API",
        action="burn_request",
        resource=f"address:{burn_request.from_address}",
        details={"amount_usd": burn_request.amount_usd, "reference_id": burn_request.reference_id},
        correlation_id=correlation_id,
    )

    # 1. Compliance screening
    compliance = ComplianceService()
    screening = await compliance.screen_address(burn_request.from_address)
    if screening.status == ComplianceStatus.BLOCKED:
        return TransactionResponse(
            transaction_id=tx_id,
            tx_type=TransactionType.BURN,
            status=TransactionStatus.REJECTED,
            amount_usd=burn_request.amount_usd,
            token_amount=token_amount,
            reference_id=burn_request.reference_id,
            compliance_status=screening.status,
            message=f"Compliance rejected: {screening.details}",
        )

    # 2. On-chain burn (stub)
    tx_hash = f"0x{uuid.uuid4().hex}"
    await audit.record(
        actor="BLOCKCHAIN",
        action="burn",
        resource=f"token:{burn_request.from_address}",
        details={
            "tx_hash": tx_hash,
            "amount": token_amount,
            "reference_id": burn_request.reference_id,
        },
        correlation_id=correlation_id,
    )

    # 3. GL entries (reverse: debit liability, credit cash)
    core_banking = get_core_banking_adapter()
    gl_entries = [
        GLEntry(
            account_number="2010-TOKEN-LIABILITY",
            entry_type=GLEntryType.DEBIT,
            amount_usd=burn_request.amount_usd,
            reference_id=burn_request.reference_id,
            description=f"CDA burn (CDA->DDA) — {burn_request.reference_id} [MT-GL-POST2025]",
            gl_code="2010",
        ),
        GLEntry(
            account_number="1010-RESERVE-CASH",
            entry_type=GLEntryType.CREDIT,
            amount_usd=burn_request.amount_usd,
            reference_id=burn_request.reference_id,
            description=f"Reserve cash release — {burn_request.reference_id} [MT-GL-POST2025]",
            gl_code="1010",
        ),
    ]
    await core_banking.post_gl_entries(gl_entries)

    # 4. Initiate fiat payout
    payment_adapter = get_payment_adapter(burn_request.payment_rail)
    payout_result = await payment_adapter.send_payment(
        destination_account=burn_request.destination_account_id,
        amount_usd=burn_request.amount_usd,
        reference_id=burn_request.reference_id,
    )

    # 5. Publish event
    middleware = get_event_middleware()
    await middleware.publish(
        topic=settings.kafka_topic_transactions,
        event_type="BURN_COMPLETED",
        payload={
            "tx_hash": tx_hash,
            "amount_usd": burn_request.amount_usd,
            "from_address": burn_request.from_address,
            "reference_id": burn_request.reference_id,
            "payout_trace": payout_result.trace_number,
            "payout_rail": burn_request.payment_rail.value,
        },
        correlation_id=correlation_id,
    )

    return TransactionResponse(
        transaction_id=tx_id,
        tx_type=TransactionType.BURN,
        status=TransactionStatus.CONFIRMED,
        amount_usd=burn_request.amount_usd,
        token_amount=token_amount,
        reference_id=burn_request.reference_id,
        tx_hash=tx_hash,
        compliance_status=ComplianceStatus.PASSED,
        message=f"Par redemption completed (CDA->DDA). Payout via {burn_request.payment_rail.value}: {payout_result.trace_number}",
    )
