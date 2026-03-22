"""
Immutable audit logging service for examiner transparency.
Every state-changing CDA/DDA operation is recorded with actor, action, resource, and details.
OCC / Fed / NYDFS examiners can query the full audit trail.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any

from offchain.models.schemas import AuditLogEntry

logger = logging.getLogger("cari.audit")

# In production this writes to an append-only database (e.g., Amazon QLDB,
# Azure Immutable Blob, or a Postgres table with row-level security).
# For dev/test we keep an in-memory log.
_audit_log: list[AuditLogEntry] = []


async def record(
    *,
    actor: str,
    action: str,
    resource: str,
    details: dict[str, Any] | None = None,
    correlation_id: str = "",
    ip_address: str = "",
) -> AuditLogEntry:
    """Append an immutable audit entry."""
    entry = AuditLogEntry(
        actor=actor,
        action=action,
        resource=resource,
        details=details or {},
        correlation_id=correlation_id,
        ip_address=ip_address,
    )
    _audit_log.append(entry)
    logger.info(
        "AUDIT | %s | %s | %s | %s | %s",
        entry.timestamp.isoformat(),
        actor,
        action,
        resource,
        json.dumps(details or {}),
    )
    return entry


async def query(
    *,
    actor: str | None = None,
    action: str | None = None,
    resource: str | None = None,
    since: datetime | None = None,
    limit: int = 100,
) -> list[AuditLogEntry]:
    """Query audit log entries (examiner access)."""
    results = _audit_log
    if actor:
        results = [e for e in results if e.actor == actor]
    if action:
        results = [e for e in results if e.action == action]
    if resource:
        results = [e for e in results if e.resource == resource]
    if since:
        results = [e for e in results if e.timestamp >= since]
    return results[-limit:]


def get_full_log() -> list[AuditLogEntry]:
    """Return the complete audit log (for testing / examiner export)."""
    return list(_audit_log)


def clear_log() -> None:
    """Clear the in-memory audit log (testing only)."""
    _audit_log.clear()
