"""
StableArch Council - Task Definitions
=======================================
Defines CrewAI tasks for the ARB package generation workflow.
Context: the Issuing Bank Cari deposit platform on the Cari Network / ZKsync Prividium.

Cari Deposit Account (CDA) = on-chain representation of a Demand Deposit Account (DDA).
DDA <-> CDA flow: fiat in DDA triggers CDA mint; CDA burn triggers fiat back to DDA.
"""

from crewai import Task, Agent


def create_platform_architecture_task(agent: Agent) -> Task:
    """Task: Design the Cari deposit platform architecture (CDA/DDA)."""
    return Task(
        description=(
            "Design the complete Cari deposit platform architecture for the Issuing Bank on the "
            "Cari Network / ZKsync Prividium.\n\n"
            "Cari Deposit Accounts (CDAs) are on-chain representations of Demand Deposit Accounts (DDAs).\n"
            "Core flow: DDA deposit triggers CDA mint; CDA burn triggers fiat back to DDA.\n\n"
            "Deliverables:\n"
            "1. Solution architecture document covering on-chain and off-chain components.\n"
            "2. Token specification: ERC-20 compatible CDA with mint/burn/redeem "
            "mechanics, 1:1 reserve backing (GENIUS Act Section 4), FDIC pass-through insurance.\n"
            "3. Integration architecture: core banking DDA ledger sync, custody (Fireblocks/BitGo/HSM), "
            "payment rails (FedNow, ACH, Fedwire).\n"
            "4. Cari Network interoperability: cross-bank CDA transfers, shared KYC registry, "
            "network-level mint/burn coordination.\n"
            "5. Data flow diagrams for: DDA deposit -> CDA mint, CDA transfer, CDA redeem -> CDA burn -> DDA settlement.\n"
            "6. Capacity planning and performance requirements.\n\n"
            "All designs must explicitly reference the Issuing Bank, Cari Network, and ZKsync Prividium. "
            "All designs must be GENIUS Act compliant."
        ),
        expected_output=(
            "A comprehensive platform architecture document in markdown format covering all "
            "deliverables listed above, with specific component names, integration patterns, "
            "and data flows for the Issuing Bank's Cari deposit (CDA/DDA) on ZKsync Prividium / Cari Network."
        ),
        agent=agent,
    )


def create_tech_stack_evaluation_task(agent: Agent) -> Task:
    """Task: Evaluate and recommend the technology stack for the Cari deposit platform."""
    return Task(
        description=(
            "Evaluate and recommend the full technology stack for the Issuing Bank's Cari deposit "
            "platform (CDA/DDA) on ZKsync Prividium within the Cari Network.\n\n"
            "Deliverables:\n"
            "1. Technology stack recommendation matrix with rationale for each component.\n"
            "2. ZKsync Prividium infrastructure: node deployment, validator configuration, "
            "zk-proof system, data availability mode.\n"
            "3. Smart contract tooling: development framework (Hardhat/Foundry), testing "
            "(fuzzing, formal verification), upgrade patterns.\n"
            "4. Key management: HSM vendor recommendation, key ceremony procedures, multi-sig.\n"
            "5. Middleware: event indexing, API gateway, message queues, oracle integration.\n"
            "6. DevOps: CI/CD for smart contracts, IaC (Terraform/Pulumi), observability stack.\n"
            "7. Technology risk assessment: vendor lock-in, OSS maturity, upgrade paths.\n\n"
            "All recommendations must reference the Issuing Bank, Cari Network, and ZKsync Prividium. "
            "Prefer enterprise-grade, audited, production-proven technologies."
        ),
        expected_output=(
            "A technology stack evaluation document in markdown format with a recommendation "
            "matrix, infrastructure diagrams, tooling selections, and risk assessment for "
            "the Issuing Bank's Cari deposit (CDA/DDA) ZKsync Prividium deployment within the Cari Network."
        ),
        agent=agent,
    )


def create_security_compliance_task(agent: Agent) -> Task:
    """Task: Produce the security and compliance review for the Cari deposit platform."""
    return Task(
        description=(
            "Produce the complete security, risk, and compliance review for the Issuing Bank's Cari "
            "deposit platform (CDA/DDA) on ZKsync Prividium / Cari Network.\n\n"
            "Deliverables:\n"
            "1. GENIUS Act compliance mapping matrix (each section -> architectural control -> evidence).\n"
            "2. BSA/AML compliance architecture: transaction monitoring, SAR filing, CTR reporting.\n"
            "3. OFAC sanctions screening integration: real-time wallet screening, SDN list checks.\n"
            "4. FinCEN Travel Rule implementation design for transfers >= $3,000.\n"
            "5. NYDFS Part 500 compliance: cybersecurity program, CISO, pen testing, encryption, "
            "incident response, vendor management.\n"
            "6. Cari Network compliance: consortium obligations, cross-bank AML data sharing, "
            "governance compliance, interoperability standards.\n"
            "7. Smart contract security requirements: audit mandates, formal verification, bug bounty.\n"
            "8. Risk register: operational, liquidity, technology, counterparty risks with "
            "likelihood/impact/mitigation.\n"
            "9. Examiner transparency package: how OCC/Fed/NYDFS examiners access data and reports.\n"
            "10. Regulatory guardrail checklist (pass/fail for each requirement).\n\n"
            "All outputs must reference the Issuing Bank, Cari Network, and ZKsync Prividium. "
            "Apply bank-grade standards, not DeFi standards."
        ),
        expected_output=(
            "A comprehensive security and compliance document in markdown format with compliance "
            "mapping matrix, risk register, guardrail checklist, and examiner transparency package "
            "for the Issuing Bank's Cari deposit platform (CDA/DDA) on ZKsync Prividium / Cari Network."
        ),
        agent=agent,
    )


