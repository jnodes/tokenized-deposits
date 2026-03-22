# ARB Compliance Summary

## GENIUS Act Alignment

M&T Bank Cari Deposit Account (CDA) contracts on ZKsync Prividium / Cari Network.

**M&T Bank Technology Stack:**
- **Hogan mainframe** on IBM Z for core banking (CIF/DDA)
- **IBM Z Data Integration Hub (DIH)** as middleware between modern APIs and Hogan
- **Kafka** event bus (Confluent Platform, KRaft mode)
- **Azure AKS** for Kubernetes orchestration
- **Azure Container Registry (ACR)** for Docker images (mtbcari.azurecr.io)
- **Azure Managed HSM / Azure Key Vault** for key management
- **Post-2025 GL format** (ISO 20022 aligned) via Hogan GL subsystem
- **GL accounts**: 1010 Reserve Cash, 1015 Reserve T-Bills, 1020 Reserve Fed Deposits, 1510 Settlement Receivable, 2010 CDA Token Liability, 2510 Settlement Payable, 3010 CDA Fee Revenue, 4010 CDA Operating Expense
- **Payment rails**: ACH, Fedwire, RTP/FedNow via Hogan payment processing

### Section 4: Reserve Requirements -- COMPLIANT

| Requirement | Implementation | Contract |
|-------------|----------------|----------|
| 1:1 reserve backing | `ReserveOracle.canMint()` enforced on every CDA mint; reverts if `supply + mint > reserves` | `MTokenizedDeposit.mint()` -> `_checkReserveBacking()` |
| Qualifying assets (cash, T-bills, Fed deposits) | Off-chain attestation by registered accounting firm; hash stored on-chain | `ReserveOracle.updateAttestation()` |
| No rehypothecation | Reserves are segregated in M&T Bank custody; oracle attestation includes asset breakdown | Off-chain + `ReserveOracle.attestationHash` |
| Staleness protection | Attestations expire after `maxStaleness` (default 24h); stale attestation blocks all CDA minting | `ReserveOracle.canMint()` staleness check |

### Section 5: Redemption at Par -- COMPLIANT

| Requirement | Implementation | Contract |
|-------------|----------------|----------|
| Redemption at par (1:1 USD) | `burn()` destroys CDA tokens; off-chain settlement credits depositor's DDA at par | `MTokenizedDeposit.burn()` |
| Within 1 business day | Settlement reference ID links to core banking for T+0 processing | `referenceId` parameter on burn |
| No unreasonable fees | No on-chain fee mechanism; gas on Prividium is consortium-configured (no public gas market) | ZKsync Prividium gas model |

### Section 6: Monthly Reserve Attestation -- COMPLIANT

| Requirement | Implementation | Contract |
|-------------|----------------|----------|
| Monthly attestation by registered accounting firm | `updateAttestation()` stores hash of signed report; cadence enforced off-chain | `ReserveOracle.updateAttestation()` |
| Public disclosure | `attestationHash` readable on-chain; links to IPFS/Arweave stored report | `ReserveOracle.attestationHash()` |

### Section 7: Disclosure Obligations -- COMPLIANT

| Requirement | Implementation |
|-------------|----------------|
| Reserve composition | Included in attestation report (linked by `attestationHash`) |
| Redemption policies | Published by M&T Bank; referenced in token metadata |
| Risk factors | Part of ARB package and public disclosure |

### Section 8: Interoperability -- COMPLIANT

| Requirement | Implementation | Contract |
|-------------|----------------|----------|
| Cross-platform transferability | Cari Network settlement protocol via Messaging Bridge for inter-bank CDA transfers | `CariSettlement` |
| Standard token interface | ERC-20 compatible CDA with additional compliance hooks | `MTokenizedDeposit` (ERC20Upgradeable) |

## Cari Rulebook Compliance

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| Operator role for CDA supply control | `OPERATOR_ROLE` controls all CDA mint/burn operations | COMPLIANT |
| Settlement Bank for daily net settlement | `SETTLEMENT_BANK_ROLE` executes `netSettle()` at window close | COMPLIANT |
| Messaging Bridge integration | Cross-bank CDA transfers routed via Messaging Bridge | COMPLIANT |
| Dual-rail processing | Parallel CDA (on-chain) + DDA (off-chain fiat) settlement | COMPLIANT |
| Rulebook governance adherence | All operations comply with Cari consortium governance rules | COMPLIANT |

## BSA/AML/KYC Compliance

