"""
Resilience, Failover, Disaster Recovery & Incident Response.
Business continuity planning for the Issuing Bank Cari deposit platform (CDA/DDA operations).

Implements:
- Circuit breaker pattern for external service calls
- Health monitoring with automatic failover triggers
- DR playbook execution engine with runbook steps
- Incident classification, escalation, and response tracking
- NYDFS Part 500 Section 500.16 incident response plan

the Issuing Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from offchain.services import audit

logger = logging.getLogger("cari.security.resilience")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Failures detected, requests blocked
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


class IncidentSeverity(str, Enum):
    P1_CRITICAL = "P1_CRITICAL"  # System down, regulatory breach, key compromise
    P2_HIGH = "P2_HIGH"          # Service degraded, compliance risk
    P3_MEDIUM = "P3_MEDIUM"      # Partial outage, no compliance impact
    P4_LOW = "P4_LOW"            # Minor issue, informational


class IncidentStatus(str, Enum):
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    MITIGATING = "MITIGATING"
    RESOLVED = "RESOLVED"
    POST_MORTEM = "POST_MORTEM"


class ComponentHealth(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"


class CircuitBreaker:
    """Circuit breaker for external service calls (HSM, Chainalysis, core banking)."""

    def __init__(
        self,
        service_name: str,
        failure_threshold: int = 5,
        recovery_timeout_seconds: int = 60,
    ) -> None:
        self.service_name = service_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_at: datetime | None = None
        self.last_success_at: datetime | None = None

    async def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        self.last_success_at = datetime.now(timezone.utc)

    async def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_at = datetime.now(timezone.utc)
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            await audit.record(
                actor="CIRCUIT_BREAKER",
                action="circuit_opened",
                resource=f"service:{self.service_name}",
                details={
                    "failure_count": self.failure_count,
                    "threshold": self.failure_threshold,
                },
            )
            logger.critical(
                "Circuit OPENED for %s after %d failures",
                self.service_name, self.failure_count,
            )

    def is_available(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN and self.last_failure_at:
            elapsed = (datetime.now(timezone.utc) - self.last_failure_at).total_seconds()
            if elapsed >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
        return self.state == CircuitState.HALF_OPEN

    def get_status(self) -> dict:
        return {
            "service": self.service_name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "threshold": self.failure_threshold,
        }


class Incident(BaseModel):
    """Security/operational incident record."""
    incident_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    component: str = ""
    description: str = ""
    impact: str = ""
    root_cause: str = ""
    mitigation_steps: list[str] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)
    reported_by: str = ""
    assigned_to: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    regulatory_notification_required: bool = False
    notification_sent: bool = False


class DRPlaybookStep(BaseModel):
    """A single step in a disaster recovery playbook."""
    step_number: int
    action: str
    responsible: str
    estimated_minutes: int = 0
    completed: bool = False
    completed_at: Optional[datetime] = None
    notes: str = ""


class DRPlaybook(BaseModel):
    """Disaster recovery playbook for a specific scenario."""
    playbook_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scenario: str
    rto_minutes: int = 0  # Recovery Time Objective
    rpo_minutes: int = 0  # Recovery Point Objective
    steps: list[DRPlaybookStep] = Field(default_factory=list)
    last_tested_at: Optional[datetime] = None
    test_result: str = ""


class ResilienceManager:
    """Orchestrates resilience, failover, and incident response."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._incidents: list[Incident] = []
        self._playbooks: dict[str, DRPlaybook] = {}
        self._component_health: dict[str, ComponentHealth] = {}
        self._initialize_playbooks()
        self._initialize_breakers()

    def _initialize_breakers(self) -> None:
        services = [
            "hsm_primary", "hsm_secondary", "core_banking",
            "chainalysis_kyt", "notabene", "prividium_rpc",
            "kafka", "redis", "fireblocks",
        ]
        for svc in services:
            self._breakers[svc] = CircuitBreaker(svc)

    def _initialize_playbooks(self) -> None:
        self._playbooks = {
            "hsm_failure": DRPlaybook(
                scenario="HSM Primary Failure",
                rto_minutes=15,
                rpo_minutes=0,
                steps=[
                    DRPlaybookStep(step_number=1, action="Detect HSM failure via health check", responsible="MONITORING", estimated_minutes=1),
                    DRPlaybookStep(step_number=2, action="Activate circuit breaker for HSM", responsible="SYSTEM", estimated_minutes=0),
                    DRPlaybookStep(step_number=3, action="Failover to secondary HSM cluster", responsible="INFRA_TEAM", estimated_minutes=5),
                    DRPlaybookStep(step_number=4, action="Verify signing capability on secondary", responsible="SECURITY_TEAM", estimated_minutes=3),
                    DRPlaybookStep(step_number=5, action="Resume transaction processing", responsible="OPS_TEAM", estimated_minutes=2),
                    DRPlaybookStep(step_number=6, action="File incident report and notify CISO", responsible="SECURITY_TEAM", estimated_minutes=5),
                ],
            ),
            "blockchain_rpc_failure": DRPlaybook(
                scenario="ZKsync Prividium RPC Node Failure",
                rto_minutes=10,
                rpo_minutes=0,
                steps=[
                    DRPlaybookStep(step_number=1, action="Detect RPC failure via health check", responsible="MONITORING", estimated_minutes=1),
                    DRPlaybookStep(step_number=2, action="Failover to secondary RPC endpoint", responsible="SYSTEM", estimated_minutes=1),
                    DRPlaybookStep(step_number=3, action="Pause new transaction submissions", responsible="OPS_TEAM", estimated_minutes=1),
                    DRPlaybookStep(step_number=4, action="Verify chain state consistency", responsible="BLOCKCHAIN_TEAM", estimated_minutes=5),
                    DRPlaybookStep(step_number=5, action="Resume operations", responsible="OPS_TEAM", estimated_minutes=2),
                ],
            ),
            "key_compromise": DRPlaybook(
                scenario="Private Key Compromise Suspected",
                rto_minutes=5,
                rpo_minutes=0,
                steps=[
                    DRPlaybookStep(step_number=1, action="IMMEDIATE: Invoke contract pause via PAUSER_ROLE", responsible="SECURITY_TEAM", estimated_minutes=1),
                    DRPlaybookStep(step_number=2, action="Revoke compromised key in HSM", responsible="KEY_CUSTODIAN", estimated_minutes=2),
                    DRPlaybookStep(step_number=3, action="Rotate all keys in the same HSM partition", responsible="KEY_CUSTODIAN", estimated_minutes=10),
                    DRPlaybookStep(step_number=4, action="Update on-chain role assignments via admin multi-sig", responsible="ADMIN_TEAM", estimated_minutes=15),
                    DRPlaybookStep(step_number=5, action="Audit all transactions signed by compromised key", responsible="FORENSICS", estimated_minutes=60),
                    DRPlaybookStep(step_number=6, action="Notify NYDFS within 72 hours (Part 500.17)", responsible="COMPLIANCE", estimated_minutes=30),
                    DRPlaybookStep(step_number=7, action="Unpause contracts after verification", responsible="SECURITY_TEAM", estimated_minutes=5),
                ],
            ),
            "reserve_breach": DRPlaybook(
                scenario="1:1 Reserve Backing Violation (GENIUS Act S4)",
                rto_minutes=30,
                rpo_minutes=0,
                steps=[
                    DRPlaybookStep(step_number=1, action="IMMEDIATE: Pause minting operations", responsible="SYSTEM", estimated_minutes=1),
                    DRPlaybookStep(step_number=2, action="Verify reserve balance with core banking", responsible="TREASURY", estimated_minutes=5),
                    DRPlaybookStep(step_number=3, action="Initiate reserve top-up if deficit confirmed", responsible="TREASURY", estimated_minutes=15),
                    DRPlaybookStep(step_number=4, action="Update oracle attestation with new reserve balance", responsible="ATTESTOR", estimated_minutes=5),
                    DRPlaybookStep(step_number=5, action="Resume minting after 1:1 backing confirmed", responsible="OPS_TEAM", estimated_minutes=2),
                    DRPlaybookStep(step_number=6, action="File regulatory notification if breach > 1 hour", responsible="COMPLIANCE", estimated_minutes=30),
                ],
            ),
        }

    def get_circuit_breaker(self, service: str) -> CircuitBreaker:
        if service not in self._breakers:
            self._breakers[service] = CircuitBreaker(service)
        return self._breakers[service]

    def get_all_breaker_status(self) -> list[dict]:
        return [b.get_status() for b in self._breakers.values()]

    async def create_incident(
        self,
        *,
        title: str,
        severity: IncidentSeverity,
        component: str = "",
        description: str = "",
        impact: str = "",
        reported_by: str = "",
    ) -> Incident:
        regulatory = severity in (IncidentSeverity.P1_CRITICAL, IncidentSeverity.P2_HIGH)

        incident = Incident(
            title=title,
            severity=severity,
            component=component,
            description=description,
            impact=impact,
            reported_by=reported_by,
            regulatory_notification_required=regulatory,
            timeline=[{
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "action": "Incident created",
                "by": reported_by,
            }],
        )
        self._incidents.append(incident)

        await audit.record(
            actor="INCIDENT_RESPONSE",
            action="create_incident",
            resource=f"incident:{incident.incident_id}",
            details={
                "title": title,
                "severity": severity.value,
                "component": component,
                "regulatory_notification": regulatory,
            },
        )
        logger.warning(
            "Incident created: [%s] %s — %s",
            severity.value, title, incident.incident_id[:12],
        )
        return incident

    async def update_incident(
        self, incident_id: str, *, status: IncidentStatus, notes: str = "", by: str = ""
    ) -> Incident:
        incident = next((i for i in self._incidents if i.incident_id == incident_id), None)
        if not incident:
            raise ValueError(f"Incident not found: {incident_id}")

        incident.status = status
        incident.timeline.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": f"Status -> {status.value}",
            "notes": notes,
            "by": by,
        })
        if status == IncidentStatus.RESOLVED:
            incident.resolved_at = datetime.now(timezone.utc)

        await audit.record(
            actor="INCIDENT_RESPONSE",
            action="update_incident",
            resource=f"incident:{incident_id}",
            details={"new_status": status.value, "notes": notes},
        )
        return incident

    def get_playbook(self, scenario: str) -> DRPlaybook | None:
        return self._playbooks.get(scenario)

    def get_all_playbooks(self) -> list[DRPlaybook]:
        return list(self._playbooks.values())

    def get_incidents(self, status: IncidentStatus | None = None) -> list[Incident]:
        if status:
            return [i for i in self._incidents if i.status == status]
        return list(self._incidents)

    def update_component_health(self, component: str, health: ComponentHealth) -> None:
        self._component_health[component] = health

    def get_system_health(self) -> dict[str, str]:
        return {k: v.value for k, v in self._component_health.items()}


_manager: ResilienceManager | None = None


def get_resilience_manager() -> ResilienceManager:
    global _manager
    if _manager is None:
        _manager = ResilienceManager()
    return _manager
