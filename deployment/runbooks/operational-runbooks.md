# Operational Runbook: API Outage

**Severity:** P1 (Critical)
**RTO:** 10 minutes
**Escalation:** Digital Assets Engineering -> SRE -> VP Engineering

---

## Detection

Alert: `CariAPIDown` (Prometheus)
- API health endpoint `/healthz` unreachable for > 1 minute
- PagerDuty notification to on-call engineer

## Immediate Actions (0-5 minutes)

### 1. Confirm the outage

```bash
# Check pod status
kubectl -n cari-prividium-mainnet get pods -l app=cari-platform

# Check recent events
kubectl -n cari-prividium-mainnet get events --sort-by=.metadata.creationTimestamp | tail -20

# Check API logs
kubectl -n cari-prividium-mainnet logs -l component=api --tail=100
```

### 2. Check dependencies

```bash
# PostgreSQL
kubectl -n cari-prividium-mainnet exec -it deploy/cari-api -- python -c "
import asyncio, asyncpg
asyncio.run(asyncpg.connect('$DATABASE_URL'))
print('DB OK')
"

# Redis
kubectl -n cari-prividium-mainnet exec -it deploy/cari-api -- python -c "
import redis; r = redis.from_url('$REDIS_URL'); r.ping(); print('Redis OK')
"

# Prividium RPC
kubectl -n cari-prividium-mainnet exec -it deploy/cari-api -- curl -s $PRIVIDIUM_RPC_URL
```

### 3. Restart pods (if dependency check passes)

```bash
kubectl -n cari-prividium-mainnet rollout restart deployment/cari-api
kubectl -n cari-prividium-mainnet rollout status deployment/cari-api --timeout=120s
```

## If restart fails (5-10 minutes)

### 4. Roll back to previous version

```bash
# Check rollout history
kubectl -n cari-prividium-mainnet rollout history deployment/cari-api

# Roll back
kubectl -n cari-prividium-mainnet rollout undo deployment/cari-api

# Or roll back to specific revision
kubectl -n cari-prividium-mainnet rollout undo deployment/cari-api --to-revision=N
```

### 5. Roll back Helm release

```bash
# List Helm history
helm -n cari-prividium-mainnet history cari-platform

# Roll back to previous release
helm -n cari-prividium-mainnet rollback cari-platform
```

## Post-Recovery

- [ ] Verify `/healthz` returns 200
- [ ] Verify reserve monitoring is active
- [ ] Check for any failed transactions during outage
- [ ] Run reconciliation to detect discrepancies
- [ ] File incident report
- [ ] If outage > 30 minutes: notify NYDFS (500.17 requirement)

---

# Operational Runbook: Reserve Breach

**Severity:** P1 (Critical) -- Regulatory
**RTO:** 5 minutes (pause operations), 30 minutes (full resolution)
**Escalation:** Treasury Operations -> Compliance -> Legal -> CISO

---

## Detection

Alert: `ReserveBackingBelowThreshold` (Prometheus)
- `cari_reserve_backing_ratio < 1.0`
- GENIUS Act Section 4 violation

## Immediate Actions (0-5 minutes)

### 1. PAUSE all minting immediately

```bash
# Via API
curl -X POST https://cari-api.mtbank.com/api/v1/admin/pause-minting \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Via smart contract (emergency -- requires PAUSER key)
# Coordinate with key holder for contract pause
```

### 2. Verify the breach

```bash
# Check current status
curl https://cari-api.mtbank.com/api/v1/reserves/status | jq .

# Expected output when breached:
# {
#   "backing_ratio": 0.98,
#   "status": "UNDER_BACKED",
#   "total_supply_usd": 50000000,
#   "total_reserves_usd": 49000000
# }
```

### 3. Identify the gap

```bash
# Check recent transactions for large burns without GL settlement
curl https://cari-api.mtbank.com/api/v1/compliance/audit?event_type=BURN_COMPLETED&limit=50

# Check core banking reserve balance
curl https://cari-api.mtbank.com/api/v1/reserves/components | jq .
```

## Resolution (5-30 minutes)

### 4. Restore backing

Options (in order of preference):
1. **Wire additional reserves** to backing account (Treasury Operations)
2. **Burn excess tokens** to reduce supply to match reserves (requires BURNER key)
3. **Both** -- add reserves AND burn to restore ratio above 1.02

### 5. Verify restoration

```bash
# Re-run attestation
curl -X POST https://cari-api.mtbank.com/api/v1/reserves/attest

# Verify ratio restored
curl https://cari-api.mtbank.com/api/v1/reserves/status | jq .backing_ratio
# Should be >= 1.0
```

### 6. Resume minting

```bash
curl -X POST https://cari-api.mtbank.com/api/v1/admin/resume-minting \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

## Post-Recovery

- [ ] File regulatory notification (OCC, NYDFS) within 72 hours
- [ ] Root cause analysis within 24 hours
- [ ] Update risk register with new residual scoring
- [ ] Review reserve monitoring frequency (consider increasing from 5min to 1min)
- [ ] Generate examiner report documenting breach and resolution

---

# Operational Runbook: Key Compromise

**Severity:** P1 (Critical) -- Security
**RTO:** 5 minutes (containment), 4 hours (full remediation)
**Escalation:** CISO -> Security Team -> Legal -> Regulatory

---

## Detection

- HSM anomaly alert
- Unauthorized transaction detected
- Vendor (Fireblocks) security notification

## Immediate Actions (0-5 minutes)

### 1. PAUSE the token contract

```bash
# Emergency pause -- contact PAUSER key holder immediately
# This halts ALL token transfers on-chain
```

### 2. Revoke the compromised key

```python
from security.key_management.hsm import KeyLifecycleManager
manager = KeyLifecycleManager()
manager.revoke_key(compromised_key_id, reason="SUSPECTED_COMPROMISE", actor="incident_responder")
```

### 3. Notify Fireblocks

```
Contact: Fireblocks Security Team
Phone: [Emergency hotline]
Email: security@fireblocks.com
Action: Request vault freeze for affected key
```

## Containment (5-60 minutes)

### 4. Audit all transactions signed by compromised key

```bash
curl https://cari-api.mtbank.com/api/v1/compliance/audit?key_id=$COMPROMISED_KEY_ID | jq .
```

### 5. Generate new key material

```python
manager = KeyLifecycleManager()
new_key = manager.generate_key(
    role=compromised_role,
    provider="azure_managed_hsm"
)
# Requires dual control approval for activation
```

### 6. Update smart contract authorized signers

```bash
# Deploy updated signer configuration via UPGRADER key
# Requires dual approval from ADMIN key holders
```

## Post-Recovery

- [ ] Resume contract operations after new key verified
- [ ] File NYDFS 500.17 notification (72h deadline)
- [ ] File SAR if unauthorized transactions occurred
- [ ] Engage forensic analysis (internal + external)
- [ ] Update incident response playbook with lessons learned
- [ ] Review all other key material for potential exposure
