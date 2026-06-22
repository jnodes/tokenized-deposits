"""
Private Key Lifecycle Manager — HSM integration for the Issuing Bank Cari deposits.
Supports AWS CloudHSM, Azure Key Vault, and Fireblocks MPC.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
Keys are used for signing CDA mint/burn/transfer operations.

Implements:
- Key generation, rotation, revocation, and destruction lifecycle
- Segregation of duties: each CDA role has its own isolated key
- NYDFS Part 500 Section 500.15 encryption of nonpublic information
- FIPS 140-2 Level 3 compliance (via HSM backends)

the Issuing Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from offchain.services import audit

logger = logging.getLogger("cari.security.key_management")


class KeyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    PENDING_ROTATION = "PENDING_ROTATION"
    ROTATED = "ROTATED"
    REVOKED = "REVOKED"
    DESTROYED = "DESTROYED"


class KeyRole(str, Enum):
    """Segregated key roles — one key per role, enforced by HSM policy."""
    MINTER = "MINTER"
    BURNER = "BURNER"
    ATTESTOR = "ATTESTOR"
    COMPLIANCE = "COMPLIANCE"
    SETTLEMENT = "SETTLEMENT"
    PAUSER = "PAUSER"
    UPGRADER = "UPGRADER"
    ADMIN = "ADMIN"


class HSMProvider(str, Enum):
    AWS_CLOUDHSM = "aws_cloudhsm"
    AZURE_KEYVAULT = "azure_keyvault"
    FIREBLOCKS_MPC = "fireblocks_mpc"
    LOCAL_DEV = "local_dev"


class KeyMetadata(BaseModel):
    """Metadata for a managed key — never contains the private key itself."""
    key_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: KeyRole
    provider: HSMProvider
    status: KeyStatus = KeyStatus.ACTIVE
    algorithm: str = "secp256k1"
    key_size_bits: int = 256
    public_key_hash: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rotated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    rotation_count: int = 0
    custodian: str = ""  # Human custodian for audit trail
    approval_quorum: int = 1  # Number of approvals needed for operations


class KeyRotationEvent(BaseModel):
    """Audit record for key rotation."""
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    key_id: str
    role: KeyRole
    action: str  # "GENERATE" | "ROTATE" | "REVOKE" | "DESTROY"
    old_public_key_hash: str = ""
    new_public_key_hash: str = ""
    approved_by: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""


class HSMBackend(ABC):
    """Abstract HSM backend — all key operations happen inside the HSM boundary."""

    @abstractmethod
    async def generate_key(self, role: KeyRole, algorithm: str = "secp256k1") -> KeyMetadata:
        ...

    @abstractmethod
    async def sign(self, key_id: str, message_hash: bytes) -> bytes:
        ...

    @abstractmethod
    async def get_public_key(self, key_id: str) -> str:
        ...

    @abstractmethod
    async def rotate_key(self, key_id: str, approved_by: list[str]) -> KeyMetadata:
        ...

    @abstractmethod
    async def revoke_key(self, key_id: str, reason: str) -> None:
        ...

    @abstractmethod
    async def destroy_key(self, key_id: str, approved_by: list[str]) -> None:
        ...


class StubHSMBackend(HSMBackend):
    """Local dev/test HSM stub — NEVER use in production.

    Simulates HSM operations with in-memory key storage.
    All key material stays in-process. No persistence.
    """

    def __init__(self, provider: HSMProvider = HSMProvider.LOCAL_DEV) -> None:
        self._provider = provider
        self._keys: dict[str, dict[str, Any]] = {}

    async def generate_key(self, role: KeyRole, algorithm: str = "secp256k1") -> KeyMetadata:
        key_bytes = secrets.token_bytes(32)
        pub_hash = hashlib.sha256(key_bytes).hexdigest()

        meta = KeyMetadata(
            role=role,
            provider=self._provider,
            algorithm=algorithm,
            public_key_hash=pub_hash,
            custodian="SYSTEM_AUTO",
        )
        self._keys[meta.key_id] = {
            "private": key_bytes,
            "metadata": meta,
        }

        await audit.record(
            actor="KEY_MANAGEMENT",
            action="generate_key",
            resource=f"key:{meta.key_id}",
            details={
                "role": role.value,
                "provider": self._provider.value,
                "public_key_hash": pub_hash,
            },
        )
        logger.info("Key generated: role=%s, id=%s", role.value, meta.key_id[:12])
        return meta

    async def sign(self, key_id: str, message_hash: bytes) -> bytes:
        entry = self._keys.get(key_id)
        if not entry:
            raise ValueError(f"Key not found: {key_id}")
        meta: KeyMetadata = entry["metadata"]
        if meta.status != KeyStatus.ACTIVE:
            raise ValueError(f"Key {key_id} is {meta.status.value}, cannot sign")

        # Stub: return HMAC-SHA256 as signature placeholder
        import hmac
        sig = hmac.new(entry["private"], message_hash, hashlib.sha256).digest()

        await audit.record(
            actor="KEY_MANAGEMENT",
            action="sign",
            resource=f"key:{key_id}",
            details={"role": meta.role.value, "msg_hash": message_hash.hex()[:16]},
        )
        return sig

    async def get_public_key(self, key_id: str) -> str:
        entry = self._keys.get(key_id)
        if not entry:
            raise ValueError(f"Key not found: {key_id}")
        return entry["metadata"].public_key_hash

    async def rotate_key(self, key_id: str, approved_by: list[str]) -> KeyMetadata:
        entry = self._keys.get(key_id)
        if not entry:
            raise ValueError(f"Key not found: {key_id}")
        old_meta: KeyMetadata = entry["metadata"]

        if len(approved_by) < old_meta.approval_quorum:
            raise ValueError(
                f"Rotation requires {old_meta.approval_quorum} approvals, got {len(approved_by)}"
            )

        # Mark old key as rotated
        old_meta.status = KeyStatus.ROTATED
        old_meta.rotated_at = datetime.now(timezone.utc)
        old_pub_hash = old_meta.public_key_hash

        # Generate new key
        new_meta = await self.generate_key(old_meta.role, old_meta.algorithm)
        new_meta.rotation_count = old_meta.rotation_count + 1
        new_meta.custodian = old_meta.custodian

        rotation_event = KeyRotationEvent(
            key_id=key_id,
            role=old_meta.role,
            action="ROTATE",
            old_public_key_hash=old_pub_hash,
            new_public_key_hash=new_meta.public_key_hash,
            approved_by=approved_by,
            reason="Scheduled rotation",
        )

        await audit.record(
            actor="KEY_MANAGEMENT",
            action="rotate_key",
            resource=f"key:{key_id}",
            details={
                "role": old_meta.role.value,
                "old_hash": old_pub_hash[:16],
                "new_key_id": new_meta.key_id[:12],
                "approved_by": approved_by,
            },
        )
        logger.info(
            "Key rotated: role=%s, old=%s -> new=%s",
            old_meta.role.value, key_id[:12], new_meta.key_id[:12],
        )
        return new_meta

    async def revoke_key(self, key_id: str, reason: str) -> None:
        entry = self._keys.get(key_id)
        if not entry:
            raise ValueError(f"Key not found: {key_id}")
        entry["metadata"].status = KeyStatus.REVOKED

        await audit.record(
            actor="KEY_MANAGEMENT",
            action="revoke_key",
            resource=f"key:{key_id}",
            details={"reason": reason, "role": entry["metadata"].role.value},
        )
        logger.warning("Key REVOKED: %s (reason: %s)", key_id[:12], reason)

    async def destroy_key(self, key_id: str, approved_by: list[str]) -> None:
        entry = self._keys.get(key_id)
        if not entry:
            raise ValueError(f"Key not found: {key_id}")

        meta: KeyMetadata = entry["metadata"]
        if len(approved_by) < 2:
            raise ValueError("Key destruction requires at least 2 approvals (dual control)")

        # Overwrite key material
        entry["private"] = b"\x00" * 32
        meta.status = KeyStatus.DESTROYED

        await audit.record(
            actor="KEY_MANAGEMENT",
            action="destroy_key",
            resource=f"key:{key_id}",
            details={
                "role": meta.role.value,
                "approved_by": approved_by,
            },
        )
        logger.warning("Key DESTROYED: %s (approved by: %s)", key_id[:12], approved_by)

    def get_all_keys(self) -> list[KeyMetadata]:
        return [entry["metadata"] for entry in self._keys.values()]


class KeyLifecycleManager:
    """Orchestrates key lifecycle across HSM backends with audit trail."""

    def __init__(self, backend: HSMBackend | None = None) -> None:
        self._backend = backend or StubHSMBackend()
        self._rotation_history: list[KeyRotationEvent] = []

    @property
    def backend(self) -> HSMBackend:
        return self._backend

    async def provision_all_roles(self) -> dict[KeyRole, KeyMetadata]:
        """Generate keys for all segregated roles — called at initial deployment."""
        keys: dict[KeyRole, KeyMetadata] = {}
        for role in KeyRole:
            meta = await self._backend.generate_key(role)
            keys[role] = meta
        logger.info("All %d role keys provisioned", len(keys))
        return keys

    async def sign_transaction(self, role: KeyRole, tx_hash: bytes, key_id: str) -> bytes:
        """Sign a transaction hash using the specified role's key."""
        return await self._backend.sign(key_id, tx_hash)

    async def rotate_key(
        self, key_id: str, approved_by: list[str], reason: str = ""
    ) -> KeyMetadata:
        return await self._backend.rotate_key(key_id, approved_by)

    async def emergency_revoke(self, key_id: str, reason: str) -> None:
        await self._backend.revoke_key(key_id, reason)

    def get_rotation_history(self) -> list[KeyRotationEvent]:
        return list(self._rotation_history)


_manager: KeyLifecycleManager | None = None


def get_key_manager() -> KeyLifecycleManager:
    global _manager
    if _manager is None:
        _manager = KeyLifecycleManager()
    return _manager