| Control | Implementation | Contract |
|---------|----------------|----------|
| KYC-gated access | Whitelist-only transfers; only verified addresses can hold CDA | `_whitelisted` mapping, `_update()` override |
| AML transaction monitoring | All CDA transfers emit `Transfer` events; off-chain monitoring by Chainalysis/TRM Labs | Standard ERC-20 events |
| SAR/CTR reporting | Off-chain reporting triggered by AML monitoring; on-chain audit trail via events | Events + off-chain |

## OFAC Sanctions Screening

| Control | Implementation | Contract |
|---------|----------------|----------|
| Real-time wallet screening | `CariComplianceOracle` stores OFAC screening results; CDA whitelist gated by screening | `CariComplianceOracle.isCompliant()` |
| SDN list enforcement | Addresses flagged by OFAC screening are frozen via `freezeAddress()` | `MTokenizedDeposit.freezeAddress()` |
| Seizure capability | `forceTransfer()` moves CDA from frozen address to escrow | `MTokenizedDeposit.forceTransfer()` |

## FinCEN Travel Rule

| Control | Implementation | Contract |
|---------|----------------|----------|
| Originator/beneficiary info (>= $3,000) | `transferWithTravelRule()` emits `TravelRuleTransfer` event with PII hashes | `MTokenizedDeposit.transferWithTravelRule()` |
| Configurable threshold | `travelRuleThreshold` adjustable by admin | `MTokenizedDeposit.setTravelRuleThreshold()` |
| Off-chain PII storage | Actual PII stored by Travel Rule service (Notabene); only hashes on-chain | `TravelRuleData` struct |

## NYDFS Part 500 Cybersecurity

| Control | Implementation |
|---------|----------------|
| Cybersecurity program | Covered by M&T Bank's existing Part 500 program |
| CISO designation | M&T Bank CISO oversees digital asset security |
| Penetration testing | Smart contract audits (minimum 2 independent firms) + infrastructure pen testing |
| Encryption | ZKsync Prividium provides transaction-level privacy via zk-proofs |
| Incident response | Pause capability (`pause()`) for immediate circuit breaker; `forceTransfer()` for seizure |
| Third-party vendor management | All vendors (Fireblocks, Chainalysis, etc.) subject to M&T vendor risk assessment |
| Key Management (GENIUS Act) | Azure Managed HSM (FIPS 140-2 Level 3) for all signing keys; keys never leave HSM boundary |
| Infrastructure | Azure AKS with RBAC, Azure Key Vault audit logging, ACR image scanning |

## Examiner Transparency

| Capability | Implementation |
|------------|----------------|
| On-chain audit trail | All CDA state changes emit indexed events (mint, burn, transfer, freeze, forceTransfer) |
| Reserve proof | `ReserveOracle` stores attestation hash and timestamp; full report accessible via IPFS/Arweave |
| Compliance records | `CariComplianceOracle` stores KYC status, risk level, screening timestamps per address |
| Role audit | OpenZeppelin AccessControl provides `getRoleAdmin()`, `hasRole()`, role grant/revoke events |
| Settlement history | CariSettlement stores full CDA settlement records queryable by ID |
| Hogan GL source of truth | Off-chain DDA records maintained in Hogan GL subsystem (post-2025 GL format) |
| IBM Z DIH audit trail | All API-to-Hogan message flows logged for examiner review |
| Azure Monitor | Production observability via Azure Monitor, Log Analytics, and Application Insights |

## ZKsync Prividium Privacy

| Feature | Implementation |
|---------|----------------|
| Transaction privacy | ZKsync Prividium private execution environment; CDA transaction data not publicly visible |
| Selective disclosure | Examiner nodes can access full CDA transaction data; zk-proofs for external verification |
| Privacy-preserving compliance | Compliance checks happen on-chain within Prividium; only hashes exposed externally |

## Contract Security Summary

| Security Measure | Status |
|------------------|--------|
| UUPS upgradeable proxy | Implemented (Timelock-gated UPGRADER_ROLE) |
| ReentrancyGuard | Implemented on all state-mutating externals |
| OpenZeppelin v5.6.1 base contracts | Used for ERC20, AccessControl, Pausable, UUPS |
| Custom errors (gas-efficient) | Implemented for all revert conditions |
| Events on all state changes | Implemented for examiner audit trail |
| No external calls to untrusted contracts | Verified (no reentrancy surface) |
| Foundry test suite | 104 tests (unit + fuzz + invariant) -- all passing |
| Formal verification | Recommended pre-mainnet (Certora) |
| Independent audits | Required: minimum 2 firms (e.g., OpenZeppelin + Trail of Bits) |
