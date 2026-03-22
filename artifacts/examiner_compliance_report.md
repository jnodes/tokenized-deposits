# M&T Bank — Examiner Compliance Report
# Cari Deposit Account (CDA) Platform — Regulatory Readiness Assessment

**Prepared for**: OCC / Federal Reserve / NYDFS Examiners
**Prepared by**: M&T Bank — Digital Assets Compliance Team
**Classification**: CONFIDENTIAL — Examiner Use Only

---

## 1. Program Overview

M&T Bank has developed a Cari Deposit Account (CDA) platform on the Cari Network, a consortium of U.S. regulated banks operating on ZKsync Prividium (a privacy-preserving ZK-rollup). The platform implements a dual-rail architecture with the Operator controlling CDA supply and the Settlement Bank executing daily net settlement. The platform:

- Issues **CDA (Cari Deposit Account)** ERC-20 tokens representing USD deposits
- Operates alongside **DDA (Demand Deposit Accounts)** off-chain fiat accounts in dual-rail configuration via **Hogan mainframe** (IBM Z)
- **Operator** (M&T Bank) controls CDA supply through mint/burn operations
- **Settlement Bank** aggregates and nets daily inter-bank CDA transfers
- **Messaging Bridge** handles cross-bank CDA transfer communication
- Maintains **1:1 reserve backing** (GENIUS Act Section 4) with US Treasury Bills, FDIC-insured deposits, and Fed reverse repo
- Provides **par redemption** (GENIUS Act Section 5) via ACH, Fedwire, RTP/FedNow (processed by Hogan)
- Enables **cross-bank CDA settlement** via Cari Network protocol with Travel Rule compliance
- Implements **bank-grade security controls** per NYDFS 23 NYCRR 500 and Cari Rulebook

### M&T Bank Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Core Banking** | Hogan mainframe (IBM Z) | CIF/DDA ledger, GL posting, payment processing |
| **Middleware** | IBM Z Data Integration Hub (DIH) | JSON/REST to COBOL copybook translation |
| **GL Format** | Post-2025 GL (ISO 20022 aligned) | Hogan GL subsystem |
| **Event Bus** | Kafka (Confluent Platform, KRaft) | Real-time event streaming |
| **Compute** | Azure AKS | Kubernetes orchestration |
| **Container Registry** | Azure ACR (mtbcari.azurecr.io) | Docker image storage |
| **Key Management** | Azure Managed HSM | FIPS 140-2 L3 key storage |
| **Payment Rails** | ACH, Fedwire, RTP/FedNow | Via Hogan payment processing |

## 2. CDA Reserve Backing Verification

### 2.1 On-Chain Enforcement
The `ReserveOracle` smart contract enforces that `totalCDASupply <= totalDDAReserves` at all times. Every CDA mint operation calls `canMint(currentSupply, mintAmount)` which:
1. Verifies `currentCDASupply + mintAmount <= totalDDAReserves`
2. Verifies attestation freshness (< 24 hours old)
3. Reverts the transaction if either check fails

### 2.2 Reserve Composition (as of latest attestation)
| Asset Class | Custodian | Allocation |
|---|---|---|
| US Treasury Bills (< 90 days) | BNY Mellon | 60% |
| FDIC-Insured DDA Deposits | M&T Bank Trust | 30% |
| Fed Reverse Repo (overnight) | FRBNY | 10% |

### 2.3 Cryptographic Proof
Each attestation generates a `ReserveProof` containing:
- On-chain CDA supply snapshot (block number, total CDA supply)
- Off-chain DDA reserve balance (verified with core banking)
- SHA-256 hash of reserve composition
- Combined proof hash for dual-rail verification

## 3. AML/OFAC Controls

### 3.1 Real-Time CDA Screening
Every CDA transaction is screened before on-chain submission:
- **OFAC SDN list**: Address checked against Chainalysis KYT
- **Sanctions lists**: EU, UN, and bilateral sanctions
- **Blocked addresses**: Automatically rejected with audit entry

