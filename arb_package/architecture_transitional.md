# Transitional Architecture

**M&T Bank | Cari Network Cari Deposit Account (CDA) Platform**
**ARB Submission -- Pilot to Production Migration**

---

## 1. Architecture Evolution Phases

```mermaid
graph LR
    subgraph "Phase 1: Internal Pilot"
        P1A["Single-node deployment<br/>Docker Compose"]
        P1B[Stub HSM + Stub Custody<br/>+ Stub Z DIH]
        P1C[Prividium Testnet]
        P1D[M&T internal CDA only]
    end

    subgraph "Phase 2: Prividium Mainnet"
        P2A["Azure AKS cluster<br/>3 nodes, 3 AZs"]
        P2B[Fireblocks MPC +<br/>Azure Managed HSM]
        P2C[Prividium Mainnet]
        P2D[Intra-bank CDA settlement<br/>+ Hogan/Z DIH integration]
    end

    subgraph "Phase 3: Cari Network"
        P3A[Multi-region AKS<br/>+ Azure ACR]
        P3B["Full vendor stack<br/>+ Hogan GL Post-2025"]
        P3C[Cari Network interop]
        P3D[Inter-bank CDA settlement<br/>via Settlement Bank]
    end

    P1A --> P2A
    P1B --> P2B
    P1C --> P2C
    P1D --> P2D
    P2A --> P3A
    P2B --> P3B
    P2C --> P3C
    P2D --> P3D
```

---

## 2. Phase 1: Internal Pilot Architecture

**Purpose:** Validate end-to-end CDA flows with M&T Treasury Operations on testnet.

```mermaid
graph TB
    subgraph "M&T Internal Network"
        subgraph "Single VM (Azure D4s_v3)"
            DOCKER[Docker Compose]
            API[FastAPI :8000]
            PG[(PostgreSQL :5432)]
            REDIS[(Redis :6379)]
            KAFKA[Kafka :9092<br/>Single broker]
        end

        subgraph "Stub Services"
            STUB_HSM[Stub HSM<br/>In-memory keys]
            STUB_CUSTODY[Stub Custody<br/>CDA Balance tracking]
            STUB_CHAINALYSIS[Stub AML<br/>Allowlist mode]
        end
    end

    subgraph "ZKsync Prividium Testnet"
        TEST_RPC[Testnet RPC]
        TEST_TOKEN[MTBankTokenizedDeposit<br/>CDA Test deployment]
        TEST_ORACLE[CariComplianceOracle<br/>Test deployment]
    end

    DOCKER --> API
    API --> PG
    API --> REDIS
    API --> KAFKA
    API --> STUB_HSM
    API --> STUB_CUSTODY
    API --> STUB_CHAINALYSIS
    API --> TEST_RPC
    TEST_RPC --> TEST_TOKEN
    TEST_RPC --> TEST_ORACLE
```

### Phase 1 Configuration

| Component | Pilot Config | Production Config |
|-----------|-------------|-------------------|
| Compute | 1x Azure D4s_v3 | 3x Azure AKS nodes (3 AZs) |
| Container Registry | Local Docker | Azure ACR (mtbcari.azurecr.io) |
| Database | PostgreSQL (single) | Azure PostgreSQL Flexible (HA) |
| Cache | Redis (single) | Azure Cache Premium (cluster) |
| HSM | Stub (in-memory) | Azure Managed HSM (FIPS 140-2 L3) |
| Custody | Stub (balance tracking) | Fireblocks MPC |
| AML/OFAC | Stub (allowlist) | Chainalysis KYT (real-time) |
| Core Banking | Stub Z DIH (mock responses) | IBM Z DIH -> Hogan mainframe |
| GL Format | Stub GL (JSON) | Hogan GL (Post-2025, ISO 20022) |
| Blockchain | Prividium testnet | Prividium mainnet |
| Event Bus | Kafka (single broker) | Kafka Confluent Platform (KRaft) |
| Monitoring | Console logging | Prometheus + Grafana + Azure Monitor |

