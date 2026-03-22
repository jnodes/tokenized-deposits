"""
Payment rails adapters — ACH, Fedwire, RTP, FedNow, internal book transfer.
Abstract interface with stub implementations for dev/test.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Payment rails move fiat between DDAs for CDA mint/burn operations.

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from offchain.models.schemas import PaymentRail
from offchain.services import audit

logger = logging.getLogger("cari.payments")


class PaymentResult(BaseModel):
    """Result of a payment rail operation."""
    payment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rail: PaymentRail
    amount_usd: float
    status: str = "COMPLETED"
    reference_id: str = ""
    trace_number: str = ""
    settled_at: Optional[datetime] = None
    message: str = ""


class PaymentRailAdapter(ABC):
    """Abstract payment rail adapter."""

    @abstractmethod
    async def send_payment(
        self,
        *,
        destination_account: str,
        amount_usd: float,
        reference_id: str,
    ) -> PaymentResult:
        ...

    @abstractmethod
    async def receive_notification(self, payload: dict) -> PaymentResult:
        """Process an inbound payment notification (webhook)."""
        ...


class ACHAdapter(PaymentRailAdapter):
    """ACH (Automated Clearing House) adapter stub."""

    async def send_payment(
        self, *, destination_account: str, amount_usd: float, reference_id: str
    ) -> PaymentResult:
        result = PaymentResult(
            rail=PaymentRail.ACH,
            amount_usd=amount_usd,
            reference_id=reference_id,
            trace_number=f"ACH-{uuid.uuid4().hex[:10].upper()}",
            settled_at=datetime.utcnow(),
            message="ACH payment submitted (stub — T+1 settlement)",
        )
        await audit.record(
            actor="PAYMENTS_ACH", action="send_payment",
            resource=f"account:{destination_account}",
            details={"amount_usd": amount_usd, "trace": result.trace_number},
        )
        return result

    async def receive_notification(self, payload: dict) -> PaymentResult:
        return PaymentResult(rail=PaymentRail.ACH, amount_usd=payload.get("amount", 0))


class FedwireAdapter(PaymentRailAdapter):
    """Fedwire adapter stub — real-time gross settlement."""

    async def send_payment(
        self, *, destination_account: str, amount_usd: float, reference_id: str
    ) -> PaymentResult:
        result = PaymentResult(
            rail=PaymentRail.FEDWIRE,
            amount_usd=amount_usd,
            reference_id=reference_id,
            trace_number=f"FW-{uuid.uuid4().hex[:12].upper()}",
            settled_at=datetime.utcnow(),
            message="Fedwire payment settled (stub — real-time)",
        )
        await audit.record(
            actor="PAYMENTS_FEDWIRE", action="send_payment",
            resource=f"account:{destination_account}",
            details={"amount_usd": amount_usd, "trace": result.trace_number},
        )
        return result

    async def receive_notification(self, payload: dict) -> PaymentResult:
        return PaymentResult(rail=PaymentRail.FEDWIRE, amount_usd=payload.get("amount", 0))


class RTPAdapter(PaymentRailAdapter):
    """RTP (Real-Time Payments) / FedNow adapter stub."""

    async def send_payment(
        self, *, destination_account: str, amount_usd: float, reference_id: str
    ) -> PaymentResult:
        result = PaymentResult(
            rail=PaymentRail.RTP,
            amount_usd=amount_usd,
            reference_id=reference_id,
            trace_number=f"RTP-{uuid.uuid4().hex[:10].upper()}",
            settled_at=datetime.utcnow(),
            message="RTP/FedNow payment settled (stub — instant)",
        )
        await audit.record(
            actor="PAYMENTS_RTP", action="send_payment",
            resource=f"account:{destination_account}",
            details={"amount_usd": amount_usd, "trace": result.trace_number},
        )
        return result

    async def receive_notification(self, payload: dict) -> PaymentResult:
        return PaymentResult(rail=PaymentRail.RTP, amount_usd=payload.get("amount", 0))


class BookTransferAdapter(PaymentRailAdapter):
    """Internal book transfer (M&T account to M&T account)."""

    async def send_payment(
        self, *, destination_account: str, amount_usd: float, reference_id: str
    ) -> PaymentResult:
        result = PaymentResult(
            rail=PaymentRail.BOOK_TRANSFER,
            amount_usd=amount_usd,
            reference_id=reference_id,
            trace_number=f"BK-{uuid.uuid4().hex[:8].upper()}",
            settled_at=datetime.utcnow(),
            message="Book transfer completed (instant, internal)",
        )
        await audit.record(
            actor="PAYMENTS_BOOK", action="send_payment",
            resource=f"account:{destination_account}",
            details={"amount_usd": amount_usd, "trace": result.trace_number},
        )
        return result

    async def receive_notification(self, payload: dict) -> PaymentResult:
        return PaymentResult(rail=PaymentRail.BOOK_TRANSFER, amount_usd=payload.get("amount", 0))


def get_payment_adapter(rail: PaymentRail) -> PaymentRailAdapter:
    """Factory: return the appropriate payment rail adapter."""
    adapters: dict[PaymentRail, type[PaymentRailAdapter]] = {
        PaymentRail.ACH: ACHAdapter,
        PaymentRail.FEDWIRE: FedwireAdapter,
        PaymentRail.RTP: RTPAdapter,
        PaymentRail.FEDNOW: RTPAdapter,  # FedNow uses same adapter as RTP
        PaymentRail.BOOK_TRANSFER: BookTransferAdapter,
    }
    cls = adapters.get(rail, BookTransferAdapter)
    return cls()
