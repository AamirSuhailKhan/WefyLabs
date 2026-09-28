# WEFYLABS — SECURITY INCIDENT RESPONSE PLAYBOOK

**Document Reference:** SEC-RUN-001  
**Classification:** INTERNAL  
**Authority:** Chief Security Officer + SRE Lead  
**Last Updated:** 2026-09-27 (Master Build 11)  
**Status:** ACTIVE — PRODUCTION TRUTH  

---

## 1. INCIDENT SEVERITY MATRIX

| Severity | Target Containment | Target Resolution | Criteria / Triggers |
| :--- | :---: | :---: | :--- |
| **P0 (CRITICAL)** | **< 15 Minutes** | **< 2 Hours** | Active cross-tenant data leak, total auth compromise, root key leak, database exposure |
| **P1 (HIGH)** | **< 30 Minutes** | **< 4 Hours** | Repeated privilege escalation attempts, mass export abuse, provider credential compromise |
| **P2 (MEDIUM)** | **< 2 Hours** | **< 24 Hours** | Webhook signature flood, AI autonomy policy bypass attempt, brute-force rate limit trigger |
| **P3 (LOW)** | **< 8 Hours** | **< 72 Hours** | Suspicious single failed login, non-critical certificate expiry warning, minor bug |

---

## 2. THE 7-STAGE INCIDENT WORKFLOW

```text
DETECTED
   ↓
TRIAGED
   ↓
CONTAINED
   ↓
INVESTIGATING
   ↓
REMEDIATING
   ↓
RESOLVED
   ↓
POSTMORTEM
```

1. **DETECTED:** Automated alert fired by `SecurityEventService` or report submitted by engineer.
2. **TRIAGED:** On-call SRE / SecOps Lead verifies validity, scopes affected tenants, and assigns severity.
3. **CONTAINED:** Automated session invalidation, IP block, or secret rotation applied to halt active breach.
4. **INVESTIGATING:** Forensic analysis of append-only `AuditLog` and correlation IDs.
5. **REMEDIATING:** Patching code, rotating affected keys, repairing data integrity.
6. **RESOLVED:** Service restored to baseline; verification drills completed.
7. **POSTMORTEM:** Root cause analysis documented within 48 hours; preventative actions tracked.

---

## 3. INCIDENT PLAYBOOKS

### Playbook A: Stolen or Leaked API Key / Secret
1. Immediately invoke `/v1/security/secrets/rotate` with new key value.
2. Revoke compromised key on third-party provider console.
3. Query `audit_logs` for `action = 'api_key.use'` matching the compromise window.
4. Notify affected tenant administrators if unauthorized mutations occurred.

### Playbook B: Suspicious User / Compromised Session
1. Execute immediate JTI token blacklist entry for user.
2. Mark user `onboarding_status = 'SUSPENDED'` in `brokers` table.
3. Terminate active WebSocket and HTTP sessions across all worker nodes.
4. Require password reset + identity re-verification before reinstatement.

### Playbook C: Cross-Tenant Data Leak Alert
1. Immediately isolate affected tenant's traffic via ingress rate-limiter.
2. Trace request UUID through `CorrelationMiddleware` and `AuditLog`.
3. Verify database query parameterization and RLS filter boundaries.
4. Deploy hotfix and run `test_master_build_11_tenant_security.py` regression suite.
