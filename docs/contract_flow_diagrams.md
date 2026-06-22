# On-Chain Flow Diagrams

## CDA Mint Flow (DDA Deposit -> CDA Mint via Operator)

```mermaid
sequenceDiagram
    participant Depositor
    participant ZDIH as IBM Z DIH - MQ/REST Gateway
    participant Hogan as Hogan Mainframe - IBM Z - CIF/DDA
    participant Operator as Operator - the Issuing Bank Supply Controller
    participant Oracle as ReserveOracle
    participant Token as TokenizedDeposit - CDA on Prividium

    Depositor->>Hogan: Deposit USD to DDA (ACH/Fedwire/RTP/FedNow)
    Hogan->>Hogan: Credit DDA (CIF account), allocate to reserves
    Hogan->>Hogan: Post GL (Dr 1010 Reserve Cash, Cr 2010 CDA Liability)
    Hogan->>ZDIH: DDA credit notification (COBOL copybook)
    ZDIH->>Operator: Operator initiates CDA mint (DDA->CDA)

    Note over Operator,Token: Pre-mint checks

    Operator->>Token: mint(to, amount, refId)
    Token->>Token: Check: MINTER_ROLE (Operator)
    Token->>Token: Check: not paused
    Token->>Token: Check: to is whitelisted
    Token->>Token: Check: to is not frozen

    Token->>Oracle: canMint(totalSupply, amount)
    Oracle->>Oracle: Check: attestation not stale
    Oracle->>Oracle: Check: CDA supply + amount <= reserves
    Oracle-->>Token: true

    Token->>Token: _mint(to, amount)
    Token-->>Token: emit Mint(to, amount, refId)
    Token-->>Token: emit Transfer(0x0, to, amount)
    Token-->>Operator: CDA mint success
```

## CDA Burn Flow (CDA -> DDA Redemption at Par - GENIUS Act S5)

```mermaid
sequenceDiagram
    participant Holder
    participant API as the Issuing Bank API Gateway
    participant Operator as Operator - the Issuing Bank Supply Controller
    participant Token as TokenizedDeposit - CDA
    participant ZDIH as IBM Z DIH - MQ/REST Gateway
    participant Hogan as Hogan Mainframe - IBM Z - CIF/DDA

    Holder->>API: Redemption request (amount)
    API->>Operator: Operator initiates CDA burn (CDA->DDA)
    Operator->>Token: burn(from, amount, refId)
    Token->>Token: Check: BURNER_ROLE (Operator)
    Token->>Token: Check: not paused
    Token->>Token: _burn(from, amount)
    Token-->>Token: emit Burn(from, amount, refId)
    Token-->>Token: emit Transfer(from, 0x0, amount)
    Token-->>Operator: CDA burn success
    Operator->>ZDIH: Settlement instruction (JSON: refId, amount)
    ZDIH->>Hogan: DDA credit request (COBOL copybook)
    Hogan->>Holder: USD credited to DDA (T+0 settlement)
    Hogan->>Hogan: Post GL (Dr 2010 CDA Liability, Cr 1010 Reserve Cash)
    Hogan->>Hogan: Release reserves
```

## CDA Transfer with Travel Rule (FinCEN >= $3,000)

```mermaid
sequenceDiagram
    participant Sender
    participant App as the Issuing Bank Digital App
    participant Notabene as Travel Rule Service - Notabene
    participant Token as TokenizedDeposit - CDA

    Sender->>App: CDA Transfer request (to, $5,000)
    App->>App: Amount >= $3,000 threshold
    App->>Notabene: Submit originator/beneficiary PII
    Notabene-->>App: travelRuleHash (keccak256 of PII)

    App->>Token: transferWithTravelRule(to, amount, travelData)
    Token->>Token: Check: sender whitelisted & not frozen
    Token->>Token: Check: receiver whitelisted & not frozen
    Token->>Token: _transfer(sender, to, amount)
    Token-->>Token: emit Transfer(sender, to, amount)
    Token-->>Token: emit TravelRuleTransfer(sender, to, amount, origHash, beneHash)
    Token-->>App: true
```

## Cari Cross-Bank CDA Settlement via Messaging Bridge