### 3.2 CDA Transaction Monitoring
- **CTR Detection**: CDA transactions >= $10,000 auto-flagged for Currency Transaction Report
- **Structuring Detection**: Multiple CDA transactions $8K-$10K within 24h trigger alert
- **Velocity Monitoring**: Aggregate CDA volume and count thresholds per address

### 3.3 Travel Rule (FinCEN 31 CFR 1010.410)
For CDA transfers >= $3,000:
- Originator and beneficiary PII collected via API
- SHA-256 hash stored on-chain (PII stored off-chain via Notabene)
- VASP-to-VASP notification via Notabene network

## 4. Cybersecurity Controls (NYDFS 23 NYCRR 500)

### 4.1 Access Controls (500.07)
- 9 segregated key roles with individual HSM-backed keys (including OPERATOR_ROLE)
- Azure Managed HSM for all production signing keys (FIPS 140-2 L3)
- Dual control for key rotation and high-value CDA operations
- Time-locked approvals for critical CDA transactions ($1M+)
- Self-approval prohibited (requestor != approver)

### 4.2 Encryption (500.15)
- All signing keys in Azure Managed HSM (FIPS 140-2 Level 3)
- Travel Rule PII hashed with SHA-256 before on-chain storage
- TLS 1.3 for all API communications
- Azure Key Vault for secrets management

### 4.3 Incident Response (500.16)
Four pre-configured DR playbooks:
1. HSM failure (RTO: 15 minutes)
2. Blockchain RPC failure (RTO: 10 minutes)
3. Key compromise (RTO: 5 minutes)
4. CDA reserve breach (RTO: 30 minutes)

### 4.4 Regulatory Notification (500.17)
- P1/P2 severity incidents auto-flagged for regulatory notification
- 72-hour deadline tracking with audit trail
- Notification content template pre-populated

### 4.5 Azure Infrastructure Controls
- Azure AKS with RBAC and Azure AD integration
- Azure ACR with vulnerability scanning (Defender for Containers)
- Azure Monitor with Log Analytics for centralized observability
- Azure VNet with Private Link for network isolation

## 5. Audit Trail

Every CDA state-changing operation generates an immutable `AuditLogEntry` with:
- Timestamp (UTC)
- Actor (role or service)
- Action (CDA operation performed)
- Resource (target of the action)
- Details (structured metadata)
- Correlation ID (links related CDA/DDA operations)

### Examiner Access
- `GET /api/v1/compliance/audit` — Query with filters (actor, action, resource, since, limit)
- `GET /api/v1/compliance/audit/full` — Complete CDA audit trail export
- `GET /api/v1/reserves/status` — Real-time CDA/DDA reserve backing status
- `GET /api/v1/reconciliation/summary` — CDA/DDA dual-rail matching summary
- Hogan GL subsystem access — Read-only terminal or Z DIH API query for off-chain DDA records
- Azure Monitor dashboards — Production observability and alerting

### Hogan GL Integration (Post-2025 Format)
- **GL Accounts**: 1010 (Reserve Cash), 1015 (Reserve T-Bills), 1020 (Reserve Fed Deposits), 2010 (CDA Token Liability)
- **GL Format**: Post-2025 GL (ISO 20022 aligned)
- **Access**: Z DIH API or read-only Hogan terminal
- **Reconciliation**: Automated dual-rail CDA/DDA matching with alerts

## 6. Control Effectiveness Summary

| Control Area | Controls Mapped | Implemented | Test Pass Rate | Avg. Effectiveness |
|---|---|---|---|---|
| GENIUS Act (S4-S8) | 5 | 5 (100%) | 100% | 94.8% |
| NYDFS 500 | 8 | 8 (100%) | 100% | 90.4% |
| BSA/AML/OFAC | 3 | 3 (100%) | 100% | 94.0% |
| Cari Rulebook | 4 | 4 (100%) | 100% | 92.5% |
| **Total** | **20** | **20 (100%)** | **100%** | **92.6%** |

---

*This report is generated programmatically from the M&T Bank CDA Platform's compliance engine. All data is derived from live control monitoring and automated test results.*

*M&T Bank | Cari Network CDA Platform | ZKsync Prividium*
