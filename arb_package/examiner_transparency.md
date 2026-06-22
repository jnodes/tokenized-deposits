# Examiner Transparency Artifacts

**the Issuing Bank | Cari Network Cari Deposit Account (CDA) Platform**
**ARB Submission -- Regulatory Examiner Access Guide**

---

## 1. Overview

This document provides OCC, Federal Reserve, and NYDFS examiners with a complete guide to accessing, querying, and verifying the the Issuing Bank CDA platform's compliance posture. The platform implements a dual-rail architecture (CDA on-chain + DDA off-chain via Hogan mainframe) with the Operator controlling CDA supply and the Settlement Bank executing daily net settlement. All artifacts are available programmatically via API, through the examiner dashboard, or as exportable reports.

**the Issuing Bank Technology Stack:**
- **Hogan mainframe** (IBM Z) — Source of truth for CIF/DDA off-chain records
- **IBM Z DIH** — Middleware for API-to-Hogan integration (MQ/REST gateway)
- **Post-2025 GL format** (ISO 20022 aligned) — All GL entries via Hogan GL subsystem
- **Azure AKS** — Kubernetes orchestration for CDA platform services
- **Azure Managed HSM** — FIPS 140-2 L3 key management
- **Azure Monitor** — Production observability (Log Analytics, Application Insights)

---

## 2. Examiner Access Points

### API Endpoints

| Endpoint | Method | Description | Authentication |
|----------|--------|-------------|----------------|
| `/api/v1/health` | GET | Platform health status | API key |
| `/api/v1/compliance/screen` | POST | Run compliance screen on address | API key + examiner role |
| `/api/v1/compliance/audit` | GET | Full audit event log | API key + examiner role |
| `/api/v1/reserves/status` | GET | Current reserve backing status | API key + examiner role |
| `/api/v1/reserves/attestation` | GET | Latest reserve attestation proof | API key + examiner role |
| `/api/v1/reconciliation/summary` | GET | On-chain vs off-chain reconciliation | API key + examiner role |

### Examiner Dashboard

The `ExaminerDashboardEngine` provides a consolidated view:

```python
from compliance.examiner_dashboard.engine import ExaminerDashboardEngine

dashboard = ExaminerDashboardEngine()

# Generate summary for examiner
summary = dashboard.generate_dashboard_summary(
    total_supply_usd=50_000_000,
    total_reserves_usd=50_250_000,
    reserve_proof_status="VERIFIED",
    control_effectiveness_pct=92.5,
    open_incidents=0,
    pending_regulatory_notifications=0
)

# Generate specific report
report = dashboard.generate_report(
    report_type="RESERVE_PROOF",
    data={"backing_ratio": 1.005, "attestation_age_hours": 4}
)

# Export to CSV for examiner analysis
csv_output = dashboard.export_csv(reports=[report])
```

### Available Report Types

| Report Type | Content | Frequency |
|------------|---------|------------|
| `RESERVE_PROOF` | CDA/DDA reserve backing ratio, composition, proof hash, attestation timestamp | Daily (automated) |
| `TRANSACTION_SUMMARY` | CDA mint/burn volumes, settlement counts, average amounts | Daily |
| `CONTROL_MATRIX` | 20 controls with implementation status, test results, effectiveness | Monthly |
| `RISK_REGISTER` | 9 risks with inherent/residual scoring, control mapping | Quarterly |
| `AML_SUMMARY` | CDA screening volumes, alert counts, OFAC matches, CTR filings | Weekly |
| `INCIDENT_REPORT` | Open/closed incidents, severity distribution, MTTR | As needed |
| `DUAL_RAIL_RECONCILIATION` | CDA vs DDA matching summary, discrepancies | Daily |

---

## 3. CDA Reserve Verification Procedure

Examiners can independently verify 1:1 CDA reserve backing:

### Step 1: Query On-Chain CDA Supply

```
Contract: TokenizedDeposit (ZKsync Prividium)
Function: totalSupply()
Returns:  Current total CDA token supply in wei (18 decimals)
```

### Step 2: Query Off-Chain DDA Reserves