```mermaid
sequenceDiagram
    participant Originator as Originator - the Issuing Bank
    participant Settlement as CariSettlement
    participant Token as TokenizedDeposit - the Issuing Bank CDA instance
    participant Bridge as Messaging Bridge - Cross-Bank Comms
    participant SBank as Settlement Bank
    participant DestBank as Destination Bank - Cari Member

    Note over Originator,DestBank: PHASE 1: Initiate CDA Transfer (Burn at Source)

    Originator->>Settlement: initiateSettlement(destBank, orig, bene, amt, travelHash)
    Settlement->>Settlement: Check: INITIATOR_ROLE
    Settlement->>Settlement: Check: destBank is registered Cari member
    Settlement->>Token: settlementBurn(originator, amount, settlementId)
    Token->>Token: Check: SETTLEMENT_ROLE
    Token->>Token: _burn(originator, amount) — CDA burned
    Token-->>Settlement: CDA burn confirmed
    Settlement-->>Settlement: emit SettlementInitiated(...)
    Settlement-->>Bridge: Settlement request via Messaging Bridge

    Note over Originator,DestBank: PHASE 2: Daily Net Settlement via Settlement Bank

    Bridge->>SBank: Queue transfer for daily net settlement
    SBank->>SBank: Net positions calculated at window close
    SBank->>Settlement: executeSettlement(settlementId)
    Settlement->>Settlement: Check: SETTLEMENT_BANK_ROLE
    Settlement->>Settlement: Check: not expired
    Settlement->>Token: settlementMint(beneficiary, amount, settlementId)
    Token->>Token: Check reserve backing
    Token->>Token: _mint(beneficiary, amount) — CDA minted at dest
    Settlement-->>Settlement: emit SettlementExecuted(...)
    SBank-->>DestBank: Net settlement confirmed

    Note over Originator,DestBank: ALTERNATIVE: Revert or Expire

    alt Settlement Reverted
        SBank->>Settlement: revertSettlement(sid, reason)
        Settlement->>Token: settlementMint(originator, amount, sid)
        Note right of Token: Originator gets CDA back
    else Settlement Expired
        Note over Settlement: After 24h expiry window
        Settlement->>Token: settlementMint(originator, amount, sid)
        Note right of Token: Originator gets CDA back
    end
```

## Daily Net Settlement Flow (Settlement Bank)

```mermaid
sequenceDiagram
    participant Banks as Cari Member Banks
    participant Bridge as Messaging Bridge
    participant SBank as Settlement Bank
    participant Contract as CariSettlement - Prividium
    participant ZDIH as IBM Z DIH - MQ/REST Gateway
    participant Hogan as Hogan Mainframe - IBM Z - CIF/DDA

    Note over Banks,Hogan: DAILY SETTLEMENT WINDOW

    SBank->>Contract: openSettlementWindow(windowId)
    Contract-->>Contract: emit SettlementWindowOpened(windowId, timestamp)

    Note over Banks,Hogan: Banks initiate CDA transfers during window

    loop Throughout settlement window
        Banks->>Bridge: Initiate CDA transfers
        Bridge->>SBank: Queue transfers for netting
        SBank->>SBank: Accumulate net positions
    end

    Note over Banks,Hogan: Window closes - Net positions calculated

    SBank->>Contract: closeSettlementWindow(windowId)
    Contract-->>Contract: emit SettlementWindowClosed(windowId, timestamp)

    SBank->>SBank: Calculate net CDA positions per bank
    SBank->>SBank: Calculate net DDA positions per bank

    Note over Banks,Hogan: Execute netSettle on-chain (CDA) + off-chain (DDA via Hogan)

    SBank->>Contract: netSettle(windowId, netPositions[])
    Contract->>Contract: For each net position: mint/burn CDA
    Contract-->>Contract: emit NetSettlementExecuted(windowId, positions[])

    SBank->>ZDIH: Execute DDA net settlements (JSON batch)
    ZDIH->>Hogan: Post GL entries (COBOL copybook)
    Hogan->>Hogan: Dr/Cr DDA accounts per net position
    Hogan->>Hogan: Post to GL (Post-2025 GL format, ISO 20022 aligned)
    Hogan-->>Banks: DDA balances adjusted via ACH/Fedwire/RTP/FedNow

    Note over Banks,Hogan: Dual-rail settlement complete
```

## Force Transfer (OFAC Seizure)

```mermaid
sequenceDiagram
    participant OFAC as OFAC/Court Order
    participant Compliance as Compliance Officer
    participant Token as TokenizedDeposit - CDA
    participant Escrow as the Issuing Bank Escrow Account

    OFAC->>Compliance: Seizure order for address X
    Compliance->>Token: freezeAddress(X)
    Token-->>Token: emit AddressFrozen(X)
    Note over Token: Address X can no longer transfer CDA

    Compliance->>Token: forceTransfer(X, escrow, balance, "OFAC order #123")
    Token->>Token: Check: COMPLIANCE_ROLE
    Token->>Token: Bypass whitelist/freeze checks
    Token->>Token: _transfer(X, escrow, balance)
    Token-->>Token: emit Transfer(X, escrow, balance)
    Token-->>Token: emit ForcedTransfer(X, escrow, balance, reason)
    Token-->>Compliance: Success

    Note over Escrow: CDA held pending legal resolution
```
