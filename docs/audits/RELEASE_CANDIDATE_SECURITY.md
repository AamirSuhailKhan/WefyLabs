# WEFYLABS AUTONOMOUS REVENUE OS — SECURITY & OUTBOUND SAFEGUARDS AUDIT

**Audit Date**: 2026-10-28T13:00:00+05:30  
**Repository**: WefyLabs / BeetleLabs AI Real Estate CRM  
**Target Branch**: `level-3`  
**Current HEAD Commit**: `0383020a865fe315adfda4549f536a594fb10454`  
**Auditor**: Senior Application Security Engineer & QA Lead  
**Deliverable**: Stage D — Security and Outbound-Action Safeguards

---

## 1. Executive Summary

This security audit inspects and evaluates the tenant isolation architecture, authentication mechanisms, authorization boundaries, background task execution contexts, outbound messaging safeguards, and residual credential exposure risks within the WefyLabs Autonomous Revenue OS.

All security tests passed 100%. Cross-tenant data leakage is prevented via strict database-level filtering, explicit context token scoping, and fail-closed tenant resolution. Outbound communications are confirmed **strictly inert** in the effective runtime configuration (`FOLLOWUP_HUB_DISPATCH_ENABLED=false`).

---

## 2. Multi-Tenant Isolation & Authorization

### 2.1 Request Lifecycle & Tenant Context Resolution
The application implements strict contextual tenant isolation via Python's `contextvars` (`current_tenant_ctx` in `app/dependencies.py`):
1. **Authentication Gate**: All non-public API endpoints require a valid Supabase JWT Bearer token validated via `get_current_broker`. Unauthenticated requests are rejected immediately with HTTP 401/403.
2. **Organization Context Gating**:
   - For single-organization brokers: The broker's authorized organization is automatically bound.
   - For multi-organization brokers: The client must supply `X-WefyLabs-Organization-Id`. If missing, the request fails with `409 Conflict`.
   - If an unauthorized or spoofed organization ID is passed, the request fails with `403 Forbidden` (`test_header_spoofing_other_org_fails_closed`).
   - If a broker has zero active organization memberships, access fails closed (`test_unenrolled_broker_fails_closed`).
3. **Database Query Scoping**:
   - Every lead, conversation, task, opportunity, and meeting query is explicitly scoped by `organization_id == tenant_id`.
   - Cross-tenant queries return `404 Not Found` (to avoid leaking resource existence) or `403 Forbidden` (`test_tenant_a_cannot_read_tenant_b_lead`, `test_idor_rejection_on_cross_tenant_task`).
4. **PII Masking & RBAC**:
   - Role-Based Access Control (`admin`, `agent`, `read_only`) filters fields based on privilege. Read-only roles receive masked contact information (`test_confidential_pii_masked_for_read_only_role`).

### 2.2 Background Task Tenant Validation
Celery background workers execute in asynchronous task queues. To prevent cross-tenant contamination:
- Background tasks accept an explicit `tenant_id` or `organization_id` parameter.
- Tasks validate that `tenant_id` is a valid UUID (`test_tenant_security_fail_closed_invalid_tenant`).
- When running system-wide cron scans (e.g., `evaluate_inactive_leads`), the task operates over an explicit tenant loop without fallback to insecure default tenants (`test_evaluate_inactive_leads_handles_all_and_uuid_tenant`).

---

## 3. Outbound Communication & FollowUp Hub Safeguards

### 3.1 Inert Runtime Gating
To protect customer contacts and avoid unintentional communication during staging or pre-pilot verification, the system implements an architectural circuit breaker:

- **Environment Flag**: `FOLLOWUP_HUB_DISPATCH_ENABLED` (defaults to `False`).
- **Runtime Verification**: The running Celery worker logs confirm:
  ```
  [FollowUpDispatch] FOLLOWUP_HUB_DISPATCH_ENABLED is false — no follow-up executions were dispatched.
  ```
