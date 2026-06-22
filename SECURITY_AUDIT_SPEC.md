# Security Audit Specification

**The Issuing Bank Tokenized Deposit Platform | Cari Network | ZKsync Prividium**

**Audit Date:** March 2026  
**Audit Scope:** Smart Contracts, Off-Chain APIs, Security Controls, Regulatory Compliance

---

## 1. Executive Summary

This specification documents the security audit scope for the Issuing Bank's tokenized deposit platform. The platform enables 1:1 USD-backed tokenized deposits on the Cari Network (ZKsync Prividium private permissioned zkRollup L2).

### 1.1 Platform Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          CLIENTS                                         │
│         Institutional Clients | Cari Member Banks | Regulators          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    OFF-CHAIN ORCHESTRATION (Quest 2)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ FastAPI      │  │ Compliance   │  │ Core Banking │  │ Custody     │ │
│  │ Routers      │  │ Services     │  │ Adapters     │  │ Adapters    │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SECURITY & COMPLIANCE (Quest 3)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ HSM Key      │  │ Signing      │  │ AML/OFAC     │  │ Travel Rule │ │
│  │ Management   │  │ Policy Engine│  │ Screening    │  │ Engine      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    SMART CONTRACTS (Quest 1)                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ │
│  │ MTokenized   │  │ ReserveOracle│  │ CariSettlement│ │ Compliance  │ │
│  │ Deposit      │  │              │  │              │  │ Oracle      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘ │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    ZKSYNC PRIVIDIUM L2                                   │
│              Private Permissioned zkRollup                               │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Inventory

### 2.1 Smart Contracts (Solidity 0.8.20-0.8.26)

| Contract | Path | Lines | Purpose | Security Features |
|----------|------|-------|---------|-------------------|
| TokenizedDeposit | `contracts/TokenizedDeposit.sol` | 434 | Main ERC-20 tokenized deposit | UUPS, AccessControl, Pausable, ReentrancyGuard |
| TokenizedDeposit | `contracts/TokenizedDeposit.sol` | 182 | Simplified token (legacy) | UUPS, AccessControl, Pausable |
| CariSettlement | `contracts/CariSettlement.sol` | 293 | Cross-bank settlement | UUPS, AccessControl, Pausable, ReentrancyGuard |
| ReserveOracle | `contracts/ReserveOracle.sol` | 165 | 1:1 reserve attestation | UUPS, AccessControl, Pausable |
| CariComplianceOracle | `contracts/CariComplianceOracle.sol` | 123 | KYC/AML status oracle | UUPS, AccessControl |

### 2.2 Off-Chain Services (Python 3.12+)

| Service | Path | Purpose | Security Concerns |
|---------|------|---------|-------------------|
| FastAPI App | `offchain/main.py` | API orchestration | CORS, authentication |
| Transactions Router | `offchain/routers/transactions.py` | Mint/burn operations | Parameter validation, authorization |
| Settlement Router | `offchain/routers/settlement.py` | Cross-bank settlement | Replay attacks, authorization |
| Compliance Router | `offchain/routers/compliance.py` | Screening endpoints | PII exposure |
| Compliance Service | `offchain/services/compliance.py` | BSA/AML/OFAC logic | False negatives, bypass |
| Blockchain Service | `offchain/services/blockchain.py` | On-chain interactions | Key exposure, replay |

### 2.3 Security Layer

| Component | Path | Purpose | Security Concerns |
|-----------|------|---------|-------------------|
| HSM Key Management | `security/key_management/hsm.py` | Key lifecycle | Key exposure, unauthorized access |
| Signing Policy Engine | `security/signing/policy_engine.py` | Dual control, approvals | Bypass, self-approval |
| Wallet Tiering | `security/wallet_tiering/strategy.py` | Hot/warm/cold strategy | Key compromise |
| Resilience Manager | `security/resilience/dr_manager.py` | Circuit breakers, DR | DoS, cascade failures |

### 2.4 Compliance Layer

| Component | Path | Purpose | Regulatory Requirement |
|-----------|------|---------|------------------------|
| AML Screening Engine | `compliance/aml_screening/engine.py` | OFAC/sanctions screening | BSA/AML, GENIUS Act |
| Travel Rule Engine | `compliance/travel_rule/engine.py` | FinCEN Travel Rule | 31 CFR 1010.410 |
| Reserve Proof Engine | `compliance/reserve_proof/engine.py` | 1:1 attestation | GENIUS Act S4, S6 |
| Examiner Dashboard | `compliance/examiner_dashboard/engine.py` | Regulatory reporting | OCC/Fed/NYDFS |

