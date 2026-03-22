# M&T Bank Tokenized Deposit Platform

**FDIC-insured, GENIUS Act-compliant tokenized deposits on the Cari Network / ZKsync Prividium.**

Built by the StableArch Council -- a multi-agent Architecture Review Board powered by [CrewAI](https://github.com/crewAIInc/crewAI).

---

## Platform Status

| Layer | Description | Tests | Status |
|-------|-------------|-------|--------|
| **Quest 0** | StableArch Council (CrewAI multi-agent system) | -- | COMPLETE |
| **Quest 1** | Smart Contracts on ZKsync Prividium | 104/104 | COMPLETE |
| **Quest 2** | Off-Chain FastAPI Orchestration Platform | 57/57 | COMPLETE |
| **Quest 3** | Security, Risk & Compliance Guardian Layer | 62/62 | COMPLETE |
| **Quest 4** | Executive-Ready Output Package | -- | COMPLETE |
| **TOTAL** | | **223/223** | **ALL PASSING** |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Foundry (for smart contract tests)
- Docker (optional, for full stack)

### Setup

```bash
cd cari
pip install -r requirements.txt
```

### Run Tests

```bash
# All off-chain tests (Quest 2 + Quest 3)
PYTHONPATH=. pytest offchain/tests/ tests/compliance/ -v

# Smart contract tests (Quest 1)
forge test -vvv

# Individual quest tests
PYTHONPATH=. pytest offchain/tests/ -v          # Quest 2 (57 tests)
PYTHONPATH=. pytest tests/compliance/ -v        # Quest 3 (62 tests)
```

### Run the Platform

```bash
# Start the FastAPI orchestrator
PYTHONPATH=. uvicorn offchain.main:app --host 0.0.0.0 --port 8000

# Or with Docker Compose (full stack with Kafka, Redis, Postgres, monitoring)
docker-compose -f deployment/docker-compose.yml up -d
```

### Deploy

```bash
# One-command deployment
./deployment/deploy.sh --env=local                # Local Docker Compose
./deployment/deploy.sh --env=prividium-testnet    # Kubernetes testnet
./deployment/deploy.sh --env=prividium-mainnet    # Kubernetes mainnet
```

### Run the StableArch Council

```bash
# Generate full ARB package with multi-agent system
python run.py

# Specific review topic
python run.py --topic "Fireblocks custody integration review for Cari tokenized deposits"

# Guardrails-only mode (check existing document)
python run.py --guardrails-only --input-file docs/arb_package_output.md
```

---

## Project Structure

```
cari/
  # ── Quest 0: StableArch Council (CrewAI) ──────────────
  agents/
    orchestrator/              # Chief Enterprise Architect (manager)
    stablecoin_platform/       # Token mechanics & core banking
    tech_stack/                # Blockchain infrastructure
    security_guardian/         # Security, risk & compliance
    strategic_advisory/        # Market intelligence & vendor eval
  crew.py                      # CrewAI crew assembly
  tasks.py                     # Task definitions
  guardrails.py                # Regulatory compliance checks
  run.py                       # CLI entry point

  # ── Quest 1: Smart Contracts (ZKsync Prividium) ───────
  contracts/
    MTBankTokenizedDeposit.sol # ERC-20 + UUPS upgradeable token
    CariComplianceOracle.sol   # On-chain KYC/AML/OFAC oracle
  test/                        # Foundry test suite (104 tests)

  # ── Quest 2: Off-Chain Orchestration (FastAPI) ────────
  offchain/
    main.py                    # FastAPI application factory
    config.py                  # Environment configuration
    routers/                   # API endpoints (transactions, settlement, etc.)
    services/                  # Business logic (blockchain, compliance, audit)
    models/                    # Pydantic schemas
    tests/                     # Quest 2 test suite (57 tests)
  integration/
    core_banking/              # FIS/Fiserv adapter
    payments_rails/            # ACH, Fedwire, RTP, FedNow adapters
    custody/                   # Fireblocks, Coinbase custody adapters
  middleware/                  # Kafka + Redis event middleware
  reconciliation/              # On-chain / off-chain reconciliation engine

  # ── Quest 3: Security & Compliance Layer ──────────────
  security/
    key_management/            # HSM abstraction (8 key roles, dual control)
    signing/                   # Risk-tiered signing policy engine
    wallet_tiering/            # Hot/warm/cold custody strategy
    resilience/                # Circuit breakers + DR playbooks
  compliance/
    aml_screening/             # Real-time + batch AML/OFAC (Chainalysis)
    travel_rule/               # FinCEN Travel Rule ($3K threshold)
    reserve_proof/             # GENIUS Act 1:1 reserve verification
    examiner_dashboard/        # OCC/Fed/NYDFS examiner reporting
  risk/
    risk_matrix_generator/     # 8 baseline risks, inherent/residual scoring
    control_matrix/            # 16 regulatory controls (GENIUS, NYDFS, BSA)
    incident_response/         # P1-P4 incident management + auto-notification
  tests/compliance/            # Quest 3 test suite (62 tests)

  # ── Quest 4: Executive Package ────────────────────────
  strategic/
    vendor_matrix.md           # Vendor evaluation (Fireblocks, Chainalysis, etc.)
    emerging_tech_assessment.md # Tokenized deposits vs stablecoins, CBDC readiness
    roadmap.md                 # Q4 2026 production roadmap
    executive_memo.md          # One-page strategy memo for leadership
  arb_package/
    executive_summary.md       # ARB submission executive summary
    architecture_target_state.md  # Production architecture (Mermaid diagrams)
    architecture_transitional.md  # Pilot -> mainnet migration
    end_to_end_flows.md        # Mint, burn, settlement, attestation flows
    risk_compliance_matrix.md  # Complete risk & compliance evidence
    control_evidence.md        # 16 controls with test evidence mapping
    examiner_transparency.md   # Regulatory examiner access guide
  deployment/
    .github/workflows/         # CI/CD pipelines (GitHub Actions)
    helm/cari-platform/        # Kubernetes Helm charts (3 environments)
    docker-compose.yml         # Full-stack local deployment
    monitoring/                # Prometheus, Grafana, alert rules
    deploy.sh                  # One-command deploy script
    runbooks/                  # Operational runbooks (outage, reserve, key)
  final/
    board_presentation.md      # Board-level slide deck (Markdown -> PPT)
    one_page_strategy.md       # Executive memo for Matt McAfee
    cost_estimate.md           # Investment & ROI analysis
    stablearch_council_review.md # Council cross-check & governance sign-off
    launch_readiness_report.md # Final launch readiness assessment
```

---

## How M&T Launches This in 2026

### Phase 1: Internal Pilot (Q2 2026)

1. Submit ARB package (`arb_package/`) for Architecture Review Board approval
2. Execute vendor agreements (Fireblocks custody, Chainalysis KYT, Notabene Travel Rule)
3. Deploy full stack to Prividium testnet:
   ```bash
   ./deployment/deploy.sh --env=prividium-testnet
   ```
4. Commission independent security audit (Trail of Bits or OpenZeppelin)
5. Run UAT with M&T Treasury Operations

### Phase 2: Prividium Mainnet (Q3 2026)

6. Remediate any audit findings (CRITICAL/HIGH)
7. Deploy to Prividium mainnet:
   ```bash
   ./deployment/deploy.sh --env=prividium-mainnet
   ```
8. File OCC Activity Letter and FDIC notification
9. Launch intra-bank settlement (M&T internal transfers)
10. Complete OCC/NYDFS examiner walkthrough

### Phase 3: Cari Network Production (Q4 2026)

11. Enable inter-bank settlement with Cari Network founding banks
12. Activate liquidity sharing protocol
13. **PRODUCTION GO-LIVE** (December 2026)
14. 90-day post-launch monitoring and stabilization

### Phase 4: Expansion (2027+)

15. Programmable escrow for commercial real estate
16. Tokenized repo/lending products
17. Additional Cari Network bank partners
18. Cross-border settlement pilot
19. CBDC bridge readiness

---

## Regulatory Coverage

| Regulation | Controls | Status |
|------------|----------|--------|
| GENIUS Act (Sections 4-8) | 5 | 100% implemented, 100% tested |
| NYDFS 23 NYCRR 500 | 8 | 100% implemented, 100% tested |
| BSA/AML/OFAC | 3 | 100% implemented, 100% tested |
| **Total** | **16** | **92.5% avg effectiveness** |

---

## StableArch Council Agents

| Agent | Role |
|-------|------|
| **Orchestrator** | Chief Enterprise Architect -- coordinates all agents, synthesizes ARB package |
| **Stablecoin Platform Architect** | Token mechanics, core banking integration, Cari interoperability |
| **Blockchain Technology Stack Expert** | ZKsync Prividium infrastructure, tooling, DevOps |
| **Security, Risk & Compliance Guardian** | GENIUS Act, BSA/AML/OFAC, NYDFS 500, risk register |
| **Strategic Advisory** | Competitive landscape, vendor evaluation, roadmap, business case |

---

## ARB Decision

**APPROVE WITH CONDITIONS** (Confidence: 91.35/100)

Conditions (all resolved during Phase 1 pilot):
1. Independent smart contract security audit
2. NYDFS 500.05 penetration test
3. Fireblocks Prividium network validation
4. Chainalysis Cari Network address coverage
5. Treasury Operations UAT sign-off

See `final/launch_readiness_report.md` for the complete assessment.

---

## Context

- **M&T Bank** is a founding partner in the Cari Network
- **Matt McAfee** (Head of Digital Assets) has publicly committed to tokenized deposits
- **Cari Network** runs on **ZKsync Prividium** (private permissioned zkRollup L2)
- Tokenized deposits are **FDIC-insured bank liabilities**, not stablecoins
- All designs comply with **GENIUS Act**, **BSA/AML/OFAC/Travel Rule**, and **NYDFS Part 500**

---

*M&T Bank | Cari Network | ZKsync Prividium*
*StableArch Council -- Architecture Review Board*
