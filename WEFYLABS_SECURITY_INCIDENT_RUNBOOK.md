# WEFYLABS SECURITY INCIDENT RUNBOOK
# SecOps Incident Response, Containment & Forensic Runbook

---

## 1. Security Incident Response Lifecycle

Every confirmed or suspected security incident must follow this standardized operational lifecycle:
```
1. CONTAINMENT      -> Freeze compromised sessions, isolate tenant, or block attacking IPs
2. INVESTIGATION    -> Query SecOps event logs, audit logs, and correlation IDs
3. REVOCATION       -> Invalidate JWT secrets, revoke API keys, terminate sessions
4. ROTATION         -> Rotate database passwords, provider keys, and webhook secrets
5. EVIDENCE PRESERVE-> Capture immutable audit snapshots and database transaction logs
6. RESTORATION      -> Apply security patches, schema updates, or configuration hotfixes
7. VERIFICATION     -> Execute Part 17 security test suite (test_part17_security.py)
8. COMMUNICATION    -> Notify designated tenant administrators without exposing technical exploit detail
```

---

## 2. Playbook 1: Cross-Tenant Access Attempt (IDOR Alert)

### Trigger
- SecOps event logged: `TENANT_BOUNDARY_VIOLATION`.
- Log: `[IDOR Violation] Tenant mismatch for Entity: entity_org=X vs active_tenant=Y`.

### Action Procedure
1. **Immediate Containment**:
   - Suspend the offending broker account immediately:
     ```python
     # Set onboarding_status = "SUSPENDED" in database
     await db.execute(update(Broker).where(Broker.id == offender_id).values(onboarding_status="SUSPENDED"))
     await db.commit()
     ```
   - Suspended accounts are immediately rejected with 403 in `app/dependencies.py`.
2. **Forensic Audit**:
   - Query `audit_logs` table for all requests matching the user's `broker_id` or session IP over the last 48 hours.
   - Inspect whether any response returned 200 or if all were safely trapped with 403 Forbidden.
3. **Evidence Preservation**:
   - Export audit records for incident review.

---

## 3. Playbook 2: Suspected Credential / API Key Compromise

### Trigger
- API key found in public commit or unauthorized anomalous requests originating from unexpected IP addresses.

### Action Procedure
1. **Immediate Revocation**:
   - Navigate to Super Admin / API Keys controller (`/api/v1/api-keys/{id}`) or directly revoke via DB:
     ```python
     await db.execute(update(ApiKey).where(ApiKey.id == key_id).values(is_active=False, revoked_at=now))
     await db.commit()
     ```
2. **Key Rotation**:
   - Issue a new cryptographically random 32-character API key for the affected service.
3. **Log Audit**:
   - Verify with `get_recent_security_events()` whether unauthorized requests penetrated any protected routes.

---

## 4. Playbook 3: Malicious Webhook Attack / Forgery

### Trigger
- SecOps event logged: `INVALID_WEBHOOK`.
- Rate limiting alert on `RateLimitTier.WEBHOOK`.

### Action Procedure
1. **Verify Signature Rejection**:
   - Verify that all invalid webhook requests were rejected with HTTP 401/403 and never enqueued into `outbox_events` or processed by Celery.
2. **IP Rate Limiting**:
   - The multi-tier rate limiter automatically enforces `300 req/min` per IP.
   - If the attack is distributed, block the source IP subnet at cloud firewall / Cloudflare edge.
3. **Secret Rotation**:
   - If webhook secret was compromised, rotate `WHATSAPP_VERIFY_TOKEN` or `RAZORPAY_WEBHOOK_SECRET` in `.env` and restart backend.

---

## 5. Playbook 4: Prompt Injection Attack Spike

### Trigger
- SecOps event logged: `AI_POLICY_REJECTION`.
- Log: `Prompt injection pattern detected in lead submission and neutralized`.

### Action Procedure
1. **Verify Neutralization**:
   - `PublicCaptureGuard.sanitize_untrusted_text` automatically substitutes injected instructions with `[FILTERED_INSTRUCTION]`.
   - Confirm downstream AI responses were not manipulated.
2. **Update Pattern Dictionary**:
   - If new evasion techniques are discovered, add the regex pattern to `_INJECTION_PATTERNS` in `apps/api/app/modules/lead_acquisition/security/public_guard.py`.
3. **Run Security Test Suite**:
   ```bash
   python -m pytest apps/api/tests/test_part17_security.py -v
   ```

---
_Status: SECURITY INCIDENT RUNBOOK VERIFIED._
