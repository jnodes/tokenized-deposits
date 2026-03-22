# Cari Network Whitepaper

## Overview

The Cari Network is a consortium-governed blockchain network designed for regulated financial institutions, built on ZKsync Prividium — a private, permissioned zkRollup Layer 2 solution. It enables instant, 24/7 settlement of tokenized bank deposits across member institutions with full regulatory compliance, FDIC insurance pass-through, and examiner transparency.

### Mission

Enable instant, 24/7 settlement of tokenized bank deposits across member institutions with full regulatory compliance, FDIC insurance pass-through, and examiner transparency.

### Founding Partners

- M&T Bank (founding partner) — led by Matt McAfee, Head of Digital Assets
- Additional founding members to be announced

---

## Cari Deposit Account (CDA)

The **Cari Deposit Account (CDA)** is the on-chain ERC-20 token representing a bank deposit liability. CDA serves as the on-chain mirror of a traditional Demand Deposit Account (DDA).

### CDA Token Characteristics

- **ERC-20 Compatible**: Standard token interface for interoperability
- **Bank Liability**: Each CDA token represents a $1.00 USD deposit liability on the issuing bank's balance sheet
- **1:1 Reserve Backing**: Fully backed by qualifying reserves (GENIUS Act compliant)
- **FDIC Pass-Through Insurance**: Deposit insurance passes through to the underlying DDA
- **Instant Settlement**: 24/7 real-time transfers within the Cari Network

### CDA Lifecycle

| Operation | Description | Rail |
|-----------|-------------|------|
| **Mint** | DDA → CDA: Customer deposits fiat into DDA, Operator mints equivalent CDA tokens | CDA Rail |
| **Burn** | CDA → DDA: Customer redeems CDA tokens, Operator burns tokens and credits fiat to DDA | CDA Rail |
| **Transfer** | CDA moves between addresses within the network | CDA Rail |
| **Settlement** | Interbank CDA transfers aggregated and netted via Settlement Bank | Both Rails |

---

## Operator Role

The **Operator** is the centralized entity (e.g., M&T Bank) that controls CDA supply for a member bank. Each member bank in the Cari Network has exactly one Operator.

### Operator Responsibilities

- **Mint CDA**: Create new CDA tokens when customers deposit fiat (DDA → CDA)
- **Burn CDA**: Destroy CDA tokens when customers redeem for fiat (CDA → DDA)
- **Compliance**: Ensure all minting/burning operations comply with AML/KYC requirements
- **Reconciliation**: Daily reconciliation between CDA balances and DDA ledger

### On-Chain Permissions

The Operator holds the following on-chain roles:

| Role | Permission | Smart Contract |
|------|------------|----------------|
| `MINTER_ROLE` | Authorized to mint new CDA tokens | MTokenizedDeposit |
| `BURNER_ROLE` | Authorized to burn CDA tokens | MTokenizedDeposit |
| `OPERATOR_ROLE` | Administrative operations | MTokenizedDeposit |

### One Operator Per Bank

- Each member bank designates exactly one Operator address
- Operator keys are secured via HSM (Hardware Security Module)
- Operator changes require consortium governance approval
- Multi-signature controls for high-value operations

---

## Settlement Bank

The **Settlement Bank** is a designated entity that operates daily net settlement cycles for interbank CDA transfers within the Cari Network.

### Settlement Bank Functions

1. **Open Settlement Windows**: Initiate daily settlement cycles (typically aligned with business days)
2. **Aggregate Transfers**: Collect all interbank CDA transfers during the settlement window
3. **Compute Net Positions**: Calculate net payable/receivable for each member bank
4. **Execute Settlement**: Process net settlement on-chain via CariSettlement contract

### On-Chain Permissions

| Role | Permission | Smart Contract |
|------|------------|----------------|
| `SETTLEMENT_OPERATOR_ROLE` | Open/close settlement windows | CariSettlement |
| `SETTLEMENT_BANK_ROLE` | Execute net settlement | CariSettlement |

---

## Daily Net Settlement

Rather than real-time gross settlement (RTGS), the Cari Network uses **daily net settlement** for interbank transfers, improving capital efficiency.

### How Daily Net Settlement Works

1. **Settlement Window Opens**: Settlement Bank opens a new settlement window (e.g., 6:00 AM ET)
2. **Transfer Aggregation**: All interbank CDA transfers during the window are recorded
3. **Window Closes**: Settlement Bank closes the window (e.g., 5:00 PM ET)
4. **Netting Calculation**: Net positions computed for each member bank
5. **Settlement Execution**: 
   - Net receivers: CDA minted to their Operator address
   - Net payers: CDA burned from their Operator address
6. **Invariant**: Sum of all net positions = 0

### Net Settlement Example

| Bank | Gross Outflows | Gross Inflows | Net Position | Settlement Action |
|------|----------------|---------------|--------------|-------------------|
| Bank A | $10M | $8M | -$2M (payer) | Burn 2M CDA |
| Bank B | $5M | $12M | +$7M (receiver) | Mint 7M CDA |
| Bank C | $15M | $10M | -$5M (payer) | Burn 5M CDA |
| **Total** | $30M | $30M | **$0** | — |

