"""
Wallet Tiering Strategy — automated movement rules for hot/warm/cold.
Manages reserve allocation across custody tiers with policy-driven rebalancing.

Implements:
- Tier-specific balance thresholds and operational limits
- Automated rebalancing triggers (low watermark / high watermark)
- Cooldown periods between movements
- Integration with custody adapters (Quest 2) and signing policy

the Issuing Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from offchain.models.schemas import CustodyTier
from offchain.services import audit

logger = logging.getLogger("cari.security.wallet_tiering")


class RebalanceAction(str, Enum):
    MOVE_TO_HOT = "MOVE_TO_HOT"
    MOVE_TO_WARM = "MOVE_TO_WARM"
    MOVE_TO_COLD = "MOVE_TO_COLD"
    NO_ACTION = "NO_ACTION"


class TierPolicy(BaseModel):
    """Policy for a single custody tier."""
    tier: CustodyTier
    min_balance_usd: float = 0.0
    max_balance_usd: float = float("inf")
    low_watermark_usd: float = 0.0   # Trigger refill when balance drops below
    high_watermark_usd: float = float("inf")  # Trigger drain when balance exceeds
    max_single_withdrawal_usd: float = float("inf")
    cooldown_minutes: int = 0  # Minimum time between movements


class WalletTieringPolicy(BaseModel):
    """Complete tiering policy across all tiers."""
    tiers: dict[str, TierPolicy] = Field(default_factory=lambda: {
        CustodyTier.HOT.value: TierPolicy(
            tier=CustodyTier.HOT,
            min_balance_usd=100_000.0,
            max_balance_usd=1_000_000.0,
            low_watermark_usd=200_000.0,
            high_watermark_usd=800_000.0,
            max_single_withdrawal_usd=250_000.0,
            cooldown_minutes=5,
        ),
        CustodyTier.WARM.value: TierPolicy(
            tier=CustodyTier.WARM,
            min_balance_usd=500_000.0,
            max_balance_usd=10_000_000.0,
            low_watermark_usd=1_000_000.0,
            high_watermark_usd=8_000_000.0,
            max_single_withdrawal_usd=2_000_000.0,
            cooldown_minutes=30,
        ),
        CustodyTier.COLD.value: TierPolicy(
            tier=CustodyTier.COLD,
            min_balance_usd=0.0,
            max_balance_usd=float("inf"),
            low_watermark_usd=0.0,
            high_watermark_usd=float("inf"),
            max_single_withdrawal_usd=10_000_000.0,
            cooldown_minutes=60,
        ),
    })


class RebalanceRecommendation(BaseModel):
    """A recommended rebalancing action."""
    recommendation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    action: RebalanceAction
    from_tier: CustodyTier
    to_tier: CustodyTier
    amount_usd: float
    reason: str
    priority: str = "NORMAL"  # "URGENT" | "NORMAL" | "LOW"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executed: bool = False


class RebalanceEvent(BaseModel):
    """Record of an executed rebalance."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_tier: CustodyTier
    to_tier: CustodyTier
    amount_usd: float
    reason: str
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    approved_by: list[str] = Field(default_factory=list)


class WalletTieringEngine:
    """Evaluates balances against policy and generates rebalance recommendations."""

    def __init__(self, policy: WalletTieringPolicy | None = None) -> None:
        self._policy = policy or WalletTieringPolicy()
        self._last_rebalance: dict[str, datetime] = {}
        self._history: list[RebalanceEvent] = []

    async def evaluate(
        self, balances: dict[CustodyTier, float]
    ) -> list[RebalanceRecommendation]:
        """Evaluate current balances and recommend rebalancing actions."""
        recommendations: list[RebalanceRecommendation] = []

        for tier_key, tier_policy in self._policy.tiers.items():
            tier = CustodyTier(tier_key)
            balance = balances.get(tier, 0.0)

            # Check cooldown
            last = self._last_rebalance.get(tier_key)
            if last:
                elapsed = (datetime.now(timezone.utc) - last).total_seconds() / 60
                if elapsed < tier_policy.cooldown_minutes:
                    continue

            # Below low watermark — needs refill
            if balance < tier_policy.low_watermark_usd and tier != CustodyTier.COLD:
                deficit = tier_policy.low_watermark_usd - balance
                # Refill from the next colder tier
                source = CustodyTier.WARM if tier == CustodyTier.HOT else CustodyTier.COLD
                recommendations.append(RebalanceRecommendation(
                    action=RebalanceAction.MOVE_TO_HOT if tier == CustodyTier.HOT else RebalanceAction.MOVE_TO_WARM,
                    from_tier=source,
                    to_tier=tier,
                    amount_usd=min(deficit, tier_policy.max_single_withdrawal_usd),
                    reason=f"{tier.value} below low watermark: ${balance:,.2f} < ${tier_policy.low_watermark_usd:,.2f}",
                    priority="URGENT" if balance < tier_policy.min_balance_usd else "NORMAL",
                ))

            # Above high watermark — drain excess
            if balance > tier_policy.high_watermark_usd and tier != CustodyTier.COLD:
                excess = balance - tier_policy.high_watermark_usd
                dest = CustodyTier.WARM if tier == CustodyTier.HOT else CustodyTier.COLD
                recommendations.append(RebalanceRecommendation(
                    action=RebalanceAction.MOVE_TO_COLD if dest == CustodyTier.COLD else RebalanceAction.MOVE_TO_WARM,
                    from_tier=tier,
                    to_tier=dest,
                    amount_usd=min(excess, tier_policy.max_single_withdrawal_usd),
                    reason=f"{tier.value} above high watermark: ${balance:,.2f} > ${tier_policy.high_watermark_usd:,.2f}",
                    priority="LOW",
                ))

        if recommendations:
            await audit.record(
                actor="WALLET_TIERING",
                action="evaluate",
                resource="custody_tiers",
                details={
                    "recommendations": len(recommendations),
                    "balances": {t.value: b for t, b in balances.items()},
                },
            )

        return recommendations

    async def record_rebalance(
        self,
        *,
        from_tier: CustodyTier,
        to_tier: CustodyTier,
        amount_usd: float,
        reason: str,
        approved_by: list[str] | None = None,
    ) -> RebalanceEvent:
        """Record an executed rebalance event."""
        event = RebalanceEvent(
            from_tier=from_tier,
            to_tier=to_tier,
            amount_usd=amount_usd,
            reason=reason,
            approved_by=approved_by or [],
        )
        self._history.append(event)
        self._last_rebalance[from_tier.value] = datetime.now(timezone.utc)

        await audit.record(
            actor="WALLET_TIERING",
            action="rebalance_executed",
            resource=f"custody:{from_tier.value}->{to_tier.value}",
            details={
                "amount_usd": amount_usd,
                "approved_by": approved_by or [],
            },
        )
        return event

    def get_history(self) -> list[RebalanceEvent]:
        return list(self._history)


_engine: WalletTieringEngine | None = None


def get_tiering_engine() -> WalletTieringEngine:
    global _engine
    if _engine is None:
        _engine = WalletTieringEngine()
    return _engine
