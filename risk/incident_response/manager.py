"""
Incident Response Playbook Engine — automated incident management.
Manages incident lifecycle from detection through resolution and post-mortem.

Re-exports and extends the incident capabilities from security/resilience/dr_manager.py
with additional playbook execution tracking and regulatory notification management.

the Issuing Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from offchain.services import audit
from security.resilience.dr_manager import (
    DRPlaybook,
    Incident,
    IncidentSeverity,
    IncidentStatus,
    ResilienceManager,
    get_resilience_manager,
)

logger = logging.getLogger("cari.risk.incident_response")


class PlaybookExecution(BaseModel):
    """Record of a playbook execution during an incident."""
    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    playbook_scenario: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    steps_completed: int = 0
    steps_total: int = 0
    status: str = "IN_PROGRESS"  # "IN_PROGRESS" | "COMPLETED" | "ABORTED"
    notes: list[str] = Field(default_factory=list)


class RegulatoryNotification(BaseModel):
    """Track regulatory notifications for incidents (NYDFS 500.17)."""
    notification_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    incident_id: str
    regulator: str  # "NYDFS" | "OCC" | "Fed" | "FinCEN"
    deadline: datetime
    sent_at: Optional[datetime] = None
    content_summary: str = ""
    status: str = "PENDING"  # "PENDING" | "SENT" | "ACKNOWLEDGED"


class IncidentResponseManager:
    """Extended incident response with playbook execution and regulatory tracking."""

    def __init__(self) -> None:
        self._resilience = get_resilience_manager()
        self._executions: list[PlaybookExecution] = []
        self._notifications: list[RegulatoryNotification] = []

    async def create_and_respond(
        self,
        *,
        title: str,
        severity: IncidentSeverity,
        component: str = "",
        description: str = "",
        playbook_scenario: str | None = None,
        reported_by: str = "",
    ) -> tuple[Incident, PlaybookExecution | None]:
        """Create an incident and optionally start playbook execution."""
        incident = await self._resilience.create_incident(
            title=title,
            severity=severity,
            component=component,
            description=description,
            impact=f"Severity {severity.value} incident on {component}",
            reported_by=reported_by,
        )

        execution = None
        if playbook_scenario:
            playbook = self._resilience.get_playbook(playbook_scenario)
            if playbook:
                execution = PlaybookExecution(
                    incident_id=incident.incident_id,
                    playbook_scenario=playbook_scenario,
                    steps_total=len(playbook.steps),
                )
                self._executions.append(execution)

                await audit.record(
                    actor="INCIDENT_RESPONSE",
                    action="start_playbook",
                    resource=f"incident:{incident.incident_id}",
                    details={
                        "playbook": playbook_scenario,
                        "steps": len(playbook.steps),
                    },
                )

        # Auto-create regulatory notification for P1/P2
        if incident.regulatory_notification_required:
            from datetime import timedelta
            notification = RegulatoryNotification(
                incident_id=incident.incident_id,
                regulator="NYDFS",
                deadline=datetime.now(timezone.utc) + timedelta(hours=72),
                content_summary=f"[{severity.value}] {title}: {description}",
            )
            self._notifications.append(notification)
            logger.warning(
                "Regulatory notification required for incident %s — deadline: %s",
                incident.incident_id[:12],
                notification.deadline.isoformat(),
            )

        return incident, execution

    async def complete_playbook_step(
        self, execution_id: str, step_notes: str = ""
    ) -> PlaybookExecution:
        """Mark a playbook step as completed."""
        execution = next(
            (e for e in self._executions if e.execution_id == execution_id), None
        )
        if not execution:
            raise ValueError(f"Execution not found: {execution_id}")

        execution.steps_completed += 1
        if step_notes:
            execution.notes.append(step_notes)

        if execution.steps_completed >= execution.steps_total:
            execution.status = "COMPLETED"
            execution.completed_at = datetime.now(timezone.utc)

        return execution

    async def send_regulatory_notification(
        self, notification_id: str
    ) -> RegulatoryNotification:
        """Mark a regulatory notification as sent."""
        notification = next(
            (n for n in self._notifications if n.notification_id == notification_id),
            None,
        )
        if not notification:
            raise ValueError(f"Notification not found: {notification_id}")

        notification.status = "SENT"
        notification.sent_at = datetime.now(timezone.utc)

        await audit.record(
            actor="INCIDENT_RESPONSE",
            action="send_notification",
            resource=f"notification:{notification_id}",
            details={
                "regulator": notification.regulator,
                "incident_id": notification.incident_id,
            },
        )
        return notification

    def get_executions(self) -> list[PlaybookExecution]:
        return list(self._executions)

    def get_notifications(self, status: str | None = None) -> list[RegulatoryNotification]:
        if status:
            return [n for n in self._notifications if n.status == status]
        return list(self._notifications)

    def get_incidents(self) -> list[Incident]:
        return self._resilience.get_incidents()


_manager: IncidentResponseManager | None = None


def get_incident_manager() -> IncidentResponseManager:
    global _manager
    if _manager is None:
        _manager = IncidentResponseManager()
    return _manager
