# End-to-End Transaction Flows

**The Issuing Bank | Cari Network Cari Deposit Account (CDA) Platform**
**ARB Submission -- Transaction Flow Documentation**

---

## 1. CDA Mint Flow (DDA Deposit -> CDA Token Creation via Operator)

```mermaid
sequenceDiagram
    participant Client as Institutional Client
    participant API as FastAPI Orchestrator
    participant COMPLY as Compliance Service
    participant AML as Chainalysis KYT
    participant ZDIH as IBM Z DIH - MQ/REST Gateway
    participant HOGAN as Hogan Mainframe - CIF/DDA/GL
    participant SIGN as Signing Policy Engine
    participant HSM as Azure Managed HSM
    participant OPERATOR as Operator - the Issuing Bank Supply Controller
    participant BC as ZKsync Prividium
    participant TOKEN as TokenizedDeposit - CDA
    participant AUDIT as Audit Service

    Client->>API: POST /api/v1/transactions/mint<br/>{depositor, amount, wallet_address}

    Note over API,COMPLY: Step 1: Compliance Pre-Check
    API->>COMPLY: screen_address(wallet_address)
    COMPLY->>AML: Real-time OFAC/sanctions check
    AML-->>COMPLY: {risk_score: 0.02, ofac_match: false}
    COMPLY-->>API: PASSED

    Note over API,HOGAN: Step 2: Verify DDA Fiat Deposit (via Z DIH -> Hogan)
    API->>ZDIH: verify_deposit(depositor, amount) [JSON]
    ZDIH->>HOGAN: Query CIF/DDA (COBOL copybook)
    HOGAN-->>ZDIH: DDA balance confirmed
    ZDIH-->>API: {verified: true, deposit_ref: "DEP-2026-001"}

    Note over API,HOGAN: Step 3: Post GL Entries (Dual-Rail DDA->CDA via Hogan)
    API->>ZDIH: post_gl_entries(debit: 1010, credit: 2010) [JSON]
    ZDIH->>HOGAN: Post GL (COBOL copybook, Post-2025 format)
    HOGAN-->>ZDIH: {posted: true, gl_ref: "GL-2026-001"}
    ZDIH-->>API: GL posted

    Note over API,SIGN: Step 4: Signing Approval
    API->>SIGN: create_signing_request(MINT, amount)
    SIGN->>SIGN: classify_risk(amount) -> LOW
    SIGN-->>API: {request_id, required_approvals: 1}
    API->>SIGN: approve(request_id, approver_id)
    SIGN-->>API: APPROVED

    Note over API,BC: Step 5: Operator Initiates On-Chain CDA Mint
    API->>OPERATOR: Operator initiates CDA mint (DDA->CDA)
    OPERATOR->>HSM: sign(MINTER_KEY, mint_tx_data)
    HSM-->>OPERATOR: {signature}
    OPERATOR->>BC: send_transaction(mint(wallet, amount))
    BC->>TOKEN: mint(wallet, amount)
    TOKEN->>TOKEN: _beforeTokenTransfer -> compliance check
    TOKEN-->>BC: {tx_hash, block_number}
    BC-->>OPERATOR: {tx_hash: "0xabc...", status: confirmed}

    Note over API,AUDIT: Step 6: Record & Respond
    API->>AUDIT: log(CDA_MINT_COMPLETED, {amount, wallet, tx_hash})
    API-->>Client: 200 OK {tx_hash, amount, status: "cda_minted"}
```

---

## 2. CDA Burn/Redeem Flow (CDA -> DDA Fiat Payout via Operator)