### Benefits of Net Settlement

- **Capital Efficiency**: Banks only need to fund net positions, not gross flows
- **Reduced On-Chain Operations**: Single mint/burn per bank per day vs. many individual transfers
- **Lower Gas Costs**: Batched operations reduce transaction fees
- **Operational Simplicity**: Aligned with traditional interbank settlement practices

---

## Messaging Bridge

The **Messaging Bridge** is the cross-bank communication layer for CDA transfers between Cari Network member institutions.

### Bridge Functions

- **Transfer Instructions**: Carry CDA transfer requests between member banks
- **Travel Rule Data**: Transmit required originator/beneficiary information for compliance
- **Settlement Messages**: Coordinate daily net settlement between member banks
- **Compliance Attestations**: Deliver zk-proof attestations for privacy-preserving KYC/AML verification

### Privacy-Preserving Communication

- Uses zero-knowledge proofs for inter-bank compliance verification
- Counterparty banks receive only necessary compliance attestations, not raw PII
- Supports selective disclosure for regulatory examinations

### Message Types

| Message Type | Description | Privacy Level |
|--------------|-------------|---------------|
| `TRANSFER_REQUEST` | Initiate cross-bank CDA transfer | Encrypted + zk-attested |
| `TRANSFER_CONFIRMATION` | Acknowledge receipt of CDA | Encrypted |
| `TRAVEL_RULE_DATA` | Originator/beneficiary compliance data | zk-attested |
| `SETTLEMENT_INSTRUCTION` | Net settlement instructions | Encrypted |

---

## Dual-Rail Architecture

The Cari Network operates on a **Dual-Rail Architecture** with parallel processing on two synchronized rails.

### CDA Rail (On-Chain)

- **Platform**: ZKsync Prividium L2
- **Operations**: CDA token mint, burn, transfer, settlement
- **Settlement**: zk-proofs anchored to Ethereum L1 for finality
- **Speed**: Near-instant (< 1 second L2 confirmation)

### DDA Rail (Off-Chain)

- **Platform**: Core banking systems (e.g., FIS, Fiserv, Jack Henry)
- **Operations**: Fiat deposit, withdrawal, ACH/wire/FedNow
- **Settlement**: Traditional payment rails (Fed, CHIPS, RTP)
- **Speed**: Same-day to T+1 depending on rail

### Rail Synchronization

| Event | CDA Rail Action | DDA Rail Action |
|-------|-----------------|-----------------|
| Customer Deposit | Mint CDA | Credit DDA |
| Customer Withdrawal | Burn CDA | Debit DDA |
| Interbank Transfer (Intra-Day) | Transfer CDA | No action |
| Daily Net Settlement | Net mint/burn | Fed funds transfer |

### Daily Reconciliation

- Reconciliation engine compares CDA supply vs. DDA ledger balance daily
- Discrepancies flagged for investigation
- Audit trail maintained for examiner review

---

## Rulebook

The **Cari Network Rulebook** is the consortium governance framework that binds all member institutions.

### Member Bank Obligations

- Maintain Operator keys in HSM custody
- Process customer redemptions within 1 business day
- Participate in daily net settlement cycles
- Comply with all applicable AML/KYC/Travel Rule requirements
- Submit to annual compliance audits

### Protocol Upgrades

- **Proposal**: Any member bank may propose protocol upgrades
- **Review Period**: 30-day review period for comments
- **Voting**: Supermajority (2/3) of member banks required for approval
- **Implementation**: 90-day implementation window after approval

### Dispute Resolution

- **Tier 1**: Direct negotiation between parties (5 business days)
- **Tier 2**: Mediation by Cari Network governance committee (15 business days)
- **Tier 3**: Binding arbitration under AAA Commercial Rules

### Data Sharing Standards

- Privacy-preserving KYC/AML data sharing via zk-proofs
- Shared sanctions screening (OFAC, UN, EU lists)
- Travel Rule compliance via Messaging Bridge
- No sharing of raw customer PII between banks

### Onboarding/Offboarding

**Onboarding Requirements:**
1. Regulated depository institution in good standing
2. Compliance attestation and audit
3. Technical readiness assessment
4. Governance committee approval (majority vote)
5. Operator key ceremony

**Offboarding Process:**
1. 90-day notice period
2. Wind-down of outstanding CDA positions
3. Settlement of net positions
4. Revocation of Operator permissions
5. Archive of transaction history

---

## Architecture

### Layer 2: ZKsync Prividium

- **Type**: Private permissioned zkRollup
- **Proof System**: zkSNARK-based validity proofs
- **EVM Compatibility**: Full zkEVM support (Solidity ^0.8.x)
- **Data Availability**: Validium mode for enterprise privacy
- **Access Control**: Whitelisted addresses only

### Settlement Layer: Ethereum L1

- **Finality**: zk-proofs posted to Ethereum for hard finality
- **Proof Posting**: ~15 minute intervals
- **Gas Efficiency**: Batched proofs for multiple L2 transactions

### Consensus: Permissioned Validators

