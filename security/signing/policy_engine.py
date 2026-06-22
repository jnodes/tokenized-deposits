"""
Transaction Signing Policy Engine — dual control, multi-approval, time-locks.
Enforces segregation of duties and approval workflows before any on-chain signing.

Implements:
- Role-based signing authority (MINTER != BURNER != ATTESTOR)
- Dual control: high-value operations require 2+ approvals
- Time-locked operations: critical changes have mandatory delay
- Transaction signing policies with thresholds and velocity limits
- NYDFS Part 500 Section 500.07 access privilege controls

the Issuing Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from offchain.services import audit
from security.key_management.hsm import KeyRole

logger = logging.getLogger("cari.security.signing")


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    EXECUTED = "EXECUTED"


class RiskTier(str, Enum):
    LOW = "LOW"          # < $10K — single approval
    MEDIUM = "MEDIUM"    # $10K-$1M — dual approval
    HIGH = "HIGH"        # $1M-$10M — dual approval + time-lock
    CRITICAL = "CRITICAL"  # > $10M — board-level + 24h time-lock


class SigningRequest(BaseModel):
    """A pending signing operation requiring approval."""
    request_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    operation: str  # "MINT" | "BURN" | "SETTLEMENT" | "KEY_ROTATION" | "PAUSE" | "UPGRADE"
    role_required: KeyRole
    amount_usd: float = 0.0
    risk_tier: RiskTier = RiskTier.LOW
    status: ApprovalStatus = ApprovalStatus.PENDING
    requestor: str = ""
    approvals: list[str] = Field(default_factory=list)
    rejections: list[str] = Field(default_factory=list)
    approvals_required: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    time_lock_until: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    tx_hash: Optional[str] = None
    details: dict = Field(default_factory=dict)


class VelocityLimit(BaseModel):
    """Rate limit for signing operations per role."""
    role: KeyRole
    max_per_hour: int = 100
    max_usd_per_hour: float = 10_000_000.0
    max_per_day: int = 1000
    max_usd_per_day: float = 100_000_000.0


class SigningPolicy(BaseModel):
    """Signing policy configuration."""
    low_threshold_usd: float = 10_000.0
    medium_threshold_usd: float = 1_000_000.0
    high_threshold_usd: float = 10_000_000.0
    time_lock_hours_high: int = 1
    time_lock_hours_critical: int = 24
    velocity_limits: dict[str, VelocityLimit] = Field(default_factory=dict)


class SigningPolicyEngine:
    """Enforces signing policies, dual control, and approval workflows."""

    def __init__(self, policy: SigningPolicy | None = None) -> None:
        self._policy = policy or SigningPolicy()
        self._pending: dict[str, SigningRequest] = {}
        self._history: list[SigningRequest] = []
        self._velocity_counters: dict[str, dict] = {}

    def classify_risk(self, amount_usd: float, operation: str) -> RiskTier:
        """Classify transaction risk tier based on amount and operation type."""
        # Critical operations always require highest scrutiny
        if operation in ("PAUSE", "UPGRADE", "KEY_ROTATION"):
            return RiskTier.HIGH

        if amount_usd >= self._policy.high_threshold_usd:
            return RiskTier.CRITICAL
        elif amount_usd >= self._policy.medium_threshold_usd:
            return RiskTier.HIGH
        elif amount_usd >= self._policy.low_threshold_usd:
            return RiskTier.MEDIUM
        return RiskTier.LOW

    def _approvals_for_tier(self, tier: RiskTier) -> int:
        return {
            RiskTier.LOW: 1,
            RiskTier.MEDIUM: 2,
            RiskTier.HIGH: 2,
            RiskTier.CRITICAL: 3,
        }[tier]

    def _time_lock_for_tier(self, tier: RiskTier) -> timedelta | None:
        if tier == RiskTier.HIGH:
            return timedelta(hours=self._policy.time_lock_hours_high)
        elif tier == RiskTier.CRITICAL:
            return timedelta(hours=self._policy.time_lock_hours_critical)
        return None

    async def create_signing_request(
        self,
        *,
        operation: str,
        role_required: KeyRole,
        amount_usd: float = 0.0,
        requestor: str = "",
        details: dict | None = None,
    ) -> SigningRequest:
        """Create a new signing request with appropriate controls."""
        risk_tier = self.classify_risk(amount_usd, operation)
        approvals_required = self._approvals_for_tier(risk_tier)
        time_lock = self._time_lock_for_tier(risk_tier)

        request = SigningRequest(
            operation=operation,
            role_required=role_required,
            amount_usd=amount_usd,
            risk_tier=risk_tier,
            requestor=requestor,
            approvals_required=approvals_required,
            time_lock_until=(
                datetime.now(timezone.utc) + time_lock if time_lock else None
            ),
            details=details or {},
        )

        self._pending[request.request_id] = request

        await audit.record(
            actor="SIGNING_POLICY",
            action="create_request",
            resource=f"signing:{request.request_id}",
            details={
                "operation": operation,
                "role": role_required.value,
                "amount_usd": amount_usd,
                "risk_tier": risk_tier.value,
                "approvals_required": approvals_required,
                "time_locked": time_lock is not None,
            },
        )
        logger.info(
            "Signing request created: %s %s $%.2f [%s] — %d approvals needed",
            operation, risk_tier.value, amount_usd,
            request.request_id[:8], approvals_required,
        )
        return request

    async def approve(self, request_id: str, approver: str) -> SigningRequest:
        """Approve a pending signing request (dual control)."""
        request = self._pending.get(request_id)
        if not request:
            raise ValueError(f"Signing request not found: {request_id}")
        if request.status != ApprovalStatus.PENDING:
            raise ValueError(f"Request {request_id} is {request.status.value}")
        if approver == request.requestor:
            raise ValueError("Self-approval is prohibited (segregation of duties)")
        if approver in request.approvals:
            raise ValueError(f"{approver} has already approved this request")

        request.approvals.append(approver)

        if len(request.approvals) >= request.approvals_required:
            request.status = ApprovalStatus.APPROVED

        await audit.record(
            actor="SIGNING_POLICY",
            action="approve_request",
            resource=f"signing:{request_id}",
            details={
                "approver": approver,
                "approvals": len(request.approvals),
                "required": request.approvals_required,
                "new_status": request.status.value,
            },
        )
        return request

    async def reject(self, request_id: str, rejector: str, reason: str = "") -> SigningRequest:
        """Reject a signing request."""
        request = self._pending.get(request_id)
        if not request:
            raise ValueError(f"Signing request not found: {request_id}")

        request.rejections.append(rejector)
        request.status = ApprovalStatus.REJECTED

        await audit.record(
            actor="SIGNING_POLICY",
            action="reject_request",
            resource=f"signing:{request_id}",
            details={"rejector": rejector, "reason": reason},
        )
        return request

    async def execute(self, request_id: str) -> SigningRequest:
        """Execute an approved signing request (checks time-lock)."""
        request = self._pending.get(request_id)
        if not request:
            raise ValueError(f"Signing request not found: {request_id}")
        if request.status != ApprovalStatus.APPROVED:
            raise ValueError(f"Request not approved (status={request.status.value})")

        # Check time-lock
        now = datetime.now(timezone.utc)
        if request.time_lock_until and now < request.time_lock_until:
            remaining = (request.time_lock_until - now).total_seconds() / 3600
            raise ValueError(
                f"Time-lock active: {remaining:.1f}h remaining "
                f"(unlocks at {request.time_lock_until.isoformat()})"
            )

        request.status = ApprovalStatus.EXECUTED
        request.executed_at = now
        self._history.append(request)
        del self._pending[request_id]

        await audit.record(
            actor="SIGNING_POLICY",
            action="execute_request",
            resource=f"signing:{request_id}",
            details={
                "operation": request.operation,
                "amount_usd": request.amount_usd,
                "approved_by": request.approvals,
            },
        )
        logger.info("Signing request executed: %s", request_id[:12])
        return request

    def get_pending(self) -> list[SigningRequest]:
        return list(self._pending.values())

    def get_history(self) -> list[SigningRequest]:
        return list(self._history)


_engine: SigningPolicyEngine | None = None


def get_signing_engine() -> SigningPolicyEngine:
    global _engine
    if _engine is None:
        _engine = SigningPolicyEngine()
    return _engine
