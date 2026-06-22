"""
Custody service adapters — Fireblocks / Coinbase hot/warm/cold wallet tiering.
Manages secure key custody for on-chain CDA signing operations.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Custody wallets hold CDA tokens and sign CDA mint/burn/transfer transactions.

the Issuing Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from offchain.models.schemas import CustodyTier
from offchain.services import audit

logger = logging.getLogger("cari.custody")


class CustodyBalance(BaseModel):
    """Balance snapshot for a custody tier."""
    tier: CustodyTier
    balance_usd: float
    address: str = ""
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class CustodyTransferResult(BaseModel):
    """Result of a custody deposit or withdrawal."""
    transfer_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    direction: str  # "DEPOSIT" | "WITHDRAWAL" | "REBALANCE"
    tier: CustodyTier
    amount_usd: float
    status: str = "COMPLETED"
    tx_hash: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    message: str = ""


class CustodyAdapter(ABC):
    """Abstract custody adapter — supports hot/warm/cold tiering."""

    @abstractmethod
    async def deposit(
        self, *, tier: CustodyTier, amount_usd: float, reference_id: str
    ) -> CustodyTransferResult:
        """Deposit funds into a custody tier."""
        ...

    @abstractmethod
    async def withdraw(
        self, *, tier: CustodyTier, amount_usd: float, reference_id: str
    ) -> CustodyTransferResult:
        """Withdraw funds from a custody tier."""
        ...

    @abstractmethod
    async def get_balance(self, tier: CustodyTier) -> CustodyBalance:
        """Get balance for a specific tier."""
        ...

    @abstractmethod
    async def get_all_balances(self) -> list[CustodyBalance]:
        """Get balances across all tiers."""
        ...

    @abstractmethod
    async def rebalance(
        self, *, from_tier: CustodyTier, to_tier: CustodyTier, amount_usd: float
    ) -> CustodyTransferResult:
        """Move funds between custody tiers (e.g., cold -> hot for liquidity)."""
        ...


class StubFireblocksCustodyAdapter(CustodyAdapter):
    """Stub Fireblocks custody adapter for dev/test.

    Simulates the Fireblocks vault architecture:
      - HOT:  Fireblocks MPC vault (immediate signing, lower limits)
      - WARM: Fireblocks policy-gated vault (approval required, medium limits)
      - COLD: Fireblocks air-gapped HSM (multi-sig, highest security)

    In production, replace with actual Fireblocks SDK calls.
    """

    TIER_ADDRESSES = {
        CustodyTier.HOT: "0xHOT_FIREBLOCKS_VAULT_001",
        CustodyTier.WARM: "0xWARM_FIREBLOCKS_VAULT_002",
        CustodyTier.COLD: "0xCOLD_FIREBLOCKS_HSM_003",
    }

    # Default operational limits (USD)
    TIER_LIMITS = {
        CustodyTier.HOT: 500_000.0,
        CustodyTier.WARM: 5_000_000.0,
        CustodyTier.COLD: float("inf"),
    }

    def __init__(self) -> None:
        self._balances: dict[CustodyTier, float] = {
            CustodyTier.HOT: 500_000.0,
            CustodyTier.WARM: 2_000_000.0,
            CustodyTier.COLD: 7_500_000.0,
        }

    async def deposit(
        self, *, tier: CustodyTier, amount_usd: float, reference_id: str
    ) -> CustodyTransferResult:
        self._balances[tier] = self._balances.get(tier, 0.0) + amount_usd
        result = CustodyTransferResult(
            direction="DEPOSIT",
            tier=tier,
            amount_usd=amount_usd,
            tx_hash=f"0xfb_dep_{uuid.uuid4().hex[:16]}",
            message=f"Deposited ${amount_usd:,.2f} to Fireblocks {tier.value} vault (stub)",
        )
        await audit.record(
            actor="CUSTODY_FIREBLOCKS",
            action="deposit",
            resource=f"vault:{tier.value}",
            details={
                "amount_usd": amount_usd,
                "reference_id": reference_id,
                "new_balance": self._balances[tier],
            },
        )
        logger.info("Fireblocks deposit: %s vault +$%.2f", tier.value, amount_usd)
        return result

    async def withdraw(
        self, *, tier: CustodyTier, amount_usd: float, reference_id: str
    ) -> CustodyTransferResult:
        current = self._balances.get(tier, 0.0)
        if amount_usd > current:
            return CustodyTransferResult(
                direction="WITHDRAWAL",
                tier=tier,
                amount_usd=amount_usd,
                status="FAILED",
                message=f"Insufficient {tier.value} balance: ${current:,.2f} < ${amount_usd:,.2f}",
            )
        self._balances[tier] = current - amount_usd
        result = CustodyTransferResult(
            direction="WITHDRAWAL",
            tier=tier,
            amount_usd=amount_usd,
            tx_hash=f"0xfb_wd_{uuid.uuid4().hex[:16]}",
            message=f"Withdrew ${amount_usd:,.2f} from Fireblocks {tier.value} vault (stub)",
        )
        await audit.record(
            actor="CUSTODY_FIREBLOCKS",
            action="withdraw",
            resource=f"vault:{tier.value}",
            details={
                "amount_usd": amount_usd,
                "reference_id": reference_id,
                "new_balance": self._balances[tier],
            },
        )
        logger.info("Fireblocks withdraw: %s vault -$%.2f", tier.value, amount_usd)
        return result

    async def get_balance(self, tier: CustodyTier) -> CustodyBalance:
        return CustodyBalance(
            tier=tier,
            balance_usd=self._balances.get(tier, 0.0),
            address=self.TIER_ADDRESSES.get(tier, ""),
        )

    async def get_all_balances(self) -> list[CustodyBalance]:
        return [await self.get_balance(t) for t in CustodyTier]

    async def rebalance(
        self, *, from_tier: CustodyTier, to_tier: CustodyTier, amount_usd: float
    ) -> CustodyTransferResult:
        src = self._balances.get(from_tier, 0.0)
        if amount_usd > src:
            return CustodyTransferResult(
                direction="REBALANCE",
                tier=from_tier,
                amount_usd=amount_usd,
                status="FAILED",
                message=f"Insufficient {from_tier.value} for rebalance: ${src:,.2f}",
            )
        self._balances[from_tier] = src - amount_usd
        self._balances[to_tier] = self._balances.get(to_tier, 0.0) + amount_usd
        result = CustodyTransferResult(
            direction="REBALANCE",
            tier=to_tier,
            amount_usd=amount_usd,
            tx_hash=f"0xfb_rebal_{uuid.uuid4().hex[:12]}",
            message=f"Rebalanced ${amount_usd:,.2f}: {from_tier.value} -> {to_tier.value} (stub)",
        )
        await audit.record(
            actor="CUSTODY_FIREBLOCKS",
            action="rebalance",
            resource="vault:rebalance",
            details={
                "from_tier": from_tier.value,
                "to_tier": to_tier.value,
                "amount_usd": amount_usd,
            },
        )
        logger.info(
            "Fireblocks rebalance: %s -> %s $%.2f",
            from_tier.value, to_tier.value, amount_usd,
        )
        return result


class StubCoinbaseCustodyAdapter(CustodyAdapter):
    """Stub Coinbase Prime custody adapter for dev/test.

    Alternative enterprise custody provider. Same interface, different backend.
    In production, replace with Coinbase Prime API calls.
    """

    def __init__(self) -> None:
        self._balances: dict[CustodyTier, float] = {
            CustodyTier.HOT: 250_000.0,
            CustodyTier.WARM: 1_000_000.0,
            CustodyTier.COLD: 5_000_000.0,
        }

    async def deposit(
        self, *, tier: CustodyTier, amount_usd: float, reference_id: str
    ) -> CustodyTransferResult:
        self._balances[tier] = self._balances.get(tier, 0.0) + amount_usd
        result = CustodyTransferResult(
            direction="DEPOSIT",
            tier=tier,
            amount_usd=amount_usd,
            tx_hash=f"0xcb_dep_{uuid.uuid4().hex[:16]}",
            message=f"Deposited ${amount_usd:,.2f} to Coinbase {tier.value} vault (stub)",
        )
        await audit.record(
            actor="CUSTODY_COINBASE",
            action="deposit",
            resource=f"vault:{tier.value}",
            details={"amount_usd": amount_usd, "reference_id": reference_id},
        )
        return result

    async def withdraw(
        self, *, tier: CustodyTier, amount_usd: float, reference_id: str
    ) -> CustodyTransferResult:
        current = self._balances.get(tier, 0.0)
        if amount_usd > current:
            return CustodyTransferResult(
                direction="WITHDRAWAL", tier=tier, amount_usd=amount_usd,
                status="FAILED",
                message=f"Insufficient {tier.value} balance: ${current:,.2f}",
            )
        self._balances[tier] = current - amount_usd
        result = CustodyTransferResult(
            direction="WITHDRAWAL",
            tier=tier,
            amount_usd=amount_usd,
            tx_hash=f"0xcb_wd_{uuid.uuid4().hex[:16]}",
            message=f"Withdrew ${amount_usd:,.2f} from Coinbase {tier.value} vault (stub)",
        )
        await audit.record(
            actor="CUSTODY_COINBASE",
            action="withdraw",
            resource=f"vault:{tier.value}",
            details={"amount_usd": amount_usd, "reference_id": reference_id},
        )
        return result

    async def get_balance(self, tier: CustodyTier) -> CustodyBalance:
        return CustodyBalance(
            tier=tier,
            balance_usd=self._balances.get(tier, 0.0),
        )

    async def get_all_balances(self) -> list[CustodyBalance]:
        return [await self.get_balance(t) for t in CustodyTier]

    async def rebalance(
        self, *, from_tier: CustodyTier, to_tier: CustodyTier, amount_usd: float
    ) -> CustodyTransferResult:
        src = self._balances.get(from_tier, 0.0)
        if amount_usd > src:
            return CustodyTransferResult(
                direction="REBALANCE", tier=from_tier, amount_usd=amount_usd,
                status="FAILED",
                message=f"Insufficient {from_tier.value} for rebalance",
            )
        self._balances[from_tier] = src - amount_usd
        self._balances[to_tier] = self._balances.get(to_tier, 0.0) + amount_usd
        result = CustodyTransferResult(
            direction="REBALANCE",
            tier=to_tier,
            amount_usd=amount_usd,
            tx_hash=f"0xcb_rebal_{uuid.uuid4().hex[:12]}",
            message=f"Rebalanced ${amount_usd:,.2f}: {from_tier.value} -> {to_tier.value} (stub)",
        )
        await audit.record(
            actor="CUSTODY_COINBASE",
            action="rebalance",
            resource="vault:rebalance",
            details={
                "from_tier": from_tier.value,
                "to_tier": to_tier.value,
                "amount_usd": amount_usd,
            },
        )
        return result


_custody_adapter: CustodyAdapter | None = None


def get_custody_adapter(provider: str = "fireblocks") -> CustodyAdapter:
    """Factory: return custody adapter based on configured provider."""
    global _custody_adapter
    if _custody_adapter is None:
        if provider == "coinbase":
            _custody_adapter = StubCoinbaseCustodyAdapter()
        else:
            _custody_adapter = StubFireblocksCustodyAdapter()
    return _custody_adapter
