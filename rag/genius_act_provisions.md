# GENIUS Act - Key Provisions Reference (Stub)

## Full Title
Guiding and Establishing National Innovation for U.S. Stablecoins Act (GENIUS Act)

## Purpose
Establishes a federal regulatory framework for payment stablecoins issued by banks and
non-bank entities in the United States.

## Key Sections Relevant to the Issuing Bank / Cari Network

### Section 4: Reserve Requirements
- **1:1 Reserve Backing**: Every payment stablecoin must be backed 1:1 by qualifying reserves.
- **Qualifying Reserves**:
  - U.S. dollars (cash)
  - Short-term U.S. Treasury bills (maturity <= 93 days)
  - Deposits at Federal Reserve Banks
  - Reverse repurchase agreements backed by U.S. Treasuries
- **No Rehypothecation**: Reserve assets cannot be pledged, lent, or otherwise rehypothecated.
- **Segregation**: Reserves must be held in segregated accounts.

### Section 5: Redemption Rights
- **Redemption at Par**: Holders must be able to redeem stablecoins at par value (1:1 with USD).
- **Redemption Timeline**: Within 1 business day of redemption request.
- **No Fees**: Redemption cannot be subject to unreasonable fees or conditions.

### Section 6: Reserve Attestation
- **Monthly Attestation**: Monthly attestation of reserve composition by a registered public
  accounting firm.
- **Public Disclosure**: Attestation results must be publicly available.
- **Standards**: Attestation must follow AICPA or equivalent standards.

### Section 7: Disclosure Obligations
- **Reserve Composition**: Regular disclosure of reserve asset types and amounts.
- **Redemption Policies**: Clear disclosure of redemption procedures and timelines.
- **Risk Factors**: Disclosure of material risks to stablecoin holders.
- **Governance**: Disclosure of issuer governance structure and key personnel.

### Section 8: Interoperability
- **Permitted Payment Stablecoins**: Must meet interoperability standards for use in payment systems.
- **Technical Standards**: Compliance with applicable technical interoperability standards.
- **Cross-Platform**: Stablecoins should be transferable across compliant platforms.

## Bank Issuer Provisions
- Insured depository institutions (like the Issuing Bank) may issue payment stablecoins under
  existing bank charter authority.
- Federal banking regulators (OCC, Fed, FDIC) serve as primary regulators.
- FDIC insurance considerations for bank-issued tokenized deposits.
- State-chartered banks subject to state regulator oversight (e.g., NYDFS for NY-chartered).

## Applicability to the Issuing Bank / Cari Network
- the Issuing Bank, as an insured depository institution, issues Cari Deposit Accounts (CDA) — on-chain
  ERC-20 tokens representing bank deposit liabilities (not stablecoins per se, but subject to
  similar reserve and redemption standards).
- CDA tokens as bank liabilities: FDIC-insured, 1:1 backed, redeemable at par.
- **Operator Role**: the Issuing Bank operates as the Operator for its CDA tokens, holding MINTER_ROLE
  and BURNER_ROLE on-chain to control CDA supply. Mint = DDA→CDA, Burn = CDA→DDA.
- **Daily Net Settlement**: Interbank CDA transfers are aggregated within a settlement window
  and netted via the Settlement Bank. Net receivers get CDA minted, net payers get CDA burned.
- Cari Network interoperability must meet Section 8 standards.
- ZKsync Prividium infrastructure must support attestation and disclosure requirements.