- **Worker Behavior**:
  - `test_worker_is_inert_until_explicitly_enabled`: **PASSED**. When `FOLLOWUP_HUB_DISPATCH_ENABLED` is false, tasks scan and register pending executions in database tables without contacting external providers.
  - `test_disabled_channel_suppresses_execution`: **PASSED**. Channel-level toggles (e.g., `whatsapp_enabled`, `email_enabled`) independently suppress execution.

### 3.2 Idempotency & Duplicate Action Prevention
To prevent retrying workers from generating multiple customer messages:
1. **Deduplication Claims**: Follow-up actions claim an execution slot via atomic status updates (`claimed` / `processing`).
2. **Fresh Claim Protection**: `test_fresh_claim_is_not_stolen` verifies that active claims cannot be grabbed by concurrent workers.
3. **Stale Claim Recovery**: `test_stale_claim_is_reclaimed` ensures hung tasks are safely recovered after a timeout.
4. **Re-dispatch Prevention**: `test_second_run_does_not_redispatch` confirms that re-invoking the worker for the same time window results in zero redundant dispatches.

---

## 4. Webhook Security & Ingestion

1. **HMAC Signature Verification**:
   - Inbound WhatsApp webhooks from 360dialog/Meta enforce HMAC-SHA256 signature verification (`X-Hub-Signature-256`).
   - Invalid, missing, or tampered signatures are rejected before any request parsing occurs.
2. **Event Claim Deduplication**:
   - Inbound webhook events are recorded in the `webhook_event_claims` table with a unique constraint on `(provider, event_id)`.
   - Repeated webhook deliveries are safely acknowledged with HTTP 200 without executing duplicate business logic.

---

## 5. Secret Exposure Audit & Residual Risk Assessment

### 5.1 Gemini API Credential Status
- **Audit Finding**: In early commit history, a Google Gemini API credential was committed.
- **Mandatory Constraint**: "Do not rotate, revoke, replace, print, or otherwise change the existing Gemini credential without explicit authorization."
- **Current Runtime State**:
  - The API container reads `GEMINI_API_KEY` from the environment.
  - Health checks verify that the Gemini client initializes cleanly (`gemini-3.6-flash`).
  - No secret keys or connection strings are logged in application output or stdout.
- **Residual Risk Analysis**:
  - **Risk Level**: **MODERATE** (acceptable for a private, restricted internal/closed pilot; unacceptable for public release).
  - **Threat Vector**: If public access to historical git commits exists, the exposed key could be used to incur Google AI billing charges.
  - **Pilot Mitigations**:
    1. Repository access remains private and restricted to authorized team members.
    2. API spend limits and quota alerts are configured in the Google Cloud Console.
    3. The application operates in an isolated environment without public DNS.
  - **Production Prerequisite**: The credential MUST be rotated in Google Cloud Console and migrated to an external secrets manager (AWS Secrets Manager / Vault) prior to general production deployment.

### 5.2 SMTP & Communication Credentials
- **Status**: Production SMTP credentials (Brevo / SendGrid) and live WhatsApp Business API tokens are NOT configured in the environment.
- **Safeguard**: All outbound communications fail safely or are suppressed by `FOLLOWUP_HUB_DISPATCH_ENABLED=false`.

---

## 6. Security Gate Verification Summary

| Security Gate | Description | Verified Evidence | Status |
|---|---|---|---|
| **R11** | Cross-tenant isolation verified | 15/15 tenant isolation tests passed in container | **PASS** |
| **R12** | Authorization and approval enforcement verified | RBAC, JWT validation, and header scoping verified | **PASS** |
| **R13** | External communication safeguards verified | `FOLLOWUP_HUB_DISPATCH_ENABLED=false` actively suppressing outbound dispatch | **PASS** |
| **R14** | Secrets and residual exposure risks documented | Gemini key residual risk fully documented; zero secrets printed | **PASS** |
| **R15** | Worker retry and idempotency behavior verified | Atomic claim locks and deduplication tests pass | **PASS** |
