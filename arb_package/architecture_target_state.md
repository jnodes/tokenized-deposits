# Target-State Architecture

**M&T Bank | Cari Network Cari Deposit Account (CDA) Platform**
**ARB Submission -- Architecture Diagrams**

---

## 1. System Architecture (Target State -- Production)

```mermaid
graph TB
    subgraph "External Clients"
        IC[Institutional Clients]
        CB[Commercial Banking Portal]
        API_EXT[Partner API Gateway]
    end

    subgraph "M&T Bank - Application Layer - Azure AKS"
        direction TB
        LB[Azure Application Gateway<br/>WAF + TLS Termination]
        
        subgraph "API Tier (AKS Namespace: cari-production)"
            FAST[FastAPI Orchestrator<br/>offchain/main.py]
            MINT_R[CDA Mint/Burn Router]
            SETTLE_R[Settlement Router]
            RECON_R["Reconciliation Router<br/>Post-2025 GL"]
            COMPLY_R[Compliance Router]
            RESERVE_R[Reserve Monitor Router]
        end

        subgraph "Service Tier"
            BLOCKCHAIN[Blockchain Service<br/>Web3 + Contract ABIs]
            COMPLIANCE[Compliance Service<br/>AML/OFAC + Travel Rule]
            AUDIT[Audit Service<br/>Immutable Event Log]
            RESERVE[Reserve Monitor<br/>1:1 CDA Backing Verification]
        end

        subgraph "Security Layer (Azure)"
            AKV[Azure Managed HSM<br/>FIPS 140-2 L3]
            SIGN[Signing Policy Engine<br/>Risk-Tiered Approvals]
            TIER[Wallet Tiering<br/>Hot / Warm / Cold]
            RESIL[Resilience Manager<br/>Circuit Breakers + DR]
        end

        subgraph "Integration Layer - Hogan/Z DIH"
            ZDIH["IBM Z DIH<br/>MQ/REST Gateway"]
            HOGAN["Hogan Mainframe<br/>IBM Z - CIF/DDA/GL"]
            CUSTODY[Custody Adapter<br/>Fireblocks MPC]
            PAYMENT["Payment Rails<br/>ACH/Fedwire/RTP/FedNow<br/>via Hogan"]
        end
    end

    subgraph "Middleware (Azure)"
        KAFKA["Kafka Event Bus<br/>Confluent Platform KRaft"]
        REDIS[Redis Cache<br/>Azure Cache]
        ACR[Azure ACR<br/>mtbcari.azurecr.io]
    end

    subgraph "ZKsync Prividium (Cari Network)"
        direction TB
        RPC[JSON-RPC Endpoint<br/>Prividium Node]
        
        subgraph "Smart Contracts"
            TOKEN[MTBankTokenizedDeposit<br/>CDA ERC-20 + UUPS Proxy]
            ORACLE[CariComplianceOracle<br/>KYC/AML/OFAC]
            ATTEST[ReserveAttestationContract]
        end
        
        subgraph "Cari Network Layer"
            OPERATOR[Operator<br/>M&T CDA Supply Controller]
            SBANK[Settlement Bank<br/>Daily Net Settlement]
            BRIDGE[Messaging Bridge<br/>Cross-Bank Comms]
        end
    end

    subgraph "External Services"
        CHAINALYSIS[Chainalysis KYT<br/>AML/OFAC Screening]
        NOTABENE[Notabene<br/>Travel Rule VASP]
        CHRONICLE[Chronicle Protocol<br/>Reserve Attestation]
        FIREBLOCKS[Fireblocks<br/>MPC Custody]
    end

    subgraph "Monitoring & Observability (Azure)"
        PROM[Prometheus<br/>Metrics Collection]
        GRAF[Grafana<br/>Dashboards + Alerts]
        PAGER[PagerDuty<br/>Incident Management]
        AZMON[Azure Monitor<br/>Log Analytics]
    end

    IC --> LB
    CB --> LB
    API_EXT --> LB
    LB --> FAST

    FAST --> MINT_R
    FAST --> SETTLE_R
    FAST --> RECON_R
    FAST --> COMPLY_R
    FAST --> RESERVE_R

    MINT_R --> BLOCKCHAIN
    MINT_R --> COMPLIANCE
    SETTLE_R --> BLOCKCHAIN
    SETTLE_R --> COMPLIANCE
    RECON_R --> RESERVE
    COMPLY_R --> COMPLIANCE
    RESERVE_R --> RESERVE

    BLOCKCHAIN --> AKV
    BLOCKCHAIN --> SIGN
    AKV --> TIER
    SIGN --> RESIL

    BLOCKCHAIN --> RPC
    RPC --> TOKEN
    RPC --> ORACLE
    RPC --> ATTEST

    TOKEN --> OPERATOR
    OPERATOR --> SBANK
    SBANK --> BRIDGE

    COMPLIANCE --> CHAINALYSIS
    COMPLIANCE --> NOTABENE
    RESERVE --> CHRONICLE

    TIER --> FIREBLOCKS
    TIER --> CUSTODY

    BLOCKCHAIN --> KAFKA
    COMPLIANCE --> KAFKA
    AUDIT --> KAFKA
    FAST --> REDIS

    FAST --> ZDIH
    ZDIH --> HOGAN
    HOGAN --> PAYMENT

    FAST --> PROM
    PROM --> GRAF
    GRAF --> PAGER
    FAST --> AZMON
```