---

## 3. Phase 1 -> Phase 2 Migration

### Migration Steps

```mermaid
sequenceDiagram
    participant DEV as Phase 1 (Testnet)
    participant CI as CI/CD Pipeline
    participant ACR as Azure ACR
    participant AKS as Phase 2 (Azure AKS)
    participant HSM as Azure Managed HSM
    participant FB as Fireblocks
    participant ZDIH as IBM Z DIH
    participant HOGAN as Hogan Mainframe

    Note over DEV,HOGAN: Migration Sequence

    DEV->>CI: 1. Tag release (v1.0.0-rc1)
    CI->>CI: 2. Run full test suite (223 tests)
    CI->>ACR: 3. Build + push production images to ACR
    CI->>CI: 4. Security scan (Trivy + Defender for Containers)

    Note over HSM,HOGAN: Vendor & Infrastructure Provisioning (pre-migration)
    HSM->>HSM: 5. Generate production key material
    FB->>FB: 6. Configure Prividium network
    FB->>FB: 7. Create vault policies
    ZDIH->>ZDIH: 8. Configure Z DIH endpoints (JSON -> COBOL)
    ZDIH->>HOGAN: 9. Validate Hogan connectivity (CIF/DDA/GL)

    ACR->>AKS: 10. Deploy to AKS (blue-green from ACR)
    AKS->>HSM: 11. Connect Azure Managed HSM (swap stub -> real)
    AKS->>FB: 12. Connect Fireblocks (swap stub -> real)
    AKS->>ZDIH: 13. Connect Z DIH (swap stub -> Hogan integration)

    Note over AKS: Phase 2 Go-Live
    AKS->>AKS: 14. Deploy mainnet contracts
    AKS->>AKS: 15. Smoke test (mint $1, burn $1)
    AKS->>AKS: 16. Enable Azure Monitor + alerting
    AKS->>AKS: 17. Route production traffic
```

### Configuration Changes (Pilot -> Mainnet)

```yaml
# Phase 1 (Pilot)
environment: dev
blockchain:
  network: prividium-testnet
  rpc_url: https://testnet.prividium.zksync.io
hsm:
  provider: stub
custody:
  provider: stub
compliance:
  aml_provider: stub
  aml_mode: allowlist
core_banking:
  provider: stub_zdih
  hogan_enabled: false
container_registry: local
event_bus:
  provider: kafka
  mode: single-broker

# Phase 2 (Mainnet)
environment: production
blockchain:
  network: prividium-mainnet
  rpc_url: https://mainnet.prividium.zksync.io
hsm:
  provider: azure_managed_hsm
  resource_id: /subscriptions/.../managedHSMs/cari-prod
custody:
  provider: fireblocks
  api_key: ${FIREBLOCKS_API_KEY}
  vault_id: ${FIREBLOCKS_VAULT_ID}
compliance:
  aml_provider: chainalysis
  api_key: ${CHAINALYSIS_API_KEY}
  aml_mode: realtime
core_banking:
  provider: ibm_z_dih
  zdih_url: ${ZDIH_GATEWAY_URL}
  hogan_enabled: true
  gl_format: post_2025_iso20022
container_registry: mtbcari.azurecr.io
event_bus:
  provider: kafka
  mode: confluent_kraft
  bootstrap_servers: ${KAFKA_BOOTSTRAP_SERVERS}
```

---

## 4. Phase 2 -> Phase 3 Migration (Cari Network Interop)

### New Components for Inter-Bank CDA Settlement

