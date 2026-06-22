"""
Regulatory Guardrail Checks
=============================
Automated compliance checks that flag non-GENIUS-Act or non-Cari-compliant designs
before they reach the final ARB package.

Context: the Issuing Bank Cari deposit platform on the Cari Network / ZKsync Prividium.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
DDA <-> CDA flow: fiat in DDA triggers CDA mint; CDA burn triggers fiat back to DDA.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class GuardrailResult:
    """Result of a single guardrail check."""
    rule_id: str
    rule_name: str
    passed: bool
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
    details: str
    remediation: str = ""


@dataclass
class GuardrailReport:
    """Aggregated report of all guardrail checks."""
    results: list[GuardrailResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.results)

    @property
    def critical_failures(self) -> list[GuardrailResult]:
        return [r for r in self.results if not r.passed and r.severity == "CRITICAL"]

    @property
    def high_failures(self) -> list[GuardrailResult]:
        return [r for r in self.results if not r.passed and r.severity == "HIGH"]

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        lines = [
            "=" * 70,
            "STABLEARCH COUNCIL - REGULATORY GUARDRAIL REPORT",
            "the Issuing Bank | Cari Network | ZKsync Prividium",
            "=" * 70,
            f"Total checks: {total}  |  Passed: {passed}  |  Failed: {failed}",
            f"Overall status: {'PASS' if self.passed else 'FAIL'}",
            "-" * 70,
        ]
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            lines.append(f"[{status}] [{r.severity}] {r.rule_id}: {r.rule_name}")
            if not r.passed:
                lines.append(f"       Details: {r.details}")
                if r.remediation:
                    lines.append(f"       Remediation: {r.remediation}")
        lines.append("=" * 70)
        return "\n".join(lines)


def _text_contains(text: str, keywords: list[str]) -> bool:
    """Case-insensitive check for presence of all keywords."""
    text_lower = text.lower()
    return all(kw.lower() in text_lower for kw in keywords)


def _text_contains_any(text: str, keywords: list[str]) -> bool:
    """Case-insensitive check for presence of any keyword."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def check_genius_act_reserve_backing(document: str) -> GuardrailResult:
    """GENIUS Act Section 4: 1:1 reserve backing requirement for CDA tokens."""
    has_reserve = _text_contains_any(document, [
        "1:1 reserve", "one-to-one reserve", "reserve backing",
        "qualifying reserves", "reserve requirement",
    ])
    has_assets = _text_contains_any(document, [
        "cash", "treasuries", "t-bills", "treasury bills",
        "fed deposit", "federal reserve deposit",
    ])
    passed = has_reserve and has_assets
    return GuardrailResult(
        rule_id="GENIUS-S4",
        rule_name="1:1 Reserve Backing (GENIUS Act Section 4)",
        passed=passed,
        severity="CRITICAL",
        details=(
            "Design must specify 1:1 reserve backing with qualifying assets "
            "(cash, short-term Treasuries, Fed deposits). No rehypothecation."
        ),
        remediation=(
            "Add explicit 1:1 reserve backing architecture with qualifying asset types "
            "and reserve attestation mechanism for the Issuing Bank's Cari deposits (CDAs)."
        ),
    )


def check_genius_act_redemption(document: str) -> GuardrailResult:
    """GENIUS Act Section 5: Redemption at par for CDA holders."""
    passed = _text_contains_any(document, [
        "redemption at par", "redeem at par", "par redemption",
        "burn-on-redemption", "burn on redemption",
    ])
    return GuardrailResult(
        rule_id="GENIUS-S5",
        rule_name="Redemption at Par (GENIUS Act Section 5)",
        passed=passed,
        severity="CRITICAL",
        details="CDA holders must be able to redeem at par value within 1 business day (CDA burn -> DDA settlement).",
        remediation=(
            "Add explicit redemption-at-par mechanism with T+0/T+1 CDA burn -> DDA settlement to "
            "depositor's the Issuing Bank account."
        ),
    )


def check_genius_act_attestation(document: str) -> GuardrailResult:
    """GENIUS Act Section 6: Monthly reserve attestation."""
    passed = _text_contains_any(document, [
        "reserve attestation", "monthly attestation", "accounting firm",
        "reserve audit", "proof of reserves", "reserve proof",
    ])
    return GuardrailResult(
        rule_id="GENIUS-S6",
        rule_name="Monthly Reserve Attestation (GENIUS Act Section 6)",
        passed=passed,
        severity="CRITICAL",
        details="Monthly reserve attestation by registered public accounting firm required.",
        remediation=(
            "Add reserve attestation service with monthly cadence and registered "
            "public accounting firm engagement."
        ),
    )