---

## 2. Data Flow Architecture

```mermaid
graph LR
    subgraph "Data Sources"
        TX[CDA Transaction Events]
        BLOCK[Block Confirmations]
        BANK["Hogan DDA/GL Events<br/>via Z DIH"]
        COMP[Compliance Alerts]
    end

    subgraph "Event Bus (Kafka Confluent KRaft)"
        T1[cari.cda.transactions]
        T2[cari.compliance]
        T3[cari.settlement]
        T4[cari.audit]
        T5[cari.reserve.alerts]
    end

    subgraph "Processing"
        P1[CDA Transaction Processor]
        P2[Compliance Screener]
        P3[Settlement Engine]
        P4["Dual-Rail Reconciliation<br/>Post-2025 GL"]
        P5[Reserve Monitor]
    end

    subgraph "Storage"
        PG[(Azure PostgreSQL<br/>CDA/DDA Ledger)]
        RD[(Azure Cache for Redis<br/>State Cache)]
        S3[(Azure Blob<br/>Audit Archive)]
        BC[(ZKsync Prividium<br/>CDA On-Chain State)]
        HOGAN[("Hogan GL<br/>Post-2025 Format")]
    end

    subgraph "Outputs"
        DASH[Examiner Dashboard]
        ALERTS[Alert Manager]
        REPORTS[Compliance Reports]
        API_OUT[External API]
    end

    TX --> T1
    BLOCK --> T1
    BANK --> T3
    COMP --> T2

    T1 --> P1
    T2 --> P2
    T3 --> P3
    T1 --> P4
    T5 --> P5

    P1 --> PG
    P1 --> RD
    P2 --> PG
    P3 --> BC
    P4 --> PG
    P4 --> HOGAN
    P5 --> RD

    P1 --> T4
    P2 --> T4
    P3 --> T4

    T4 --> S3

    PG --> DASH
    PG --> REPORTS
    RD --> ALERTS
    PG --> API_OUT
    HOGAN --> REPORTS
```

---

## 3. Network Architecture