```mermaid
graph TB
    subgraph "M&T Bank - Phase 2 Existing"
        API[FastAPI Orchestrator]
        SETTLE[Settlement Service]
        COMPLY[Compliance Service]
    end

    subgraph "M&T Core Banking - Hogan/Z DIH"
        ZDIH["IBM Z DIH<br/>MQ/REST Gateway"]
        HOGAN["Hogan Mainframe<br/>CIF/DDA/GL"]
    end

    subgraph "New: Cari Network Gateway"
        CARI_GW[Cari Gateway Service]
        CARI_AUTH[Cari Auth<br/>Bank Identity + mTLS]
        CARI_ROUTE[Cari Router<br/>Counterparty Discovery]
    end

    subgraph "Cari Network (ZKsync Prividium)"
        OPERATOR[Operator<br/>CDA Supply Controller]
        SBANK[Settlement Bank<br/>Daily Net Settlement]
        BRIDGE[Messaging Bridge<br/>Cross-Bank Comms]
        CARI_ORACLE[Cari Network<br/>Compliance Oracle]
    end

    subgraph "Counterparty Banks"
        BANK_B[Bank B Gateway]
        BANK_C[Bank C Gateway]
    end

    API --> CARI_GW
    SETTLE --> CARI_GW
    COMPLY --> CARI_GW

    API --> ZDIH
    ZDIH --> HOGAN

    CARI_GW --> CARI_AUTH
    CARI_GW --> CARI_ROUTE
    CARI_AUTH --> OPERATOR
    CARI_ROUTE --> BRIDGE
    OPERATOR --> SBANK
    SBANK --> BRIDGE

    BRIDGE --> CARI_ORACLE

    BRIDGE --> BANK_B
    BRIDGE --> BANK_C
```

### Phase 3 Additions

| Component | Purpose | Integration Point |
|-----------|---------|-------------------|
| Cari Gateway Service | Inter-bank CDA message routing | New microservice alongside FastAPI |
| Cari Auth (mTLS) | Bank identity verification | Certificate-based mutual TLS |
| Cari Router | Counterparty bank discovery | Cari Network directory service |
| Operator Contract | M&T Bank controls CDA supply (mint/burn) | OPERATOR_ROLE on-chain |
| Settlement Bank | Daily net settlement of CDA transfers | SETTLEMENT_BANK_ROLE on-chain |
| Messaging Bridge | Cross-bank CDA transfer communication | New Prividium contract deployment |
| Hogan GL Integration | Post-2025 GL format for dual-rail reconciliation | Z DIH -> Hogan GL subsystem |
| Azure ACR | Container images for multi-region AKS | mtbcari.azurecr.io |

### Migration Path: GHCR -> Azure ACR

| Phase | Container Registry | Notes |
|-------|-------------------|-------|
| Phase 1 (Pilot) | Local Docker / GHCR | Development convenience |
| Phase 2 (Mainnet) | Azure ACR (mtbcari.azurecr.io) | M&T standard; geo-replication |
| Phase 3 (Cari Network) | Azure ACR (multi-region) | Cross-AZ resilience |

---

## 5. Rollback Strategy

Each phase supports full rollback:

| Phase Transition | Rollback Method | RTO |
|-----------------|-----------------|-----|
| Phase 1 -> Phase 2 | Blue-green deployment; switch back to blue | 5 minutes |
| Phase 2 -> Phase 3 | Disable Cari Gateway; revert to intra-bank only | 10 minutes |
| Smart contract upgrade | UUPS proxy -- revert to previous implementation | 1 block (~2 seconds) |
| Vendor failover | Switch custody/AML to secondary provider | 15 minutes |

### Emergency Procedures

```
CRITICAL ROLLBACK (smart contract vulnerability):
1. PAUSER key holder pauses CDA token contract (immediate)
2. Engineering reviews vulnerability
3. Deploy patched implementation via UUPS proxy
4. UPGRADER key holder upgrades (dual approval required)
5. Resume CDA operations after verification

NON-CRITICAL ROLLBACK (API service issue):
1. AKS deployment rollback: kubectl rollout undo
2. Verify health checks passing
3. Investigate root cause
4. Deploy fix through normal CI/CD pipeline
```

---

*ARB Submission -- Transitional Architecture*
*M&T Bank | Cari Network CDA Platform | ZKsync Prividium*
