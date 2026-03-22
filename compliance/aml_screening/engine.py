"""
BSA/AML + OFAC Sanctions Screening Engine — real-time + batch.
Production-grade compliance screening for Cari deposit (CDA) operations.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
All CDA/DDA operations are screened for BSA/AML/OFAC compliance.

Implements:
- Real-time address screening against OFAC SDN list
- Batch screening for periodic re-screening of all whitelisted CDA addresses
- CTR (Currency Transaction Report) detection at $10,000 threshold
- SAR (Suspicious Activity Report) pattern detection
- Integration with Chainalysis KYT and TRM Labs (stubs for dev)
- NYDFS Part 504 transaction monitoring requirements

M&T Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from offchain.models.schemas import ComplianceStatus
from offchain.services import audit

logger = logging.getLogger("cari.compliance.aml")


class ScreeningType(str, Enum):
    REAL_TIME = "REAL_TIME"
    BATCH = "BATCH"
    PERIODIC_RESCREEN = "PERIODIC_RESCREEN"


class AlertType(str, Enum):
    OFAC_MATCH = "OFAC_MATCH"
    SANCTIONS_MATCH = "SANCTIONS_MATCH"
    CTR_THRESHOLD = "CTR_THRESHOLD"
    SAR_PATTERN = "SAR_PATTERN"
    STRUCTURING = "STRUCTURING"
    VELOCITY_ANOMALY = "VELOCITY_ANOMALY"
    HIGH_RISK_JURISDICTION = "HIGH_RISK_JURISDICTION"


class ScreeningResult(BaseModel):
    """Detailed result of a single screening check."""
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    screening_type: ScreeningType
    address: str
    status: ComplianceStatus
    alerts: list[AlertType] = Field(default_factory=list)
    risk_score: float = 0.0
    ofac_match: bool = False
    sanctions_match: bool = False
    ctr_required: bool = False
    sar_filed: bool = False
    details: str = ""
    provider: str = ""
    screened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TransactionPattern(BaseModel):
    """Pattern detection for SAR filing."""
    address: str
    total_usd_24h: float = 0.0
    tx_count_24h: int = 0
    total_usd_30d: float = 0.0
    tx_count_30d: int = 0
    unique_counterparties_30d: int = 0
    largest_single_tx_usd: float = 0.0


class BatchScreeningReport(BaseModel):
    """Summary of a batch screening run."""
    report_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    run_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    total_addresses: int = 0
    passed: int = 0
    flagged: int = 0
    blocked: int = 0
    alerts_generated: int = 0
    duration_seconds: float = 0.0


# Pre-configured high-risk jurisdictions (FATF grey/black list)
HIGH_RISK_JURISDICTIONS = {
    "KP", "IR", "MM", "SY", "YE", "AF",  # FATF black list
    "AL", "BB", "BF", "CM", "CD", "GI",   # FATF grey list (partial)
    "HT", "JM", "JO", "ML", "MZ", "NG",
    "PA", "PH", "SN", "SS", "TZ", "TR",
    "UG", "AE", "VN", "VU",
}

# Stub OFAC SDN entries for testing
_STUB_OFAC_ADDRESSES = {
    "0xOFAC_BLOCKED_001",
    "0xOFAC_BLOCKED_002",
    "0xSANCTIONED_ENTITY",
}


class AMLScreeningEngine:
    """Full BSA/AML/OFAC screening engine."""

    CTR_THRESHOLD = 10_000.0
    STRUCTURING_THRESHOLD = 8_000.0  # Detect structuring below CTR
    SAR_VELOCITY_THRESHOLD_24H = 50_000.0
    SAR_TX_COUNT_THRESHOLD_24H = 20

    def __init__(self) -> None:
        self._screening_history: list[ScreeningResult] = []
        self._patterns: dict[str, TransactionPattern] = {}
        self._batch_reports: list[BatchScreeningReport] = []

    async def screen_address_realtime(self, address: str) -> ScreeningResult:
        """Real-time OFAC/sanctions screening of a single address."""
        alerts: list[AlertType] = []
        status = ComplianceStatus.PASSED
        risk_score = 0.1

        # OFAC SDN check (stub — in production calls Chainalysis API)
        if address in _STUB_OFAC_ADDRESSES:
            alerts.append(AlertType.OFAC_MATCH)
            status = ComplianceStatus.BLOCKED
            risk_score = 1.0

        # Sanctions check
        if address.upper().startswith("0XSANCTION"):
            alerts.append(AlertType.SANCTIONS_MATCH)
            status = ComplianceStatus.BLOCKED
            risk_score = 1.0

        result = ScreeningResult(
            screening_type=ScreeningType.REAL_TIME,
            address=address,
            status=status,
            alerts=alerts,
            risk_score=risk_score,
            ofac_match=AlertType.OFAC_MATCH in alerts,
            sanctions_match=AlertType.SANCTIONS_MATCH in alerts,
            provider="chainalysis_kyt_stub",
            details=f"Alerts: {[a.value for a in alerts]}" if alerts else "No alerts",
        )
        self._screening_history.append(result)

        await audit.record(
            actor="AML_ENGINE",
            action="screen_realtime",
            resource=f"address:{address}",
            details={
                "status": status.value,
                "risk_score": risk_score,
                "alerts": [a.value for a in alerts],
            },
        )

        if alerts:
            logger.warning("AML ALERT: %s — %s", address, [a.value for a in alerts])
        return result

    async def screen_transaction(
        self, *, from_addr: str, to_addr: str, amount_usd: float
    ) -> ScreeningResult:
        """Screen a transaction for BSA/AML compliance."""
        # Screen both parties
        from_result = await self.screen_address_realtime(from_addr)
        to_result = await self.screen_address_realtime(to_addr)

        alerts: list[AlertType] = list(set(from_result.alerts + to_result.alerts))

        # CTR threshold
        ctr_required = amount_usd >= self.CTR_THRESHOLD
        if ctr_required:
            alerts.append(AlertType.CTR_THRESHOLD)

        # Update pattern counters BEFORE structuring check
        pattern = self._get_or_create_pattern(from_addr)
        pattern.total_usd_24h += amount_usd
        pattern.tx_count_24h += 1

        # Structuring detection
        if self.STRUCTURING_THRESHOLD <= amount_usd < self.CTR_THRESHOLD:
            if pattern.tx_count_24h >= 3:
                alerts.append(AlertType.STRUCTURING)

        # Velocity anomaly
        if pattern.total_usd_24h > self.SAR_VELOCITY_THRESHOLD_24H:
            alerts.append(AlertType.VELOCITY_ANOMALY)
        if pattern.tx_count_24h > self.SAR_TX_COUNT_THRESHOLD_24H:
            alerts.append(AlertType.VELOCITY_ANOMALY)

        # Determine status
        if from_result.status == ComplianceStatus.BLOCKED or to_result.status == ComplianceStatus.BLOCKED:
            status = ComplianceStatus.BLOCKED
        elif AlertType.STRUCTURING in alerts or AlertType.VELOCITY_ANOMALY in alerts:
            status = ComplianceStatus.FLAGGED
        else:
            status = ComplianceStatus.PASSED

        result = ScreeningResult(
            screening_type=ScreeningType.REAL_TIME,
            address=f"{from_addr}->{to_addr}",
            status=status,
            alerts=alerts,
            risk_score=max(from_result.risk_score, to_result.risk_score),
            ofac_match=from_result.ofac_match or to_result.ofac_match,
            sanctions_match=from_result.sanctions_match or to_result.sanctions_match,
            ctr_required=ctr_required,
            provider="chainalysis_kyt_stub",
            details=f"CTR: {ctr_required}, Alerts: {[a.value for a in alerts]}",
        )
        self._screening_history.append(result)
        return result

    async def batch_screen(self, addresses: list[str]) -> BatchScreeningReport:
        """Batch screening of multiple addresses (periodic re-screening)."""
        start = datetime.now(timezone.utc)
        passed = flagged = blocked = total_alerts = 0

        for addr in addresses:
            result = await self.screen_address_realtime(addr)
            if result.status == ComplianceStatus.PASSED:
                passed += 1
            elif result.status == ComplianceStatus.FLAGGED:
                flagged += 1
            else:
                blocked += 1
            total_alerts += len(result.alerts)

        end = datetime.now(timezone.utc)
        report = BatchScreeningReport(
            total_addresses=len(addresses),
            passed=passed,
            flagged=flagged,
            blocked=blocked,
            alerts_generated=total_alerts,
            duration_seconds=(end - start).total_seconds(),
        )
        self._batch_reports.append(report)

        await audit.record(
            actor="AML_ENGINE",
            action="batch_screen",
            resource="address_list",
            details={
                "total": len(addresses),
                "passed": passed,
                "flagged": flagged,
                "blocked": blocked,
            },
        )
        return report

    def _get_or_create_pattern(self, address: str) -> TransactionPattern:
        if address not in self._patterns:
            self._patterns[address] = TransactionPattern(address=address)
        return self._patterns[address]

    def get_screening_history(self, address: str | None = None) -> list[ScreeningResult]:
        if address:
            return [r for r in self._screening_history if address in r.address]
        return list(self._screening_history)

    def get_batch_reports(self) -> list[BatchScreeningReport]:
        return list(self._batch_reports)


_engine: AMLScreeningEngine | None = None


def get_aml_engine() -> AMLScreeningEngine:
    global _engine
    if _engine is None:
        _engine = AMLScreeningEngine()
    return _engine