---

## 3. Banking Workflows

### 3.1 Mint Flow (Deposit → Token)

```
Client Request → Compliance Screen → Core Banking Verify → Reserve Check → On-Chain Mint → GL Entry
```

**Security Checkpoints:**
1. Address screened against OFAC SDN list
2. Deposit verified in core banking (FIS/Symcor)
3. Reserve backing verified via ReserveOracle.canMint()
4. Whitelist status checked on-chain
5. Frozen status checked on-chain
6. HSM-backed signing for on-chain transaction

**Files:**
- `contracts/TokenizedDeposit.sol:165-180` (mint function)
- `offchain/routers/transactions.py:42-173` (API endpoint)

### 3.2 Burn Flow (Redemption)

```
Client Request → Compliance Screen → On-Chain Burn → GL Entry → Fiat Payout
```

**Security Checkpoints:**
1. Address screened (blocked addresses rejected)
2. Balance sufficient check
3. HSM-backed signing
4. Double-entry GL posting
5. Fiat payout via ACH/Fedwire/RTP

**Files:**
- `contracts/TokenizedDeposit.sol:189-197` (burn function)
- `offchain/routers/transactions.py:176-285` (API endpoint)

### 3.3 Transfer Flow

```
Transfer Request → Whitelist Check → Freeze Check → On-Chain Transfer → Travel Rule (if >= $3K)
```

**Security Checkpoints:**
1. Sender whitelisted and not frozen
2. Receiver whitelisted and not frozen
3. Travel Rule metadata for >= $3,000
4. PII hashed before on-chain storage

**Files:**
- `contracts/TokenizedDeposit.sol:394-412` (_update override)
- `contracts/TokenizedDeposit.sol:214-228` (transferWithTravelRule)

### 3.4 Settlement Flow (Cross-Bank)

```
Initiate → Burn at Source → Validator Verification → Mint at Destination
```

**Security Checkpoints:**
1. Destination bank is registered member
2. Tokens burned at source before mint
3. Settlement expiry prevents indefinite lock
4. Revert path for failed settlements

**Files:**
- `contracts/CariSettlement.sol:147-194` (initiateSettlement)
- `contracts/CariSettlement.sol:197-216` (executeSettlement)

---

## 4. Regulatory Compliance Mapping

### 4.1 GENIUS Act (S4-S8)

| Section | Requirement | Implementation | Control ID |
|---------|-------------|----------------|------------|
| S4 | 1:1 Reserve Backing | ReserveOracle.canMint() | CTRL-GENIUS-S4 |
| S5 | Par Redemption | TokenizedDeposit.burn() at 1:1 | CTRL-GENIUS-S5 |
| S6 | Monthly Attestation | Oracle staleness (24h), ReserveProofEngine | CTRL-GENIUS-S6 |
| S7 | Public Disclosure | Examiner dashboard | CTRL-GENIUS-S7 |
| S8 | Interoperability | CariSettlement cross-bank protocol | CTRL-GENIUS-S8 |

### 4.2 NYDFS 23 NYCRR 500

| Section | Requirement | Implementation | Control ID |
|---------|-------------|----------------|------------|
| 500.07 | Access Privileges | 8 segregated key roles, RBAC | CTRL-NYDFS-500.07 |
| 500.15 | Encryption | HSM-backed keys, TLS 1.3 | CTRL-NYDFS-500.15 |
| 500.17 | Incident Response | DR playbooks, auto-notification | CTRL-NYDFS-500.17 |

### 4.3 BSA/AML/OFAC

| Requirement | Implementation | Control ID |
|-------------|----------------|------------|
| OFAC Screening | AMLScreeningEngine real-time | CTRL-BSA-OFAC |
| CTR Reporting | $10,000 threshold detection | CTRL-BSA-CTR |
| SAR Detection | Structuring, velocity patterns | CTRL-BSA-SAR |
| Travel Rule | $3,000 threshold, PII hashing | CTRL-FINCEN-TR |

### 4.4 OWASP Top 10 Mapping

