# Architecture Flow Diagrams — Security, Risk & Compliance Layer

## M&T Bank Technology Stack

- **Hogan mainframe** (IBM Z) — Core banking (CIF/DDA/GL)
- **IBM Z DIH** — MQ/REST gateway for API-to-Hogan integration
- **Kafka** (Confluent Platform, KRaft mode) — Event bus
- **Azure AKS** — Kubernetes orchestration
- **Azure ACR** (mtbcari.azurecr.io) — Container registry
- **Azure Managed HSM** — Key management

## Security Guardian Architecture

```mermaid
graph TB
    subgraph "Security Layer (Azure)"
        KM[Key Management<br/>Azure Managed HSM]
        SP[Signing Policy<br/>Dual Control]
        WT[Wallet Tiering<br/>Hot/Warm/Cold]
        DR[Resilience<br/>DR Playbooks]
    end

    subgraph "Compliance Layer"
        AML[AML/OFAC<br/>CDA Real-time + Batch]
        TR[Travel Rule<br/>FinCEN + Notabene]
        RP[Reserve Proof<br/>CDA/DDA Cryptographic]
        ED[Examiner Dashboard<br/>Regulatory Reporting]
    end

    subgraph "Risk Layer"
        RM[Risk Matrix<br/>12 Baseline Risks]
        CM[Control Matrix<br/>20 Controls]
        IR[Incident Response<br/>Playbook Execution]
    end

    subgraph "Quest 2 — Off-Chain Platform (DDA Layer via Hogan)"
        API[FastAPI Routers]
        BC[Blockchain Service]
        ZDIH[IBM Z DIH<br/>(MQ/REST Gateway)]
        HOGAN[Hogan Mainframe<br/>(CIF/DDA/GL)]
        CU[Custody Adapters]
    end

    subgraph "Quest 1 — Smart Contracts (CDA Layer)"
        MTD[MTokenizedDeposit<br/>(CDA)]
        RO[ReserveOracle]
        CS[CariSettlement]
        OP[Operator<br/>CDA Supply Control]
        SB[Settlement Bank<br/>Daily Net Settlement]
    end

    API --> SP
    SP --> KM
    KM --> BC
    BC --> MTD
    BC --> RO
    BC --> CS
    BC --> OP
    BC --> SB

    API --> AML
    API --> TR

    API --> ZDIH
    ZDIH --> HOGAN

    CU --> WT
    WT --> CU

    DR --> API

    RP --> RO
    RP --> HOGAN

    ED --> RM
    ED --> CM
    ED --> AML
    ED --> RP

    IR --> DR
```

## Signing Policy Flow

```mermaid
sequenceDiagram
    participant User as Operator
    participant API as FastAPI
    participant SP as Signing Policy Engine
    participant Approver1 as Approver #1
    participant Approver2 as Approver #2
    participant HSM as Azure Managed HSM
    participant Chain as ZKsync Prividium

    User->>API: POST /mint ($2M CDA)
    API->>SP: create_signing_request(CDA_MINT, $2M)
    SP->>SP: classify_risk($2M) → HIGH
    SP-->>API: Request created (2 approvals + 1h time-lock)

    Note over SP: Dual Control Required
    Approver1->>SP: approve(request_id, "approver_1")
    Approver2->>SP: approve(request_id, "approver_2")
    SP->>SP: Status → APPROVED

    Note over SP: Time-Lock: Wait 1 hour
    API->>SP: execute(request_id)
    SP->>SP: Check time-lock elapsed
    SP->>HSM: sign(OPERATOR_KEY, tx_hash)
    HSM-->>SP: signature
    SP->>Chain: Submit signed CDA mint transaction
    Chain-->>SP: tx_hash
    SP-->>API: CDA MINTED
```

## AML Screening Flow (CDA Transactions)

```mermaid
sequenceDiagram
    participant TX as CDA Transaction
    participant AML as AML Engine
    participant OFAC as OFAC SDN Check
    participant CTR as CTR Detection
    participant SAR as SAR Patterns
    participant Audit as Audit Log

    TX->>AML: screen_cda_transaction(from, to, $amount)
    AML->>OFAC: Check from_address
    OFAC-->>AML: CLEAN / BLOCKED
    AML->>OFAC: Check to_address
    OFAC-->>AML: CLEAN / BLOCKED

    alt OFAC Match
        AML-->>TX: BLOCKED + freeze CDA
        AML->>Audit: Record OFAC_MATCH alert
    end

    AML->>CTR: Check amount >= $10,000
    alt CTR Threshold
        CTR-->>AML: CTR_REQUIRED
        AML->>Audit: Record CTR alert
    end

    AML->>SAR: Check patterns (structuring, velocity)
    alt Suspicious Pattern
        SAR-->>AML: FLAGGED
        AML->>Audit: Record SAR_PATTERN alert
    end

    AML-->>TX: CDA transfer PASSED / FLAGGED / BLOCKED
```

## Incident Response Flow

```mermaid
sequenceDiagram
    participant Monitor as Health Monitor
    participant IR as Incident Response
    participant PB as DR Playbook
    participant Team as Response Team
    participant Reg as Regulator (NYDFS)

    Monitor->>IR: Detect anomaly (P1_CRITICAL)
    IR->>IR: Create CDA incident
    IR->>PB: Load playbook (key_compromise)

    loop For each playbook step
        PB->>Team: Execute step
        Team-->>PB: Step completed
        PB->>IR: Record progress
    end

    alt P1/P2 Severity
        IR->>IR: Create regulatory notification
        IR->>Reg: Notify within 72 hours
        Reg-->>IR: Acknowledged
    end

    IR->>IR: Resolve incident
    IR->>IR: Post-mortem
```

## Reserve Proof Verification (CDA/DDA Dual-Rail via Hogan)

```mermaid
graph LR
    subgraph "On-Chain CDA State"
        Supply[Total CDA Supply<br/>MTokenizedDeposit]
        Oracle[ReserveOracle<br/>Attestation Hash]
    end

    subgraph "Off-Chain DDA Reserves (Hogan GL)"
        TB[US Treasury Bills<br/>60% — GL 1015]
        FDIC[FDIC Deposits<br/>30% — GL 1010]
        RRP[Fed Reverse Repo<br/>10% — GL 1020]
    end

    subgraph "Proof Engine"
        PE[ReserveProofEngine]
        Hash[SHA-256 Proof Hash]
    end

    subgraph "Hogan Integration"
        ZDIH[IBM Z DIH<br/>(MQ/REST Gateway)]
        HOGAN[Hogan GL Subsystem<br/>(Post-2025 Format)]
    end

    Supply --> PE
    Oracle --> PE
    TB --> ZDIH
    FDIC --> ZDIH
    RRP --> ZDIH
    ZDIH --> HOGAN
    HOGAN --> PE
    PE --> Hash

    Hash --> |"CDA/DDA ratio >= 1.0"| Verified[VERIFIED ✓]
    Hash --> |"CDA/DDA ratio < 1.0"| Failed[FAILED ✗]
```