def check_genius_act_disclosure(document: str) -> GuardrailResult:
    """GENIUS Act Section 7: Disclosure obligations."""
    passed = _text_contains_any(document, [
        "disclosure", "reserve composition disclosure",
        "redemption policy disclosure", "risk factor disclosure",
    ])
    return GuardrailResult(
        rule_id="GENIUS-S7",
        rule_name="Disclosure Obligations (GENIUS Act Section 7)",
        passed=passed,
        severity="HIGH",
        details="Disclosure of reserve composition, redemption policies, and risk factors.",
        remediation="Add disclosure module for reserve composition and redemption policies.",
    )


def check_ofac_screening(document: str) -> GuardrailResult:
    """OFAC sanctions screening integration."""
    passed = _text_contains_any(document, [
        "ofac", "sanctions screening", "sdn list",
        "sanctions", "chainalysis", "elliptic", "trm labs",
    ])
    return GuardrailResult(
        rule_id="OFAC-01",
        rule_name="OFAC Sanctions Screening",
        passed=passed,
        severity="CRITICAL",
        details="Real-time OFAC sanctions screening for all wallet addresses and counterparties.",
        remediation=(
            "Integrate OFAC SDN list screening at wallet provisioning and on every "
            "transfer/mint/burn operation."
        ),
    )


def check_travel_rule(document: str) -> GuardrailResult:
    """FinCEN Travel Rule compliance."""
    passed = _text_contains_any(document, [
        "travel rule", "fincen travel", "originator/beneficiary",
        "notabene", "travel rule protocol",
    ])
    return GuardrailResult(
        rule_id="FINCEN-TR",
        rule_name="FinCEN Travel Rule",
        passed=passed,
        severity="CRITICAL",
        details="Travel Rule compliance for transfers >= $3,000 (originator/beneficiary info).",
        remediation=(
            "Add Travel Rule protocol integration (e.g., Notabene) for qualifying transfers."
        ),
    )


def check_bsa_aml(document: str) -> GuardrailResult:
    """BSA/AML transaction monitoring."""
    passed = _text_contains_any(document, [
        "bsa", "aml", "anti-money laundering", "transaction monitoring",
        "suspicious activity", "sar", "ctr", "kyc",
    ])
    return GuardrailResult(
        rule_id="BSA-AML",
        rule_name="BSA/AML Compliance",
        passed=passed,
        severity="CRITICAL",
        details="BSA/AML transaction monitoring, SAR filing, CTR reporting.",
        remediation="Add AML transaction monitoring system with SAR/CTR reporting capabilities.",
    )


def check_nydfs_part500(document: str) -> GuardrailResult:
    """NYDFS Part 500 cybersecurity compliance."""
    passed = _text_contains_any(document, [
        "nydfs", "part 500", "cybersecurity program", "ciso",
        "penetration testing", "pen testing", "incident response",
    ])
    return GuardrailResult(
        rule_id="NYDFS-500",
        rule_name="NYDFS Part 500 Cybersecurity",
        passed=passed,
        severity="HIGH",
        details="NYDFS Part 500 cybersecurity program, CISO, pen testing, incident response.",
        remediation="Add NYDFS Part 500 compliance section covering cybersecurity program requirements.",
    )


def check_cari_interoperability(document: str) -> GuardrailResult:
    """Cari Network interoperability standards for CDA transfers."""
    passed = _text_contains_any(document, [
        "cari interop", "cari network interop", "cross-bank transfer",
        "interbank", "cari member", "cari consortium",
    ]) or (
        _text_contains(document, ["cari"]) and
        _text_contains_any(document, ["interoperab", "cross-bank", "member bank"])
    )
    return GuardrailResult(
        rule_id="CARI-INT",
        rule_name="Cari Network Interoperability",
        passed=passed,
        severity="CRITICAL",
        details="Design must support Cari Network interoperability standards for cross-bank CDA operations.",
        remediation=(
            "Add Cari Network interoperability layer: cross-bank CDA transfers, "
            "shared KYC registry, settlement finality protocol."
        ),
    )


def check_smart_contract_audit(document: str) -> GuardrailResult:
    """Smart contract audit requirements."""
    passed = _text_contains_any(document, [
        "smart contract audit", "security audit", "formal verification",
        "openzeppelin", "trail of bits", "certora", "halborn",
        "independent audit", "bug bounty",
    ])
    return GuardrailResult(
        rule_id="SEC-AUDIT",
        rule_name="Smart Contract Security Audit",
        passed=passed,
        severity="HIGH",
        details="Minimum 2 independent smart contract audits required before mainnet deployment.",
        remediation="Add smart contract audit plan with at least 2 independent audit firms.",
    )


