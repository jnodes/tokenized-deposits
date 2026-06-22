# Quest 2 — Regulatory Compliance Matrix

## the Issuing Bank Technology Stack

- **Hogan mainframe** (IBM Z) — Core banking (CIF/DDA/GL)
- **IBM Z Data Integration Hub (DIH)** — MQ/REST gateway for API-to-Hogan integration
- **Kafka** (Confluent Platform, KRaft mode) — Event bus
- **Azure AKS** — Kubernetes orchestration
- **Azure ACR** (cari-platform.azurecr.io) — Container registry
- **Azure Managed HSM / Azure Key Vault** — Key management
- **Post-2025 GL format** (ISO 20022 aligned) — GL entries via Hogan GL subsystem

## GENIUS Act Mapping to Off-Chain Platform

| GENIUS Act | Requirement | Platform Implementation | Module |
|---|---|---|---|
| Section 4 | 1:1 Reserve Backing | `ReserveMonitorService` enforces `backing_ratio >= 1.0`; blocks mint if `supply + amount > reserves` | `offchain/services/reserves.py` |
| Section 4 | Reserve Transparency | `GET /api/v1/reserves/status` returns backing ratio, attestation freshness, compliance flag | `offchain/routers/reserves.py` |
| Section 5 | Par Redemption | `POST /api/v1/transactions/burn` burns tokens and initiates fiat payout at 1:1 par value via Hogan | `offchain/routers/transactions.py` |
| Section 6 | Monthly Attestation | Oracle staleness check (`reserve_staleness_seconds=86400`); `attestation_fresh` flag blocks stale mints | `offchain/services/reserves.py` |
| Section 7 | Disclosure | Full audit trail via `GET /api/v1/compliance/audit`; immutable AuditLogEntry for every operation | `offchain/services/audit.py` |
| Section 8 | Interoperability | Cari Network settlement via `POST /api/v1/settlement/initiate`; burn-at-source/mint-at-destination | `offchain/routers/settlement.py` |

## BSA/AML/OFAC Compliance

| Requirement | Implementation | Module |
|---|---|---|
| OFAC Sanctions Screening | `screen_address()` checks against Chainalysis KYT (stub in dev) | `offchain/services/compliance.py` |
| Transaction Screening | `screen_transaction()` screens both parties, flags CTR threshold ($10K) | `offchain/services/compliance.py` |
| FinCEN Travel Rule | `compute_travel_rule_hash()` for transactions >= $3,000; hash stored on-chain | `offchain/services/compliance.py` |
| BSA Reporting | CTR auto-flag at $10K threshold in transaction screening | `offchain/services/compliance.py` |

## NYDFS Part 500 / OCC Guidance

| Requirement | Implementation | Module |
|---|---|---|
| Immutable Audit Trail | Every state-changing operation logged with actor/action/resource/details | `offchain/services/audit.py` |
| Examiner Access | `GET /api/v1/compliance/audit` with query filters (actor, action, since) | `offchain/routers/compliance.py` |
| Separation of Duties | RBAC roles (MINTER, BURNER, ATTESTOR, COMPLIANCE, SETTLEMENT) with separate HSM keys | `offchain/config.py` |
| HSM Key Management | Azure Managed HSM / Azure Key Vault integration (FIPS 140-2 L3) | `offchain/config.py` |
| Custody Controls | Hot/warm/cold tiering with operational limits per tier | `integration/custody/adapter.py` |

## Azure Compliance Controls

| Requirement | Azure Service | Implementation |
|---|---|---|
| Container Security | Azure ACR + Defender for Containers | Image vulnerability scanning, admission control |
| Identity & Access | Azure AKS RBAC + Azure AD | Service principal authentication, role bindings |
| Network Isolation | Azure VNet + Private Link | Private endpoints for Azure services |
| Secrets Management | Azure Key Vault | Secrets rotation, access policies |
| Monitoring | Azure Monitor + Log Analytics | Centralized logging, alerting |

## Hogan/Z DIH Integration Controls

| Requirement | Implementation | Module |
|---|---|---|
| DDA Integration | IBM Z DIH adapter for CIF/DDA queries | `integration/z_dih/adapter.py` |
| GL Posting | Post-2025 GL format (ISO 20022) via Hogan GL subsystem | `integration/z_dih/adapter.py` |
| Payment Processing | Hogan payment rail routing (ACH/Fedwire/RTP/FedNow) | `integration/payments_rails/adapter.py` |
| Message Integrity | Z DIH message signing, COBOL copybook validation | Z DIH audit trail |
| Reconciliation | Dual-rail CDA/DDA matching via Hogan GL | `reconciliation/engine.py` |

## Reconciliation & Examiner Reporting

| Capability | Implementation | Module |
|---|---|---|
| On-Chain/Off-Chain Matching | Match by `reference_id` with $0.01 tolerance | `reconciliation/engine.py` |
| Exception Detection | Flags amount mismatches, orphan records (both directions) | `reconciliation/engine.py` |
| Aggregate Reporting | `GET /api/v1/reconciliation/summary` with matched/unmatched/exception counts | `offchain/routers/reconciliation.py` |
| Double-Entry Bookkeeping | GL entries (DEBIT/CREDIT) posted for every mint/burn via core banking adapter | `integration/core_banking/adapter.py` |