```mermaid
sequenceDiagram
    participant Client as Institutional Client
    participant API as FastAPI Orchestrator
    participant COMPLY as Compliance Service
    participant TRAVEL as Travel Rule Engine
    participant SIGN as Signing Policy Engine
    participant HSM as Azure Managed HSM
    participant OPERATOR as Operator - the Issuing Bank Supply Controller
    participant BC as ZKsync Prividium
    participant TOKEN as TokenizedDeposit - CDA
    participant ZDIH as IBM Z DIH - MQ/REST Gateway
    participant HOGAN as Hogan Mainframe - CIF/DDA/GL
    participant AUDIT as Audit Service

    Client->>API: POST /api/v1/transactions/burn<br/>{holder, amount, payout_method, beneficiary}

    Note over API,COMPLY: Step 1: Compliance Pre-Check
    API->>COMPLY: screen_transaction(holder, amount)
    COMPLY-->>API: PASSED (no alerts)

    Note over API,TRAVEL: Step 2: Travel Rule Check
    API->>TRAVEL: process_transfer(amount, originator, beneficiary)
    alt amount >= $3,000
        TRAVEL->>TRAVEL: compute_hashes(PII)
        TRAVEL->>TRAVEL: notify_vasp(Notabene)
        TRAVEL-->>API: {required: true, status: SUBMITTED}
    else amount < $3,000
        TRAVEL-->>API: {required: false}
    end

    Note over API,SIGN: Step 3: Signing Approval
    API->>SIGN: create_signing_request(BURN, amount)
    SIGN->>SIGN: classify_risk(amount)
    Note right of SIGN: HIGH risk (>$1M):<br/>3 approvals + 1h time-lock
    SIGN-->>API: {request_id, required_approvals: N}
    loop Until approved
        API->>SIGN: approve(request_id, approver_N)
    end
    SIGN-->>API: APPROVED (after time-lock if applicable)

    Note over API,BC: Step 4: Operator Initiates On-Chain CDA Burn
    API->>OPERATOR: Operator initiates CDA burn (CDA->DDA)
    OPERATOR->>HSM: sign(BURNER_KEY, burn_tx_data)
    HSM-->>OPERATOR: {signature}
    OPERATOR->>BC: send_transaction(burn(holder, amount))
    BC->>TOKEN: burn(holder, amount)
    TOKEN-->>BC: {tx_hash, block_number}
    BC-->>OPERATOR: {tx_hash, status: confirmed}

    Note over API,HOGAN: Step 5: DDA Fiat Payout (Dual-Rail via Hogan)
    API->>ZDIH: post_gl_entries(debit: 2010, credit: 1010) [JSON]
    ZDIH->>HOGAN: Post GL (COBOL copybook, Post-2025 format)
    HOGAN-->>ZDIH: GL posted
    API->>ZDIH: initiate_payout(beneficiary, amount, method) [JSON]
    ZDIH->>HOGAN: Payment request (COBOL copybook)
    alt method = ACH
        HOGAN-->>ZDIH: {status: pending, settlement: T+1}
    else method = Fedwire
        HOGAN-->>ZDIH: {status: settled, settlement: real-time}
    else method = RTP/FedNow
        HOGAN-->>ZDIH: {status: settled, settlement: real-time}
    end
    ZDIH-->>API: Payout status

    Note over API,AUDIT: Step 6: Record & Respond
    API->>AUDIT: log(CDA_BURN_COMPLETED, {amount, holder, tx_hash, payout_ref})
    API-->>Client: 200 OK {tx_hash, payout_ref, status: "cda_redeemed_to_dda"}
```

---

## 3. Inter-Bank CDA Settlement Flow (via Settlement Bank & Messaging Bridge)

```mermaid
sequenceDiagram
    participant MT as the Issuing Bank
    participant MT_GW as the Issuing Bank Cari Gateway
    participant BRIDGE as Messaging Bridge
    participant SBANK as Settlement Bank
    participant ORACLE as Compliance Oracle
    participant SETTLE as Settlement Contract - Prividium
    participant BP_GW as Bank B Cari Gateway
    participant BP as Bank B

    MT->>MT_GW: Initiate inter-bank CDA transfer<br/>{amount: $5M, counterparty: Bank B}

    Note over MT_GW,BRIDGE: Step 1: Pre-flight Checks
    MT_GW->>MT_GW: Verify CDA reserve backing (1:1)
    MT_GW->>ORACLE: Compliance check (both parties)
    ORACLE-->>MT_GW: CLEARED

    Note over MT_GW,SETTLE: Step 2: Create CDA Settlement via Messaging Bridge
    MT_GW->>BRIDGE: Cross-bank CDA transfer message
    BRIDGE->>SETTLE: createSettlement(the Issuing Bank, BankB, $5M)
    SETTLE->>SETTLE: Lock the Issuing Bank CDA ($5M)
    SETTLE-->>BRIDGE: {settlement_id, status: PENDING}
    BRIDGE->>SBANK: Queue for daily net settlement

    Note over SBANK,BP_GW: Step 3: Counterparty Confirmation
    SBANK->>BP_GW: Notify: incoming CDA settlement
    BP_GW->>BP: Verify acceptance
    BP-->>BP_GW: ACCEPTED
    BP_GW->>SBANK: confirmSettlement(settlement_id)

    Note over SBANK,SETTLE: Step 4: Daily Net Settlement Execution
    SBANK->>SBANK: Calculate net CDA positions at window close
    SBANK->>SETTLE: netSettle(settlement_id)
    SETTLE->>SETTLE: Transfer the Issuing Bank CDA -> Bank B
    SETTLE->>SETTLE: Update reserve allocations
    SETTLE-->>SBANK: {status: SETTLED, block: 12345}
    SBANK-->>MT_GW: {status: SETTLED, block: 12345}
    SBANK-->>BP_GW: {status: SETTLED, block: 12345}

    Note over MT,BP: Step 5: Dual-Rail Off-Chain DDA Reconciliation
    MT_GW->>MT: Update DDA ledger (debit $5M)
    BP_GW->>BP: Update DDA ledger (credit $5M)
    MT->>MT: Post GL entries (CDA + DDA)
    BP->>BP: Post GL entries (CDA + DDA)
```