| OWASP Category | Applicable Components | Mitigation |
|----------------|----------------------|------------|
| A01:2021 - Broken Access Control | Smart contracts, API endpoints | Role-based access, modifiers |
| A02:2021 - Cryptographic Failures | HSM, key storage | FIPS 140-2 Level 3 HSM |
| A03:2021 - Injection | API parameters, reference IDs | Pydantic validation, Solidity type safety |
| A04:2021 - Insecure Design | Settlement flow, upgrade pattern | ReentrancyGuard, time-locks |
| A05:2021 - Security Misconfiguration | CORS, debug mode | Environment-based config |
| A07:2021 - Identification and Authentication Failures | Signing policy, role assignment | Dual control, self-approval prevention |

### 4.5 PCI-DSS Mapping

| Requirement | Implementation | Status |
|-------------|----------------|--------|
| 3.4 - Cryptographic storage | HSM key storage, SHA-256 hashing | Implemented |
| 6.5 - Secure coding | ReentrancyGuard, access control | Implemented |
| 6.6 - Security reviews | This audit | In Progress |
| 10.2 - Audit logs | All operations logged | Implemented |
| 11.3 - Penetration testing | Required annually | Pending |

---

## 5. Ethereum Security Patterns

### 5.1 Reentrancy Protection

**Pattern:** `nonReentrant` modifier from OpenZeppelin ReentrancyGuard

**Protected Functions:**
- `TokenizedDeposit.mint()` (L169)
- `TokenizedDeposit.burn()` (L193)
- `TokenizedDeposit.transferWithTravelRule()` (L218)
- `TokenizedDeposit.forceTransfer()` (L283)
- `TokenizedDeposit.settlementMint()` (L308)
- `TokenizedDeposit.settlementBurn()` (L329)
- `CariSettlement.initiateSettlement()` (L158)
- `CariSettlement.executeSettlement()` (L199)
- `CariSettlement.revertSettlement()` (L222)
- `CariSettlement.expireSettlement()` (L241)

### 5.2 Access Control

**Pattern:** OpenZeppelin AccessControlUpgradeable with role-based modifiers

**Roles Defined:**
| Role | Contract | Purpose |
|------|----------|---------|
| DEFAULT_ADMIN_ROLE | All | Role management |
| MINTER_ROLE | TokenizedDeposit | Mint tokens |
| BURNER_ROLE | TokenizedDeposit | Burn tokens |
| COMPLIANCE_ROLE | TokenizedDeposit | Whitelist/freeze/force-transfer |
| UPGRADER_ROLE | All UUPS | Authorize upgrades |
| PAUSER_ROLE | All Pausable | Emergency pause |
| SETTLEMENT_ROLE | TokenizedDeposit | Settlement callbacks |
| ATTESTOR_ROLE | ReserveOracle | Update attestations |
| SETTLEMENT_OPERATOR_ROLE | CariSettlement | Execute/revert settlements |
| INITIATOR_ROLE | CariSettlement | Initiate settlements |
| ORACLE_UPDATER_ROLE | CariComplianceOracle | Update compliance records |

### 5.3 Upgrade Security (UUPS)

**Pattern:** UUPS proxy pattern with `_authorizeUpgrade` hook

**Security Measures:**
1. Constructor disables initializers on implementation
2. `_authorizeUpgrade` restricted to UPGRADER_ROLE
3. Only proxy can call initialize
4. Storage layout must be preserved

### 5.4 Pause Mechanism

**Pattern:** OpenZeppelin PausableUpgradeable with `whenNotPaused` modifier

**Protected Operations:**
- All mint/burn operations
- All transfers (via _update override)
- Settlement operations

---

## 6. Key Management Security

### 6.1 HSM Integration

**Providers Supported:**
- AWS CloudHSM
- Azure Key Vault
- Fireblocks MPC
- Local dev stub (NOT for production)

**Key Roles (Segregated):**
| Role | Purpose | Approval Quorum |
|------|---------|-----------------|
| MINTER | Mint tokenized deposits | 1 (low), 2 (medium+), 3 (critical) |
| BURNER | Burn for redemption | Same as MINTER |
| ATTESTOR | Reserve attestations | 2 |
| COMPLIANCE | Whitelist/freeze/seize | 2 |
| SETTLEMENT | Cross-bank operations | 2 |
| PAUSER | Emergency pause | 1 (HIGH risk tier) |
| UPGRADER | Contract upgrades | 2 (HIGH risk tier) |
| ADMIN | Role management | 2 |