```
Endpoint: GET /api/v1/reserves/status
Returns:  {
    "total_cda_supply_usd": 50000000.00,
    "total_dda_reserves_usd": 50250000.00,
    "backing_ratio": 1.005,
    "status": "COMPLIANT",
    "last_attestation": "2026-03-21T10:00:00Z"
}
```

### Step 3: Verify Cryptographic Proof

```
Endpoint: GET /api/v1/reserves/attestation
Returns:  {
    "proof_hash": "sha256:abc123...",
    "cda_supply_snapshot": 50000000.00,
    "dda_reserve_components": [
        {"type": "US_TREASURY_BILLS", "amount": 30150000.00, "pct": 60},
        {"type": "FDIC_INSURED_DEPOSITS", "amount": 15075000.00, "pct": 30},
        {"type": "FED_REVERSE_REPO", "amount": 5025000.00, "pct": 10}
    ],
    "attestation_timestamp": "2026-03-21T10:00:00Z",
    "genius_act_s4_compliant": true,
    "genius_act_s6_compliant": true
}
```

### Step 4: Cross-Reference (Dual-Rail)

```
Verification = on_chain_cda_supply <= off_chain_dda_reserves
50,000,000 <= 50,250,000 -> COMPLIANT (backing ratio: 1.005)
```

---

## 4. Audit Trail Access

### Event Types Logged

| Event | Logged Data | Retention |
|-------|------------|------------|
| CDA_MINT_INITIATED | amount, depositor, wallet, timestamp | 7 years |
| CDA_MINT_COMPLETED | amount, wallet, tx_hash, block_number | 7 years |
| CDA_BURN_INITIATED | amount, holder, beneficiary, timestamp | 7 years |
| CDA_BURN_COMPLETED | amount, holder, tx_hash, payout_ref | 7 years |
| COMPLIANCE_SCREEN | address, risk_score, alerts, disposition | 7 years |
| OFAC_BLOCK | address, match_type, SDN_entry | 7 years |
| CTR_FILED | amount, parties, filing_ref | 7 years |
| TRAVEL_RULE_SUBMITTED | amount, originator_hash, beneficiary_hash | 7 years |
| RESERVE_ATTESTATION | cda_supply, dda_reserves, backing_ratio, proof_hash | 7 years |
| KEY_ROTATION | key_id, old_key_ref, new_key_ref, approvers | 7 years |
| INCIDENT_CREATED | incident_id, severity, type, description | 7 years |
| REGULATORY_NOTIFICATION | incident_id, regulator, deadline, status | 7 years |
| DAILY_NET_SETTLEMENT | window_id, net_positions, settlement_bank | 7 years |
| HOGAN_GL_POSTED | gl_ref, debit_account, credit_account, amount | 7 years |
| ZDIH_MESSAGE_SENT | message_id, direction, payload_hash | 7 years |
| ZDIH_MESSAGE_RECEIVED | message_id, response_code, latency_ms | 7 years |

### Query Examples

```
# Get all OFAC blocks in date range
GET /api/v1/compliance/audit?event_type=OFAC_BLOCK&from=2026-01-01&to=2026-03-31

# Get all CTR filings
GET /api/v1/compliance/audit?event_type=CTR_FILED

# Get all key rotation events
GET /api/v1/compliance/audit?event_type=KEY_ROTATION

# Export full audit log as CSV
GET /api/v1/compliance/audit?format=csv&from=2026-01-01
```

---

## 5. Control Effectiveness Verification

### Automated Test Results

Examiners can verify control effectiveness by requesting the latest test execution report:

```
Total Tests:    223
Passing:        223 (100%)
Failing:        0

Breakdown:
- Smart Contracts (Foundry):     104 tests
- Off-Chain Platform (pytest):    57 tests
- Security & Compliance (pytest): 62 tests
```

### Control Matrix Export