---

## 4. Daily Net Settlement Flow (Settlement Bank)

```mermaid
sequenceDiagram
    participant Banks as Cari Member Banks
    participant BRIDGE as Messaging Bridge
    participant SBANK as Settlement Bank
    participant CONTRACT as CariSettlement - Prividium
    participant DDA as DDA Rails - FedNow/Fedwire

    Note over Banks,DDA: DAILY SETTLEMENT WINDOW OPENS

    SBANK->>CONTRACT: openSettlementWindow(windowId)
    CONTRACT-->>CONTRACT: emit SettlementWindowOpened(windowId, timestamp)

    Note over Banks,DDA: Banks initiate CDA transfers during window

    loop Throughout settlement window
        Banks->>BRIDGE: Initiate CDA transfers
        BRIDGE->>SBANK: Queue transfers for netting
        SBANK->>SBANK: Accumulate net CDA positions
    end

    Note over Banks,DDA: Window closes - Net positions calculated

    SBANK->>CONTRACT: closeSettlementWindow(windowId)
    CONTRACT-->>CONTRACT: emit SettlementWindowClosed(windowId, timestamp)

    SBANK->>SBANK: Calculate net CDA positions per bank
    SBANK->>SBANK: Calculate net DDA positions per bank (dual-rail)

    Note over Banks,DDA: Execute netSettle on-chain (CDA) + off-chain (DDA)

    SBANK->>CONTRACT: netSettle(windowId, netPositions[])
    CONTRACT->>CONTRACT: For each net position: mint/burn CDA
    CONTRACT-->>CONTRACT: emit NetSettlementExecuted(windowId, positions[])

    SBANK->>DDA: Execute DDA net settlements (dual-rail)
    DDA-->>Banks: DDA balances adjusted via FedNow/Fedwire

    Note over Banks,DDA: Dual-rail CDA + DDA settlement complete
```

---

## 5. Reserve Attestation Flow

```mermaid
sequenceDiagram
    participant CRON as Scheduled Job - Daily
    participant RESERVE as Reserve Monitor
    participant ZDIH as IBM Z DIH - MQ/REST Gateway
    participant HOGAN as Hogan Mainframe - DDA Reserves/GL
    participant BC as ZKsync Prividium
    participant TOKEN as CDA Token Contract
    participant PROOF as Reserve Proof Engine
    participant ATTEST as Attestation Contract
    participant EXAM as Examiner Dashboard

    CRON->>RESERVE: trigger_attestation()

    Note over RESERVE,TOKEN: Step 1: Snapshot On-Chain CDA Supply
    RESERVE->>BC: call(token.totalSupply())
    BC->>TOKEN: totalSupply()
    TOKEN-->>RESERVE: {total_cda_supply: 50000000}

    Note over RESERVE,HOGAN: Step 2: Verify Off-Chain DDA Reserves (via Z DIH -> Hogan)
    RESERVE->>ZDIH: get_reserve_balance() [JSON]
    ZDIH->>HOGAN: Query reserve GL accounts (COBOL copybook)
    HOGAN->>HOGAN: Sum: 1010 + 1015 + 1020 (Post-2025 GL)
    HOGAN-->>ZDIH: {reserve_total: 50250000, breakdown: {...}}
    ZDIH-->>RESERVE: {reserve_total: 50250000}

    Note over RESERVE,PROOF: Step 3: Generate Cryptographic Proof
    RESERVE->>PROOF: generate_proof(cda_supply, dda_reserves)
    PROOF->>PROOF: Compute backing_ratio: 1.005
    PROOF->>PROOF: Compute proof_hash (SHA-256)
    PROOF->>PROOF: Validate GENIUS Act S4 (>=1.0)
    PROOF->>PROOF: Validate GENIUS Act S6 (freshness <72h)
    PROOF-->>RESERVE: {proof_hash, backing_ratio: 1.005, status: VERIFIED}

    Note over RESERVE,ATTEST: Step 4: Publish On-Chain
    RESERVE->>ATTEST: publishAttestation(proof_hash, timestamp)
    ATTEST-->>RESERVE: {tx_hash, block_number}

    Note over RESERVE,EXAM: Step 5: Update Dashboard
    RESERVE->>EXAM: update_summary(proof)
    EXAM-->>RESERVE: {dashboard_updated: true}

    Note over RESERVE: CDA/DDA Attestation Complete
    RESERVE->>RESERVE: log(ATTESTATION_PUBLISHED)
```