### 6.2 Signing Policy Engine

**Risk Tiers:**
| Tier | Amount Range | Approvals Required | Time-Lock |
|------|--------------|-------------------|-----------|
| LOW | < $10,000 | 1 | None |
| MEDIUM | $10,000 - $1M | 2 | None |
| HIGH | $1M - $10M | 2 | 1 hour |
| CRITICAL | > $10M | 3 | 24 hours |

**Critical Operations (Always HIGH):**
- PAUSE
- UPGRADE
- KEY_ROTATION

**Protections:**
- Self-approval blocked (requestor != approver)
- Duplicate approval blocked
- Time-lock enforcement before execution

---

## 7. Audit Test Matrix

### 7.1 Smart Contract Tests

| Test ID | Description | Severity | Status |
|---------|-------------|----------|--------|
| SC-001 | Reentrancy on mint | Critical | Pending |
| SC-002 | Reentrancy on settlement | Critical | Pending |
| SC-003 | Role escalation via DEFAULT_ADMIN | Critical | Pending |
| SC-004 | UUPS upgrade authorization bypass | Critical | Pending |
| SC-005 | Initialization front-running | High | Pending |
| SC-006 | Reserve oracle manipulation | High | Pending |
| SC-007 | Whitelist bypass via _update | High | Pending |
| SC-008 | Force transfer flag abuse | High | Pending |
| SC-009 | Settlement expiry DoS | Medium | Pending |
| SC-010 | Integer overflow in canMint | Medium | Pending |

### 7.2 API Security Tests

| Test ID | Description | Severity | Status |
|---------|-------------|----------|--------|
| API-001 | Unauthorized mint access | Critical | Pending |
| API-002 | IDOR in account access | High | Pending |
| API-003 | Amount parameter tampering | High | Pending |
| API-004 | Reference ID injection | Medium | Pending |
| API-005 | Travel Rule threshold bypass | High | Pending |
| API-006 | Settlement ID enumeration | Medium | Pending |
| API-007 | CORS misconfiguration | Medium | Pending |
| API-008 | Debug mode in production | Medium | Pending |

### 7.3 Compliance Tests

| Test ID | Description | Severity | Status |
|---------|-------------|----------|--------|
| CMP-001 | OFAC bypass via address variation | Critical | Pending |
| CMP-002 | PII in plaintext on-chain | Critical | Pending |
| CMP-003 | Structuring detection gap | High | Pending |
| CMP-004 | Velocity anomaly detection gap | High | Pending |
| CMP-005 | CTR threshold incorrect | High | Pending |
| CMP-006 | Travel Rule threshold bypass | High | Pending |
| CMP-007 | Private key in config | Critical | Pending |
| CMP-008 | Stub HSM in production | Critical | Pending |

---

## 8. Risk Register

| Risk ID | Description | Inherent Risk | Mitigation | Residual Risk |
|---------|-------------|---------------|------------|---------------|
| R-001 | Smart contract bug | High | Audits, fuzz tests, formal verification | Medium |
| R-002 | Key compromise | Critical | HSM, dual control, rotation | Medium |
| R-003 | Oracle manipulation | High | Staleness check, multi-source | Medium |
| R-004 | OFAC false negative | High | Real-time screening, batch re-screen | Medium |
| R-005 | Upgrade vulnerability | Critical | Time-lock, multi-sig, audits | Medium |
| R-006 | Settlement failure | Medium | Revert path, expiry mechanism | Low |
| R-007 | DoS attack | Medium | Rate limiting, circuit breakers | Low |
| R-008 | Data breach | High | Encryption, access control, audit | Medium |

---

## 9. Appendix

### A. File Checksums

To be generated during audit execution.

### B. Tool Versions

- Solidity: 0.8.20 - 0.8.26
- Foundry: Latest
- OpenZeppelin Contracts: 5.x
- Python: 3.12+
- FastAPI: Latest
- Pydantic: v2

### C. References

- GENIUS Act (S. 6071 / H.R. 4766)
- NYDFS 23 NYCRR 500
- FinCEN Travel Rule (31 CFR 1010.410)
- OWASP Top 10 2021
- SWC Registry (Smart Contract Weakness Classification)
- OpenZeppelin Contracts Documentation

---

*This specification is confidential and intended for security audit purposes only.*