- Validator set operated by Cari Network member institutions
- Validator changes require consortium governance approval
- HSM-backed validator keys
- Geographic distribution for resilience

### Privacy Model

- Transaction-level privacy for deposit holders
- Selective disclosure to regulators via zk-proof attestations
- Configurable privacy levels per transaction type
- Zero-knowledge proofs for inter-bank compliance verification

---

## Compliance Framework

### GENIUS Act Compliance (Sections 4-8)

| Section | Requirement | Implementation |
|---------|-------------|----------------|
| Section 4 | 1:1 Reserve Backing | ReserveOracle contract + daily attestation |
| Section 5 | Redemption at Par | Instant CDA → DDA via Operator |
| Section 6 | Monthly Attestation | Automated attestation pipeline |
| Section 7 | Disclosure Obligations | Examiner dashboard + public reports |
| Section 8 | Interoperability | Standard CDA interface + Messaging Bridge |

### BSA/AML/OFAC

- Real-time sanctions screening for all CDA operations
- Transaction monitoring with configurable risk thresholds
- Suspicious Activity Report (SAR) automation
- OFAC list synchronization (daily updates)

### Travel Rule

- Originator/beneficiary data collection for transfers > $3,000
- Privacy-preserving data transmission via Messaging Bridge
- Compliance attestations without raw PII exposure

### NYDFS Part 500

- Cybersecurity program requirements
- Risk assessment and penetration testing
- Incident response and notification
- Audit trail and logging requirements

### OCC/Federal Reserve Guidance

- Stablecoin activities guidance compliance
- Novel activities supervision framework
- Safety and soundness standards

---

## Smart Contract Architecture

### MTokenizedDeposit

The core CDA token contract implementing ERC-20 with compliance controls.

**Key Functions:**
- `mint(address to, uint256 amount)` — Operator mints CDA (requires MINTER_ROLE)
- `burn(address from, uint256 amount)` — Operator burns CDA (requires BURNER_ROLE)
- `transfer(address to, uint256 amount)` — Standard ERC-20 transfer with compliance checks
- `pause()` / `unpause()` — Emergency controls

**Compliance Hooks:**
- Pre-transfer compliance check via CariComplianceOracle
- Blacklist/whitelist enforcement
- Transfer limits and velocity controls

### CariSettlement

The interbank settlement contract managing daily net settlement cycles.

**Key Functions:**
- `openSettlementWindow()` — Settlement Bank opens new window
- `closeSettlementWindow()` — Settlement Bank closes window
- `recordTransfer(address from, address to, uint256 amount)` — Record interbank transfer
- `executeNetSettlement(address[] banks, int256[] netPositions)` — Execute net settlement

**Invariants:**
- Sum of all net positions must equal zero
- Only Settlement Bank can execute settlement
- Settlement window must be closed before execution

### ReserveOracle

The reserve attestation contract ensuring 1:1 backing.

**Key Functions:**
- `updateReserve(uint256 amount, bytes attestation)` — Update reserve amount
- `getReserve()` — Query current reserve
- `verifyBacking()` — Verify CDA supply <= reserve

**Data Sources:**
- Off-chain attestation from registered accounting firm
- Core banking system reserve balance
- Custody account balances

### CariComplianceOracle

The on-chain compliance verification contract.

**Key Functions:**
- `checkCompliance(address account)` — Verify account compliance status
- `updateSanctionsList(bytes32[] hashes)` — Update sanctions list
- `attestKYC(address account, bytes proof)` — zk-proof KYC attestation

---

## Interoperability

### Cross-Bank CDA Transfers

1. **Initiation**: Sender's bank initiates transfer via Messaging Bridge
2. **Compliance**: Both banks verify compliance via zk-attestations
3. **Execution**: CDA transferred on-chain
4. **Confirmation**: Receiver's bank acknowledges receipt

### Shared KYC/AML Registry

- Privacy-preserving registry of compliance attestations
- Banks share attestation status, not raw KYC data
- Reduces duplicate KYC burden for multi-bank customers

### Network-Level Coordination

- Standardized CDA token interface across all member banks
- Common settlement window timing
- Shared Messaging Bridge infrastructure
- Unified compliance oracle integration

---

## Governance

### Consortium Model

- **Membership**: Open to regulated depository institutions meeting requirements
- **Voting Rights**: One vote per member bank (equal weighting)
- **Governance Committee**: Elected representatives from member banks

### Voting Thresholds

| Decision Type | Required Threshold |
|---------------|-------------------|
| Protocol Upgrades | Supermajority (2/3) |
| New Member Admission | Majority (>50%) |
| Emergency Actions | Supermajority (2/3) |
| Rulebook Amendments | Supermajority (2/3) |
| Committee Elections | Plurality |

### Dispute Resolution Framework

- Structured escalation process (negotiation → mediation → arbitration)
- Governance committee serves as mediator
- Binding arbitration for unresolved disputes
- Appeal mechanism for material decisions

### Member Onboarding/Offboarding

- Clear criteria and process for new member admission
- Orderly wind-down procedures for departing members
- Protection of network integrity during transitions
- Preservation of transaction history and audit trails
