# Tokenized Deposit Smart Contracts

Production-ready smart contracts for a **tokenized deposit platform** on **ZKsync Prividium** (Cari Network).

## Contracts

| Contract | Description | Proxy |
|----------|-------------|-------|
| **TokenizedDeposit** | Permissioned ERC-20 tokenized deposit (cUSD). FDIC-insured bank liability, 1:1 reserve backed. | UUPS |
| **ReserveOracle** | 1:1 reserve backing attestation oracle (GENIUS Act Section 4). Chainlink/Prividium-native hook. | UUPS |
| **CariSettlement** | Cross-bank settlement for Cari Network inter-bank transfers. Burn-at-source / mint-at-destination. | UUPS |
| **CariComplianceOracle** | On-chain KYC/AML/OFAC compliance registry (legacy, retained for compatibility). | UUPS |

### Interfaces

| Interface | Purpose |
|-----------|---------|
| `IReserveOracle` | Standard interface for reserve attestation oracles |
| `ICariSettlement` | Standard settlement interface for Cari cross-bank flows |
| `ITokenizedDeposit` | Token interface with Travel Rule, compliance, and settlement callbacks |

## Architecture

### Role-Based Access Control (RBAC)

```
DEFAULT_ADMIN_ROLE  (Consortium Timelock/multi-sig)
  ├── MINTER_ROLE         (HSM-backed, treasury ops)
  ├── BURNER_ROLE         (HSM-backed, redemption service)
  ├── COMPLIANCE_ROLE     (Compliance officer - whitelist/freeze/forceTransfer)
  ├── UPGRADER_ROLE       (Timelock-gated contract upgrades)
  ├── PAUSER_ROLE         (Emergency circuit breaker)
  ├── SETTLEMENT_ROLE     (CariSettlement contract only)
  └── ATTESTOR_ROLE       (HSM-backed reserve attestor, on ReserveOracle)
```

### Separation of Duties (SoD)

- **Minter** cannot attest reserves (different HSM keys)
- **Attestor** cannot mint tokens
- **Compliance** cannot mint/burn (only whitelist/freeze/forceTransfer)
- **Admin** is a Timelock controlled by multi-sig, not an EOA

## Quick Start

### Build

```bash
forge build
```

### Test

```bash
# Run all tests (unit + fuzz + invariant)
forge test

# Run only TokenizedDeposit tests
forge test --match-contract TokenizedDepositTest

# Run with verbose output
forge test -vvvv

# Run fuzz tests with more runs
forge test --match-contract FuzzTest --fuzz-runs 10000

# Run invariant tests
forge test --match-contract InvariantTest
```

### Deploy

```bash
# Set environment variables
export DEPLOYER_PRIVATE_KEY=0x...
export ZKSYNC_SEPOLIA_RPC=https://sepolia.era.zksync.dev

# Deploy to ZKsync Sepolia testnet
forge script deploy/DeployAll.s.sol:DeployAll \
    --rpc-url $ZKSYNC_SEPOLIA_RPC \
    --broadcast -vvvv

# Deploy to ZKsync Prividium mainnet
forge script deploy/DeployAll.s.sol:DeployAll \
    --rpc-url $PRIVIDIUM_RPC \
    --broadcast --verify -vvvv
```

### Post-Deployment (via consortium multi-sig)

1. `token.setCariSettlement(settlementAddress)`
2. `token.grantRole(MINTER_ROLE, minterHSMAddress)`
3. `token.grantRole(BURNER_ROLE, burnerHSMAddress)`
4. `token.grantRole(COMPLIANCE_ROLE, complianceAddress)`
5. `token.grantRole(PAUSER_ROLE, pauserAddress)`
6. `settlement.grantRole(SETTLEMENT_OPERATOR_ROLE, operatorAddress)`
7. `settlement.grantRole(INITIATOR_ROLE, initiatorAddress)`
8. `oracle.updateAttestation(initialReserves, reportHash)`

## Test Coverage

104 tests across 5 test suites:

| Suite | Tests | Type |
|-------|-------|------|
| TokenizedDepositTest | 50 | Unit |
| ReserveOracleTest | 20 | Unit |
| CariSettlementTest | 25 | Unit |
| FuzzTest | 7 | Fuzz (1024 runs each) |
| InvariantTest | 2 | Invariant (256 runs, 16384 calls) |

### Critical Invariants Tested

- `totalSupply <= totalReserves` (1:1 backing - GENIUS Act Section 4)
- `totalSupply == totalMinted - totalBurned` (supply accounting)
- Frozen accounts cannot transfer
- Non-whitelisted accounts cannot hold tokens
- Only authorized roles can mint/burn/freeze/upgrade
- Stale oracle attestations block minting

## Cari Network Integration

### Cross-Bank Settlement Flow

1. **Source bank** calls `settlement.initiateSettlement()` -- burns tokens from originator
2. **Cari validators** verify the burn event and Travel Rule data
3. **Settlement operator** calls `settlement.executeSettlement()` -- mints tokens to beneficiary
4. On failure: `settlement.revertSettlement()` re-mints to originator
5. On timeout: anyone calls `settlement.expireSettlement()` to unlock originator funds

### Member Bank Registry

Each Cari member bank is registered via `settlement.addMemberBank(bankAddress)`. Only registered banks can receive cross-bank settlements.

## Security Considerations

- All contracts use UUPS upgradeable proxy pattern
- ReentrancyGuard on all state-mutating external functions
- OpenZeppelin v5.6.1 battle-tested base contracts
- Custom errors for gas-efficient reverts
- Events on all state changes for examiner audit trail
- `forceTransfer` uses a controlled bypass flag (not public, not persistent)
- No external calls to untrusted contracts (no reentrancy surface)
