# Quest 2 — Off-Chain Orchestration Platform

## Architecture Flow Diagrams

### The Issuing Bank Technology Stack Integration

- **Hogan mainframe** (IBM Z) — Core banking (CIF/DDA/GL)
- **IBM Z DIH** — MQ/REST gateway for API-to-Hogan integration
- **Kafka** (Confluent Platform, KRaft mode) — Event bus
- **Azure AKS** — Kubernetes orchestration
- **Azure ACR** (cari-platform.azurecr.io) — Container registry
- **Azure Managed HSM** — Key management

### Mint Flow - Fiat Deposit to Tokenized Deposit via Hogan/Z DIH

```mermaid
sequenceDiagram
    participant Client as API Client
    participant API as FastAPI Router
    participant Comp as Compliance Service
    participant ZDIH as IBM Z DIH - MQ/REST Gateway
    participant Hogan as Hogan Mainframe - CIF/DDA/GL
    participant Res as Reserve Monitor
    participant BC as Blockchain Service
    participant Kafka as Kafka Event Bus - Confluent KRaft

    Client->>API: POST /api/v1/transactions/mint
    API->>Comp: screen_address(to_address)
    Comp-->>API: ComplianceScreeningResult
    alt Blocked/Flagged
        API-->>Client: 200 REJECTED
    end
    API->>ZDIH: verify_deposit(account, ref, amount) [JSON]
    ZDIH->>Hogan: Query CIF/DDA (COBOL copybook)
    Hogan-->>ZDIH: DepositVerification
    ZDIH-->>API: DepositVerification
    alt Not Verified
        API-->>Client: 200 FAILED
    end
    API->>Res: check_mint_allowed(token_amount)
    Res-->>API: (allowed, reason)
    alt Not Allowed
        API-->>Client: 200 FAILED (reserve backing)
    end
    API->>BC: mint(to, amount, reference_id)
    BC-->>API: tx_hash
    API->>ZDIH: post_gl_entries([DEBIT 1010, CREDIT 2010]) [JSON]
    ZDIH->>Hogan: Post GL (COBOL copybook, Post-2025 format)
    Hogan-->>ZDIH: OK
    ZDIH-->>API: OK
    API->>Kafka: publish(MINT_COMPLETED)
    API-->>Client: 200 CONFIRMED (tx_hash)
```

### Burn Flow - Par Redemption - GENIUS Act S5 via Hogan/Z DIH

```mermaid
sequenceDiagram
    participant Client as API Client
    participant API as FastAPI Router
    participant Comp as Compliance Service
    participant BC as Blockchain Service
    participant ZDIH as IBM Z DIH - MQ/REST Gateway
    participant Hogan as Hogan Mainframe - CIF/DDA/GL
    participant Kafka as Kafka Event Bus - Confluent KRaft

    Client->>API: POST /api/v1/transactions/burn
    API->>Comp: screen_address(from_address)
    Comp-->>API: ComplianceScreeningResult
    alt Blocked
        API-->>Client: 200 REJECTED
    end
    API->>BC: burn(from, amount, reference_id)
    BC-->>API: tx_hash
    API->>ZDIH: post_gl_entries([DEBIT 2010, CREDIT 1010]) [JSON]
    ZDIH->>Hogan: Post GL (COBOL copybook, Post-2025 format)
    Hogan-->>ZDIH: OK
    ZDIH-->>API: OK
    API->>ZDIH: send_payment(dest_account, amount, rail) [JSON]
    ZDIH->>Hogan: Payment request (COBOL copybook)
    Hogan-->>ZDIH: PaymentResult (trace_number)
    ZDIH-->>API: PaymentResult (trace_number)
    API->>Kafka: publish(BURN_COMPLETED)
    API-->>Client: 200 CONFIRMED (tx_hash, trace_number)
```

### Cari Settlement Flow - Cross-Bank

```mermaid
sequenceDiagram
    participant Client as API Client
    participant API as FastAPI Router
    participant Comp as Compliance Service
    participant TR as Travel Rule
    participant BC as Blockchain Service
    participant Kafka as Event Middleware

    Client->>API: POST /api/v1/settlement/initiate
    API->>Comp: screen_transaction(orig, benef, amount)
    Comp-->>API: ComplianceScreeningResult
    alt Blocked
        API-->>Client: 200 REJECTED
    end
    API->>TR: compute_travel_rule_hash(parties)
    TR-->>API: combined_hash
    API->>BC: initiate_settlement(dest_bank, orig, benef, amount, hash)
    Note over BC: Burns tokens at source bank
    BC-->>API: tx_hash, settlement_id
    API->>Kafka: publish(SETTLEMENT_INITIATED)
    API-->>Client: 200 CONFIRMED (settlement_id)
```

### Reconciliation Flow

```mermaid
sequenceDiagram
    participant Ops as Operations
    participant API as FastAPI Router
    participant Engine as Reconciliation Engine
    participant OnChain as On-Chain Records
    participant OffChain as Off-Chain GL

    Ops->>API: POST /api/v1/reconciliation/run
    API->>Engine: reconcile()
    Engine->>OnChain: Load on-chain transactions
    Engine->>OffChain: Load off-chain GL entries
    Engine->>Engine: Match by reference_id
    Engine->>Engine: Validate amounts (±$0.01)
    Engine-->>API: ReconciliationEntry[]
    API-->>Ops: Results (matched/unmatched/exceptions)
    Ops->>API: GET /api/v1/reconciliation/summary
    API-->>Ops: ReconciliationSummary
```

### Custody Tier Architecture

```mermaid
graph TD
    subgraph Fireblocks Custody
        HOT[HOT Vault<br/>MPC Signing<br/>Limit: $500K]
        WARM[WARM Vault<br/>Policy-Gated<br/>Limit: $5M]
        COLD[COLD Vault<br/>Air-Gapped HSM<br/>Unlimited]
    end

    HOT <-->|Rebalance| WARM
    WARM <-->|Rebalance| COLD

    MINT[Mint Operations] --> HOT
    BURN[Burn Operations] --> HOT
    RESERVE[Reserve Backing] --> COLD
    SETTLE[Settlements] --> WARM
```