---

## 6. Incident Response Flow

```mermaid
sequenceDiagram
    participant ALERT as Monitoring Alert
    participant RESIL as Resilience Manager
    participant CB as Circuit Breaker
    participant IR as Incident Response
    participant PLAY as DR Playbook
    participant NOTIFY as Regulatory Notification
    participant EXAM as Examiner Dashboard

    ALERT->>RESIL: Anomaly detected (e.g., HSM timeout)

    Note over RESIL,CB: Step 1: Circuit Breaker Evaluation
    RESIL->>CB: record_failure()
    alt failure_count >= threshold
        CB->>CB: state = OPEN (halt CDA operations)
        CB-->>RESIL: CIRCUIT OPEN
    else below threshold
        CB-->>RESIL: CIRCUIT CLOSED (continue)
    end

    Note over RESIL,IR: Step 2: Create Incident
    RESIL->>IR: create_and_respond(title, severity, type)
    IR->>IR: Assign incident_id
    IR->>IR: Determine severity (P1-P4)

    Note over IR,PLAY: Step 3: Execute Playbook
    IR->>PLAY: load_playbook(incident_type)
    PLAY-->>IR: {steps: [...], rto: "15min"}
    loop For each playbook step
        IR->>IR: Execute step
        IR->>IR: Log completion
    end
    IR-->>RESIL: Playbook complete

    Note over IR,NOTIFY: Step 4: Regulatory Notification (P1/P2 only)
    alt severity = P1 or P2
        IR->>NOTIFY: create_notification(NYDFS, 72h deadline)
        IR->>NOTIFY: create_notification(OCC, 72h deadline)
        NOTIFY-->>IR: {notification_ids}
    end

    Note over IR,EXAM: Step 5: Update Dashboard
    IR->>EXAM: log_incident(incident_details)
    EXAM-->>IR: {logged: true}
```

---

## 7. AML/OFAC Screening Flow (CDA Transactions)

```mermaid
sequenceDiagram
    participant TX as CDA Transaction Request
    participant COMPLY as Compliance Service
    participant AML as AML Screening Engine
    participant OFAC as OFAC Check - Chainalysis
    participant CTR as CTR Detection
    participant TRAVEL as Travel Rule
    participant AUDIT as Audit Log

    TX->>COMPLY: screen_cda_transaction(from, to, amount)

    Note over COMPLY,AML: Parallel Screening
    par OFAC Screening
        COMPLY->>AML: screen_address(from_address)
        AML->>OFAC: check_sanctions(address)
        alt OFAC Match
            OFAC-->>AML: {match: true, list: SDN}
            AML-->>COMPLY: BLOCKED (OFAC_MATCH)
            COMPLY->>AUDIT: log(OFAC_BLOCK, address)
            COMPLY-->>TX: REJECTED - CDA transfer blocked
        else Clean
            OFAC-->>AML: {match: false}
            AML-->>COMPLY: PASSED
        end
    and CTR Detection
        COMPLY->>CTR: check_ctr_threshold(amount)
        alt amount >= $10,000
            CTR-->>COMPLY: CTR_REQUIRED
            COMPLY->>AUDIT: log(CTR_FILED, amount)
        else
            CTR-->>COMPLY: No CTR needed
        end
    and Travel Rule
        COMPLY->>TRAVEL: check_threshold(amount)
        alt amount >= $3,000
            TRAVEL->>TRAVEL: hash_pii(originator, beneficiary)
            TRAVEL->>TRAVEL: notify_vasp(counterparty)
            TRAVEL-->>COMPLY: SUBMITTED
        else
            TRAVEL-->>COMPLY: NOT_REQUIRED
        end
    end

    COMPLY->>AUDIT: log(CDA_SCREENING_COMPLETE, results)
    COMPLY-->>TX: APPROVED (CDA transfer may proceed)
```

---

*ARB Submission -- End-to-End Transaction Flows*
*The Issuing Bank | Cari Network CDA Platform | ZKsync Prividium*