def check_examiner_transparency(document: str) -> GuardrailResult:
    """Regulatory examiner access and transparency."""
    passed = _text_contains_any(document, [
        "examiner", "regulatory access", "audit trail",
        "examiner transparency", "occ", "federal reserve",
        "supervisor", "regulatory reporting",
    ])
    return GuardrailResult(
        rule_id="REG-TRANS",
        rule_name="Examiner Transparency",
        passed=passed,
        severity="HIGH",
        details="Examiners (OCC, Fed, NYDFS) must have transparent access to data and reports.",
        remediation="Add examiner transparency package with data access protocols and reporting.",
    )


def check_mt_bank_references(document: str) -> GuardrailResult:
    """All outputs must reference the Issuing Bank, Cari Network, ZKsync Prividium."""
    has_mt = _text_contains_any(document, ["the Issuing Bank", "Issuing Bank", "issuing bank"])
    has_cari = _text_contains(document, ["cari"])
    has_prividium = _text_contains_any(document, ["prividium", "zksync"])
    passed = has_mt and has_cari and has_prividium
    missing = []
    if not has_mt:
        missing.append("the Issuing Bank")
    if not has_cari:
        missing.append("Cari Network")
    if not has_prividium:
        missing.append("ZKsync Prividium")
    return GuardrailResult(
        rule_id="CTX-REF",
        rule_name="the Issuing Bank / Cari / Prividium References",
        passed=passed,
        severity="HIGH",
        details=f"Missing references: {', '.join(missing)}" if missing else "All references present.",
        remediation="Ensure every output section references the Issuing Bank, Cari Network, and ZKsync Prividium.",
    )


def check_rulebook_compliance(document: str) -> GuardrailResult:
    """Cari Network Rulebook governance compliance."""
    passed = _text_contains_any(document, [
        "rulebook", "consortium governance", "member obligations",
        "member bank obligations", "protocol upgrade", "dispute resolution",
        "data sharing standards", "onboarding", "offboarding",
    ])
    return GuardrailResult(
        rule_id="CARI-RULE",
        rule_name="Cari Network Rulebook Compliance",
        passed=passed,
        severity="HIGH",
        details="Design must address Cari Network Rulebook governance: member obligations, protocol upgrades, dispute resolution.",
        remediation=(
            "Add Cari Rulebook compliance section covering member bank obligations, "
            "protocol upgrade voting, dispute resolution, and data sharing standards."
        ),
    )


ALL_CHECKS = [
    check_genius_act_reserve_backing,
    check_genius_act_redemption,
    check_genius_act_attestation,
    check_genius_act_disclosure,
    check_ofac_screening,
    check_travel_rule,
    check_bsa_aml,
    check_nydfs_part500,
    check_cari_interoperability,
    check_smart_contract_audit,
    check_examiner_transparency,
    check_mt_bank_references,
    check_rulebook_compliance,
]


def run_guardrail_checks(document: str) -> GuardrailReport:
    """Run all regulatory guardrail checks against a document.

    Args:
        document: The text content to check (e.g., ARB package output).

    Returns:
        GuardrailReport with pass/fail results for each check.
    """
    report = GuardrailReport()
    for check_fn in ALL_CHECKS:
        result = check_fn(document)
        report.results.append(result)
    return report


if __name__ == "__main__":
    # Quick self-test with a sample document
    sample = """\
    the Issuing Bank Cari deposit platform on the Cari Network using ZKsync Prividium.
    Cari Deposit Accounts (CDAs) are on-chain representations of DDAs.
    1:1 reserve backing with qualifying reserves (cash, T-bills, Fed deposits).
    Redemption at par within 1 business day via CDA burn -> DDA settlement.
    Monthly reserve attestation by registered public accounting firm.
    Disclosure of reserve composition and redemption policies.
    OFAC sanctions screening via Chainalysis integrated at wallet provisioning.
    FinCEN Travel Rule via Notabene for transfers >= $3,000.
    BSA/AML transaction monitoring with SAR/CTR reporting.
    NYDFS Part 500 cybersecurity program with designated CISO and annual pen testing.
    Cari Network interoperability for cross-bank CDA transfers between member banks.
    Smart contract security audit by OpenZeppelin and Trail of Bits.
    Examiner transparency package for OCC and Federal Reserve examiners.
    Cari Network Rulebook compliance with member bank obligations and dispute resolution.
    """
    report = run_guardrail_checks(sample)
    print(report.summary())
