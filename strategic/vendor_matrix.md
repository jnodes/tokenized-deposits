# Vendor Evaluation Matrix

**the Issuing Bank | Cari Network Tokenized Deposit Platform**
**Prepared for:** Architecture Review Board & Procurement
**Classification:** CONFIDENTIAL -- Internal Use Only

---

## 1. Evaluation Methodology

All vendors scored on a weighted 1-5 scale across six dimensions:

| Dimension | Weight | Description |
|-----------|--------|-------------|
| Regulatory Fit | 25% | GENIUS Act, NYDFS 500, BSA/AML/OFAC compliance readiness |
| Enterprise Readiness | 20% | SOC 2, SLAs, uptime guarantees, bank-grade support |
| Technical Capability | 20% | Feature completeness, API quality, integration effort |
| Cari Network Compatibility | 15% | ZKsync Prividium support, permissioned chain readiness |
| Cost Efficiency | 10% | TCO over 3-year horizon (pilot + production) |
| Strategic Alignment | 10% | the Issuing Bank roadmap fit, vendor stability, ecosystem presence |

**Scoring:** 5 = Best-in-class | 4 = Strong | 3 = Adequate | 2 = Gaps | 1 = Not recommended

---

## 2. Blockchain Infrastructure

### ZKsync Prividium (Selected -- Cari Network Standard)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Regulatory Fit | 5 | Permissioned L2 with privacy features; built for regulated institutions |
| Enterprise Readiness | 4 | Matter Labs enterprise support; SLA in negotiation |
| Technical Capability | 5 | zkRollup with EVM equivalence; Solidity/Foundry compatible |
| Cari Network Compatibility | 5 | **Native Cari Network infrastructure** -- no integration needed |
| Cost Efficiency | 4 | Gas costs amortized via L2 batching; ~$0.02/tx at scale |
| Strategic Alignment | 5 | the Issuing Bank founding partner commitment; the Head of Digital Assets public endorsement |
| **Weighted Score** | **4.75** | **SELECTED** |

### Alternatives Evaluated

| Vendor | Weighted Score | Disposition | Key Gap |
|--------|---------------|-------------|---------|
| Hyperledger Besu (private) | 3.4 | Not selected | No Cari Network support; separate chain |
| Polygon CDK | 3.6 | Not selected | Public chain heritage; regulatory uncertainty |
| R3 Corda | 3.2 | Not selected | Legacy architecture; limited DeFi composability |

---

## 3. Custody & Key Management

### Fireblocks (Recommended -- Primary)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Regulatory Fit | 5 | SOC 2 Type II; $30B+ institutional AUC; NY BitLicense ready |
| Enterprise Readiness | 5 | 99.98% uptime SLA; 24/7 dedicated support tier |
| Technical Capability | 5 | MPC-CMP with hardware isolation; policy engine; raw signing |
| Cari Network Compatibility | 4 | ZKsync support GA; Prividium custom network config needed |
| Cost Efficiency | 3 | Premium pricing ($50K+/yr base); per-tx fees at volume |
| Strategic Alignment | 5 | Used by 1,800+ institutions; BNY, Standard Chartered reference clients |
| **Weighted Score** | **4.60** | **RECOMMENDED** |

### Coinbase Prime (Secondary / Failover)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Regulatory Fit | 5 | NY BitLicense holder; SEC registered; SOC 2 Type II |
| Enterprise Readiness | 4 | Strong but less bank-specific than Fireblocks |
| Technical Capability | 4 | Good API; limited policy engine granularity |
| Cari Network Compatibility | 3 | EVM support; Prividium requires custom integration |
| Cost Efficiency | 4 | Competitive pricing; volume discounts |
| Strategic Alignment | 4 | Large institutional base; bank partnerships growing |
| **Weighted Score** | **4.15** | **SECONDARY** |

### Other Evaluated

| Vendor | Weighted Score | Disposition |
|--------|---------------|-------------|
| Anchorage Digital | 3.9 | Backup option; OCC-chartered |
| BitGo | 3.7 | Mature but acquisition uncertainty |
| Copper.co | 3.3 | EU-focused; limited US bank experience |

---

## 4. Compliance & Analytics

### Chainalysis KYT + Reactor (Recommended -- AML/OFAC)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Regulatory Fit | 5 | Used by OFAC, FinCEN, IRS-CI; gold standard for sanctions screening |
| Enterprise Readiness | 5 | Bank-grade SLAs; dedicated compliance team |
| Technical Capability | 5 | Real-time API screening; batch mode; risk scoring; attribution DB |
| Cari Network Compatibility | 4 | EVM chain support; Prividium requires custom chain config |
| Cost Efficiency | 3 | Premium pricing; per-address/per-tx model at volume |
| Strategic Alignment | 5 | the Issuing Bank existing relationship; regulatory examiner familiarity |
| **Weighted Score** | **4.55** | **RECOMMENDED** |