```mermaid
graph TB
    subgraph "Public Internet"
        CLIENT[Client Applications]
    end

    subgraph "DMZ - Azure VNet Public Subnet"
        WAF[Azure WAF]
        APIGW[API Gateway<br/>Rate Limiting + Auth]
    end

    subgraph "Application Tier (Azure AKS Private Subnet)"
        AKS[Azure Kubernetes Service<br/>3 nodes, 3 AZs]
        
        subgraph "Pods"
            API_POD[API Pods x3<br/>FastAPI]
            WORKER_POD[Worker Pods x2<br/>Kafka Consumers]
            MONITOR_POD[Monitor Pod x1<br/>Reserve + Reconciliation]
        end
    end

    subgraph "Data Tier (Azure Private Subnet)"
        PG_DB[(Azure PostgreSQL<br/>Flexible Server<br/>HA + Read Replicas)]
        REDIS_C[(Azure Cache for Redis<br/>Premium Tier)]
        BLOB[(Azure Blob Storage<br/>Audit Archives)]
    end

    subgraph "Blockchain Access (Private Subnet)"
        PRIV_NODE[ZKsync Prividium Node<br/>Dedicated RPC]
    end

    subgraph "HSM (Azure Managed Service)"
        AZ_HSM[Azure Managed HSM<br/>FIPS 140-2 L3]
        AKV[Azure Key Vault<br/>Secrets Management]
    end

    subgraph "Core Banking - M&T Internal Network"
        ZDIH["IBM Z DIH<br/>MQ/REST Gateway"]
        HOGAN["Hogan Mainframe<br/>IBM Z - CIF/DDA/GL"]
    end

    subgraph "Container Registry (Azure)"
        ACR[Azure ACR<br/>mtbcari.azurecr.io]
    end

    subgraph "External Services - VPN / Private Link"
        FB_VPN[Fireblocks<br/>Private API]
        CH_VPN[Chainalysis<br/>Private API]
        NB_VPN[Notabene<br/>API]
    end

    CLIENT --> WAF
    WAF --> APIGW
    APIGW --> AKS
    AKS --> API_POD
    AKS --> WORKER_POD
    AKS --> MONITOR_POD

    API_POD --> PG_DB
    API_POD --> REDIS_C
    WORKER_POD --> PG_DB
    WORKER_POD --> BLOB

    API_POD --> PRIV_NODE
    WORKER_POD --> PRIV_NODE

    API_POD --> AZ_HSM
    API_POD --> AKV

    API_POD --> ZDIH
    ZDIH --> HOGAN

    AKS --> ACR

    API_POD --> FB_VPN
    API_POD --> CH_VPN
    API_POD --> NB_VPN
```

---

## 4. Deployment Architecture (Kubernetes)

```mermaid
graph TB
    subgraph "Azure Kubernetes Service"
        subgraph "Namespace: cari-production"
            subgraph "Deployments"
                D1[api-server<br/>replicas: 3<br/>FastAPI]
                D2[kafka-consumer<br/>replicas: 2<br/>CDA Event Workers]
                D3[reserve-monitor<br/>replicas: 1<br/>CronJob: 5m]
                D4[dual-rail-reconciliation<br/>replicas: 1<br/>CronJob: 1h]
            end

            subgraph "Services"
                SVC1[api-service<br/>ClusterIP :8000]
                SVC2[metrics-service<br/>ClusterIP :9090]
            end

            subgraph "Ingress"
                ING[Ingress Controller<br/>TLS + Path Routing]
            end

            subgraph "ConfigMaps & Secrets"
                CM[cari-cda-config<br/>Environment vars]
                SEC[cari-cda-secrets<br/>Azure Key Vault ref]
            end
        end

        subgraph "Namespace: cari-monitoring"
            PROM_D[Prometheus<br/>replicas: 2]
            GRAF_D[Grafana<br/>replicas: 1]
            ALERT_D[Alertmanager<br/>replicas: 2]
        end
    end

    ING --> SVC1
    SVC1 --> D1
    D1 --> CM
    D1 --> SEC
    D2 --> CM
    D2 --> SEC
    D1 --> SVC2
    SVC2 --> PROM_D
    PROM_D --> GRAF_D
    PROM_D --> ALERT_D
```

---

*ARB Submission -- Architecture Diagrams*
*M&T Bank | Cari Network CDA Platform | ZKsync Prividium*