def create_strategic_advisory_task(agent: Agent) -> Task:
    """Task: Produce the strategic advisory report for the Cari deposit initiative."""
    return Task(
        description=(
            "Produce the strategic advisory report for the Issuing Bank's Cari deposit initiative "
            "on the Cari Network / ZKsync Prividium.\n\n"
            "Deliverables:\n"
            "1. Competitive landscape analysis: the Issuing Bank vs. JPMorgan Kinexys, Citi Token Services, "
            "USDF Consortium, Fnality, Partior, and other bank tokenization initiatives.\n"
            "2. Cari Network vendor radar: evaluate ZKsync/Matter Labs, custody vendors "
            "(Fireblocks, BitGo, Anchorage), compliance vendors (Chainalysis, TRM Labs, "
            "Notabene), audit firms (OpenZeppelin, Trail of Bits, Certora).\n"
            "3. Vendor evaluation matrix with scoring (technical capability, enterprise readiness, "
            "financial stability, strategic alignment, TCO).\n"
            "4. Strategic roadmap: Phase 1 (intra-bank CDA) -> Phase 2 (Cari interbank CDA) -> Phase 3 "
            "(extended use cases) -> Phase 4 (retail-facing CDA).\n"
            "5. Business case summary: cost reduction, revenue opportunities, risk reduction, "
            "regulatory positioning.\n"
            "6. Risk/opportunity assessment for the Issuing Bank's Cari Network founding partnership.\n\n"
            "All outputs must reference the Issuing Bank, Cari Network, and ZKsync Prividium. "
            "Frame through the lens of a conservative regional bank."
        ),
        expected_output=(
            "A strategic advisory document in markdown format with competitive analysis, vendor "
            "radar, evaluation matrix, phased roadmap, business case, and risk/opportunity "
            "assessment for the Issuing Bank's Cari Network participation."
        ),
        agent=agent,
    )


def create_arb_synthesis_task(agent: Agent, context_tasks: list[Task]) -> Task:
    """Task: Synthesize all outputs into the final ARB package for the Cari deposit platform."""
    return Task(
        description=(
            "Synthesize all specialist agent outputs into a unified Architecture Review Board (ARB) "
            "package for the Issuing Bank's Cari deposit platform (CDA/DDA) on ZKsync Prividium / Cari Network.\n\n"
            "Your ARB package must include:\n"
            "1. EXECUTIVE SUMMARY: One-page overview for the Issuing Bank leadership and board.\n"
            "2. SOLUTION ARCHITECTURE: Consolidated platform architecture with all components.\n"
            "3. TECHNOLOGY STACK: Finalized technology selections with rationale.\n"
            "4. SECURITY & COMPLIANCE: Consolidated compliance mapping, risk register, guardrails.\n"
            "5. VENDOR RECOMMENDATIONS: Final vendor selections with justification.\n"
            "6. STRATEGIC ROADMAP: Phased implementation plan with decision gates.\n"
            "7. RISK REGISTER: Unified risk register across all domains.\n"
            "8. GO/NO-GO RECOMMENDATION: Clear recommendation with conditions.\n"
            "9. APPENDICES: Detailed technical specifications, compliance checklists, vendor scorecards.\n\n"
            "CRITICAL REQUIREMENTS:\n"
            "- Every section must explicitly reference the Issuing Bank, Cari Network, and ZKsync Prividium.\n"
            "- Flag any non-GENIUS-Act-compliant or non-Cari-compliant elements.\n"
            "- No 'TBD' or placeholder sections -- everything must be specific and actionable.\n"
            "- Format for dual audiences: bank executive leadership AND regulatory examiners.\n"
            "- Include the Head of Digital Assets' commitment context."
        ),
        expected_output=(
            "A complete, production-ready ARB package document in markdown format suitable for "
            "the Issuing Bank leadership, board, and regulatory examiner review. Must cover all 9 sections "
            "listed above with no placeholders or incomplete sections."
        ),
        agent=agent,
        context=context_tasks,
    )