### Notabene (Recommended -- Travel Rule)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Regulatory Fit | 5 | Purpose-built for FinCEN Travel Rule; FATF compliant |
| Enterprise Readiness | 4 | Growing bank client base; SOC 2 in progress |
| Technical Capability | 5 | VASP directory; counterparty discovery; PII secure transfer |
| Cari Network Compatibility | 4 | Chain-agnostic; API-based integration |
| Cost Efficiency | 4 | Reasonable per-transfer pricing |
| Strategic Alignment | 4 | Market leader in Travel Rule compliance |
| **Weighted Score** | **4.45** | **RECOMMENDED** |

### Elliptic (Alternative -- AML)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Regulatory Fit | 4 | Strong but smaller regulatory footprint than Chainalysis |
| Enterprise Readiness | 4 | Good SLAs; fewer bank references |
| Technical Capability | 4 | Comparable screening; smaller attribution database |
| Cari Network Compatibility | 3 | EVM support; less custom chain flexibility |
| Cost Efficiency | 4 | More competitive pricing |
| Strategic Alignment | 3 | Secondary market position |
| **Weighted Score** | **3.80** | **ALTERNATIVE** |

---

## 5. Oracle & Attestation Services

### Chronicle Protocol (Recommended -- Reserve Attestation)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Regulatory Fit | 5 | Designed for regulated asset attestation; GENIUS Act S6 aligned |
| Enterprise Readiness | 4 | Emerging but purpose-built for institutional use |
| Technical Capability | 5 | On-chain attestation with cryptographic proof; push + pull models |
| Cari Network Compatibility | 4 | EVM compatible; ZKsync deployment supported |
| Cost Efficiency | 4 | Competitive; per-attestation pricing |
| Strategic Alignment | 4 | Aligned with tokenized deposit use case |
| **Weighted Score** | **4.45** | **RECOMMENDED** |

### Chainlink (Alternative)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Regulatory Fit | 3 | Public chain focused; less regulated-asset experience |
| Enterprise Readiness | 4 | Mature infrastructure; strong uptime |
| Technical Capability | 5 | Broad oracle network; Proof of Reserve product |
| Cari Network Compatibility | 3 | Public chain heritage; permissioned support unclear |
| Cost Efficiency | 3 | LINK token economics; gas overhead |
| Strategic Alignment | 3 | Less aligned with bank-specific needs |
| **Weighted Score** | **3.55** | **ALTERNATIVE** |

---

## 6. Recommended Vendor Stack Summary

| Layer | Primary Vendor | Secondary/Failover | Contract Model |
|-------|---------------|-------------------|----------------|
| Blockchain Infrastructure | ZKsync Prividium (Cari) | N/A (network standard) | Cari Network membership |
| Custody & Key Management | Fireblocks | Coinbase Prime | Enterprise license + per-tx |
| AML/OFAC Screening | Chainalysis KYT | Elliptic | Per-address + per-tx |
| Travel Rule | Notabene | Manual VASP (fallback) | Per-transfer |
| Reserve Attestation | Chronicle Protocol | Chainlink PoR | Per-attestation |
| Monitoring/Observability | Datadog / Grafana Cloud | PagerDuty (alerting) | Enterprise license |

### Estimated Annual Vendor Cost (Production)

| Vendor | Year 1 (Pilot) | Year 2 (Scale) | Year 3 (Production) |
|--------|----------------|----------------|---------------------|
| Fireblocks | $75K | $120K | $200K |
| Chainalysis KYT | $50K | $80K | $150K |
| Notabene | $25K | $40K | $60K |
| Chronicle Protocol | $15K | $30K | $50K |
| Monitoring/Observability | $20K | $40K | $60K |
| **Total** | **$185K** | **$310K** | **$520K** |

---

## 7. Procurement Next Steps

1. **Fireblocks** -- Initiate enterprise POC agreement; request Prividium custom network configuration
2. **Chainalysis** -- Extend existing the Issuing Bank relationship to cover Cari Network address monitoring
3. **Notabene** -- Execute pilot agreement for Travel Rule compliance on permissioned transfers
4. **Chronicle Protocol** -- Technical evaluation for on-chain reserve attestation integration
5. **Legal Review** -- All vendor contracts through the Issuing Bank Legal for data residency, liability, and regulatory examination access clauses

---

*Prepared by StableArch Council -- Strategic Advisory Agent*
*Document Version: 1.0 | Classification: CONFIDENTIAL*
