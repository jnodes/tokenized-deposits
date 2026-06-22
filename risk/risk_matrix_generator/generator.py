"""
Risk Matrix Generator - automated risk register and scoring.
Generates comprehensive risk assessments for the Issuing Bank Cari deposit program (CDA/DDA).

Implements:
- NIST CSF and FFIEC risk categories
- Likelihood x Impact scoring (5x5 matrix)
- Inherent vs. residual risk calculation
- Control mapping and mitigation tracking
- CSV/JSON export for examiner consumption

the Issuing Bank | Cari Network | ZKsync Prividium.
"""

from __future__ import annotations

import csv
import io
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from offchain.services import audit

logger = logging.getLogger("cari.risk.matrix")


class RiskCategory(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    TECHNOLOGY = "TECHNOLOGY"
    COMPLIANCE = "COMPLIANCE"
    CYBERSECURITY = "CYBERSECURITY"
    THIRD_PARTY = "THIRD_PARTY"
    STRATEGIC = "STRATEGIC"
    LIQUIDITY = "LIQUIDITY"
    REPUTATIONAL = "REPUTATIONAL"


class Likelihood(int, Enum):
    RARE = 1
    UNLIKELY = 2
    POSSIBLE = 3
    LIKELY = 4
    ALMOST_CERTAIN = 5


class Impact(int, Enum):
    NEGLIGIBLE = 1
    MINOR = 2
    MODERATE = 3
    MAJOR = 4
    CATASTROPHIC = 5


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class RiskEntry(BaseModel):
    """A single risk in the risk register."""
    risk_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    category: RiskCategory
    owner: str = ""
    regulatory_reference: str = ""  # e.g., "GENIUS Act S4", "NYDFS 500.07"

    # Inherent risk (before controls)
    inherent_likelihood: Likelihood
    inherent_impact: Impact
    inherent_score: int = 0
    inherent_level: RiskLevel = RiskLevel.LOW

    # Controls
    controls: list[str] = Field(default_factory=list)
    control_effectiveness_pct: float = 0.0

    # Residual risk (after controls)
    residual_likelihood: Likelihood = Likelihood.RARE
    residual_impact: Impact = Impact.NEGLIGIBLE
    residual_score: int = 0
    residual_level: RiskLevel = RiskLevel.LOW

    # Tracking
    status: str = "OPEN"  # "OPEN" | "MITIGATED" | "ACCEPTED" | "TRANSFERRED"
    mitigation_plan: str = ""
    last_reviewed: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


def _score_to_level(score: int) -> RiskLevel:
    if score >= 20:
        return RiskLevel.CRITICAL
    elif score >= 12:
        return RiskLevel.HIGH
    elif score >= 6:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


class RiskMatrixGenerator:
    """Generates and maintains the enterprise risk register."""

    def __init__(self) -> None:
        self._risks: list[RiskEntry] = []
        self._initialize_baseline_risks()

    def _initialize_baseline_risks(self) -> None:
        """Pre-populate with the Issuing Bank Cari deposit (CDA/DDA) baseline risks."""
        baseline = [
            RiskEntry(
                title="Private Key Compromise",
                description="Unauthorized access to HSM-managed signing keys could enable fraudulent minting/burning",
                category=RiskCategory.CYBERSECURITY,
                owner="CISO",
                regulatory_reference="NYDFS 500.15, OCC 2023-12",
                inherent_likelihood=Likelihood.UNLIKELY,
                inherent_impact=Impact.CATASTROPHIC,
                controls=["HSM FIPS 140-2 Level 3", "Dual control for key rotation", "Segregation of duties", "24/7 key usage monitoring"],
                control_effectiveness_pct=95.0,
                residual_likelihood=Likelihood.RARE,
                residual_impact=Impact.MAJOR,
                mitigation_plan="Quarterly key rotation, annual HSM audit, real-time anomaly detection",
            ),
            RiskEntry(
                title="Reserve Backing Violation",
                description="Token supply exceeds reserve assets, violating GENIUS Act Section 4 1:1 backing requirement",
                category=RiskCategory.COMPLIANCE,
                owner="TREASURER",
                regulatory_reference="GENIUS Act S4",
                inherent_likelihood=Likelihood.POSSIBLE,
                inherent_impact=Impact.CATASTROPHIC,
                controls=["On-chain ReserveOracle pre-mint check", "Real-time reserve monitoring", "Automated pause on breach", "Monthly attestation"],
                control_effectiveness_pct=98.0,
                residual_likelihood=Likelihood.RARE,
                residual_impact=Impact.MAJOR,
                mitigation_plan="Multi-layer reserve checks (on-chain + off-chain), daily reconciliation",
            ),
            RiskEntry(
                title="OFAC Sanctions Violation",
                description="Processing transactions with sanctioned entities without proper screening",
                category=RiskCategory.COMPLIANCE,
                owner="BSA_OFFICER",
                regulatory_reference="31 CFR Part 501, OFAC SDN",
                inherent_likelihood=Likelihood.POSSIBLE,
                inherent_impact=Impact.CATASTROPHIC,
                controls=["Real-time Chainalysis KYT screening", "Batch re-screening daily", "On-chain whitelist enforcement", "Automated freeze capability"],
                control_effectiveness_pct=97.0,
                residual_likelihood=Likelihood.RARE,
                residual_impact=Impact.MAJOR,
                mitigation_plan="Dual-provider screening (Chainalysis + TRM Labs), quarterly OFAC training",
            ),
            RiskEntry(
                title="Travel Rule Non-Compliance",
                description="Failure to collect/transmit originator/beneficiary data for transfers >= $3,000",
                category=RiskCategory.COMPLIANCE,
                owner="BSA_OFFICER",
                regulatory_reference="31 CFR 1010.410, FinCEN Travel Rule",
                inherent_likelihood=Likelihood.LIKELY,
                inherent_impact=Impact.MAJOR,
                controls=["Automated threshold detection", "Notabene VASP integration", "On-chain hash storage", "API validation"],
                control_effectiveness_pct=90.0,
                residual_likelihood=Likelihood.UNLIKELY,
                residual_impact=Impact.MODERATE,
                mitigation_plan="API enforcement of Travel Rule data before transaction submission",
            ),
            RiskEntry(
                title="Smart Contract Vulnerability",
                description="Exploitable bug in TokenizedDeposit, ReserveOracle, or CariSettlement contracts",
                category=RiskCategory.TECHNOLOGY,
                owner="CTO",
                regulatory_reference="OCC 2021-18, NYDFS 500.08",
                inherent_likelihood=Likelihood.POSSIBLE,
                inherent_impact=Impact.CATASTROPHIC,
                controls=["Formal verification", "Multiple audit firms", "Invariant testing (256 runs)", "UUPS upgrade capability", "Pause mechanism"],
                control_effectiveness_pct=92.0,
                residual_likelihood=Likelihood.UNLIKELY,
                residual_impact=Impact.MAJOR,
                mitigation_plan="Quarterly audit, bug bounty program, invariant test suite with 1024 fuzz runs",
            ),
            RiskEntry(
                title="Third-Party Custody Failure",
                description="Fireblocks/Coinbase custody provider experiences outage or breach",
                category=RiskCategory.THIRD_PARTY,
                owner="VENDOR_MANAGEMENT",
                regulatory_reference="NYDFS 500.11, OCC Third-Party Risk",
                inherent_likelihood=Likelihood.UNLIKELY,
                inherent_impact=Impact.MAJOR,
                controls=["Dual custody provider setup", "Hot/warm/cold tiering", "Insurance coverage", "SLA monitoring"],
                control_effectiveness_pct=85.0,
                residual_likelihood=Likelihood.RARE,
                residual_impact=Impact.MODERATE,
                mitigation_plan="Multi-provider strategy, quarterly vendor assessment, DR testing",
            ),
            RiskEntry(
                title="Core Banking Integration Failure",
                description="FIS/Symcor API outage prevents deposit verification or GL posting",
                category=RiskCategory.OPERATIONAL,
                owner="OPS_MANAGER",
                regulatory_reference="NYDFS 500.16",
                inherent_likelihood=Likelihood.POSSIBLE,
                inherent_impact=Impact.MODERATE,
                controls=["Circuit breaker pattern", "Queue-based retry", "Manual override procedure", "DR failover"],
                control_effectiveness_pct=88.0,
                residual_likelihood=Likelihood.UNLIKELY,
                residual_impact=Impact.MINOR,
                mitigation_plan="Async queue architecture, 15-minute RTO, quarterly failover drills",
            ),
            RiskEntry(
                title="Regulatory Change Risk",
                description="Changes to GENIUS Act, stablecoin regulation, or banking guidance invalidate platform design",
                category=RiskCategory.STRATEGIC,
                owner="CHIEF_REGULATORY_OFFICER",
                regulatory_reference="GENIUS Act (pending)",
                inherent_likelihood=Likelihood.LIKELY,
                inherent_impact=Impact.MODERATE,
                controls=["Regulatory monitoring", "Modular architecture", "StableArch Council advisory", "Quarterly compliance review"],
                control_effectiveness_pct=75.0,
                residual_likelihood=Likelihood.POSSIBLE,
                residual_impact=Impact.MINOR,
                mitigation_plan="Maintain flexibility via upgradeable contracts and modular off-chain stack",
            ),
        ]

        for risk in baseline:
            risk.inherent_score = risk.inherent_likelihood.value * risk.inherent_impact.value
            risk.inherent_level = _score_to_level(risk.inherent_score)
            risk.residual_score = risk.residual_likelihood.value * risk.residual_impact.value
            risk.residual_level = _score_to_level(risk.residual_score)
            risk.last_reviewed = datetime.now(timezone.utc)
            risk.status = "MITIGATED"

        self._risks = baseline

    async def add_risk(self, risk: RiskEntry) -> RiskEntry:
        risk.inherent_score = risk.inherent_likelihood.value * risk.inherent_impact.value
        risk.inherent_level = _score_to_level(risk.inherent_score)
        risk.residual_score = risk.residual_likelihood.value * risk.residual_impact.value
        risk.residual_level = _score_to_level(risk.residual_score)
        self._risks.append(risk)

        await audit.record(
            actor="RISK_MATRIX",
            action="add_risk",
            resource=f"risk:{risk.risk_id}",
            details={
                "title": risk.title,
                "inherent_level": risk.inherent_level.value,
                "residual_level": risk.residual_level.value,
            },
        )
        return risk

    def get_all_risks(self) -> list[RiskEntry]:
        return list(self._risks)

    def get_risks_by_category(self, category: RiskCategory) -> list[RiskEntry]:
        return [r for r in self._risks if r.category == category]

    def get_risks_by_level(self, level: RiskLevel) -> list[RiskEntry]:
        return [r for r in self._risks if r.residual_level == level]

    def get_risk_summary(self) -> dict:
        """Generate aggregate risk summary."""
        return {
            "total_risks": len(self._risks),
            "by_residual_level": {
                level.value: len(self.get_risks_by_level(level))
                for level in RiskLevel
            },
            "by_category": {
                cat.value: len(self.get_risks_by_category(cat))
                for cat in RiskCategory
            },
            "avg_control_effectiveness": (
                sum(r.control_effectiveness_pct for r in self._risks) / len(self._risks)
                if self._risks else 0
            ),
        }

    async def export_csv(self) -> str:
        """Export risk register as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Risk ID", "Title", "Category", "Owner", "Regulatory Ref",
            "Inherent Likelihood", "Inherent Impact", "Inherent Score", "Inherent Level",
            "Controls", "Control Effectiveness %",
            "Residual Likelihood", "Residual Impact", "Residual Score", "Residual Level",
            "Status", "Mitigation Plan",
        ])
        for r in self._risks:
            writer.writerow([
                r.risk_id[:12], r.title, r.category.value, r.owner, r.regulatory_reference,
                r.inherent_likelihood.name, r.inherent_impact.name, r.inherent_score, r.inherent_level.value,
                "; ".join(r.controls), r.control_effectiveness_pct,
                r.residual_likelihood.name, r.residual_impact.name, r.residual_score, r.residual_level.value,
                r.status, r.mitigation_plan,
            ])

        await audit.record(
            actor="RISK_MATRIX",
            action="export_csv",
            resource="risk_register",
            details={"total_risks": len(self._risks)},
        )
        return output.getvalue()


_generator: RiskMatrixGenerator | None = None


def get_risk_matrix() -> RiskMatrixGenerator:
    global _generator
    if _generator is None:
        _generator = RiskMatrixGenerator()
    return _generator