```python
from risk.control_matrix.matrix import ControlMatrix

matrix = ControlMatrix()
summary = matrix.get_control_summary()

# Returns:
# {
#     "total_controls": 20,
#     "implemented": 20,
#     "tested": 20,
#     "implementation_rate": 100.0,
#     "test_pass_rate": 100.0,
#     "avg_effectiveness": 92.6,
#     "by_regulation": {
#         "GENIUS_ACT": {"count": 5, "avg_effectiveness": 93.6},
#         "NYDFS_500": {"count": 8, "avg_effectiveness": 90.4},
#         "BSA_AML_OFAC": {"count": 3, "avg_effectiveness": 94.0},
#         "CARI_RULEBOOK": {"count": 4, "avg_effectiveness": 92.5}
#     }
# }

# Export as CSV
csv_data = matrix.export_csv()
```

---

## 6. Incident History Access

### Active Incidents

```
GET /api/v1/incidents?status=active
```

### Regulatory Notifications

```
GET /api/v1/incidents/notifications?regulator=NYDFS
GET /api/v1/incidents/notifications?regulator=OCC
```

### DR Playbook Execution History

```
GET /api/v1/incidents/playbooks?type=key_compromise
GET /api/v1/incidents/playbooks?type=reserve_breach
```

---

## 7. Examiner Walkthrough Checklist

For on-site or remote examinations, the following checklist provides a structured review path:

| # | Check | Method | Expected Result |
|---|-------|--------|------------------|
| 1 | Platform is operational | `GET /healthz` | `{"status": "ok"}` |
| 2 | CDA reserve backing >= 1.0 | `GET /api/v1/reserves/status` | `backing_ratio >= 1.0` |
| 3 | Attestation is fresh | `GET /api/v1/reserves/attestation` | `age < 72 hours` |
| 4 | OFAC screening active | `POST /api/v1/compliance/screen` with test address | Screening result returned |
| 5 | Audit trail populated | `GET /api/v1/compliance/audit` | CDA events present |
| 6 | All controls implemented | Control matrix CSV export | 20/20 implemented |
| 7 | All controls tested | Control matrix CSV export | 20/20 tested |
| 8 | No open P1/P2 incidents | `GET /api/v1/incidents?severity=P1,P2&status=active` | Empty list |
| 9 | Key rotation current | Audit log query for KEY_ROTATION | Within 90-day policy |
| 10 | Risk register current | Risk matrix CSV export | 12 risks with residual scoring |
| 11 | Dual-rail reconciliation | `GET /api/v1/reconciliation/summary` | CDA/DDA balances match |
| 12 | Hogan GL integration | Query HOGAN_GL_POSTED events | GL entries posted in Post-2025 format |
| 13 | Z DIH connectivity | Query ZDIH_MESSAGE_* events | Message round-trip successful |
| 14 | Azure Monitor active | Azure Monitor dashboard | Metrics and logs streaming |
| 15 | Azure Managed HSM audit | Azure Key Vault diagnostics | HSM access logs available |

### Hogan GL Source of Truth

Examiners can request access to the Hogan GL subsystem for off-chain DDA record verification:
- **GL Accounts**: 1010 (Reserve Cash), 1015 (Reserve T-Bills), 1020 (Reserve Fed Deposits), 2010 (CDA Token Liability)
- **GL Format**: Post-2025 GL format (ISO 20022 aligned)
- **Access Method**: Read-only terminal access or Z DIH API query

### IBM Z DIH Audit Trail

All API-to-Hogan message flows are logged for examiner review:
- **Message ID**: Unique identifier for each request/response pair
- **Direction**: INBOUND (API -> Hogan) or OUTBOUND (Hogan -> API)
- **Payload Hash**: SHA-256 hash of message payload for integrity verification
- **Response Code**: Hogan transaction result code
- **Latency**: Round-trip time in milliseconds

### Azure Monitor Observability

Production observability via Azure Monitor:
- **Log Analytics**: Centralized log aggregation for all CDA platform services
- **Application Insights**: Distributed tracing for request flows
- **Azure Managed HSM Diagnostics**: Key access audit logs
- **Azure AKS Metrics**: Container health, resource utilization, pod status

---

*ARB Submission -- Examiner Transparency Artifacts*
*the Issuing Bank | Cari Network CDA Platform | ZKsync Prividium*
