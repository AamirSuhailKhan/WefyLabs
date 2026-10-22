# Phase 2C.6C Canonical Identity Truth & Tenant Authority Audit

## 1. Executive Summary & Identity Architecture
This audit establishes the singular authoritative identity and authorization chain in WefyLabs.

In compliance with Phase 2 requirements, caller-controlled organization or tenant identity **MUST NOT** determine authorization. The backend derives tenant authority exclusively from authenticated session credentials verified against authoritative database state.

The singular canonical identity chain is:
```
AUTHENTICATED SESSION (Supabase JWT / HttpOnly Cookie)
       ↓
CURRENT BROKER (PostgreSQL `brokers` table via email / sub)
       ↓
ORGANIZATION MEMBERSHIP (PostgreSQL `organization_members` table)
       ↓
CANONICAL ORGANIZATION (PostgreSQL `organizations` table)
       ↓
TENANT CONTEXT (Frozen ContextVar `TenantContext` injected into Domain Services)
```

---

## 2. Frontend Identity Parameter Audit

An exhaustive audit of all parameters passed from `apps/web` across API endpoints revealed:

| Parameter Passed | Transport Mechanism | Client Source | Backend Handling & Security Enforcement |
| :--- | :--- | :--- | :--- |
| `Authorization` | HTTP Header (`Bearer <jwt>`) | `localStorage.getItem('wefylabs_token')` | Validated cryptographically via `SUPABASE_JWT_SECRET` (HS256/RS256). Subject identifier maps strictly to `brokers.id` or `brokers.email`. |
| `X-WefyLabs-Organization-Id` | HTTP Header | `localStorage.getItem('wefylabs_org_id')` | **Treated strictly as a workspace selector, NEVER as an authorization grant.** Validated against `organization_members` where `broker_id == current_broker.id`. Spoofed UUIDs return 403 `ORGANIZATION_ACCESS_DENIED`. |
| `broker_id` (in payloads) | JSON Body / Query Param | Frontend state | **Ignored for authorization.** Backend overrides or compares against `current_broker.id`. A broker cannot create or modify resources on behalf of another broker. |
| `organization_id` (in payloads) | JSON Body | Frontend state | **Overridden server-side.** Backend controllers explicitly inject `tenant.organization_id` from the verified `TenantContext`, preventing cross-tenant write injection. |
| `email` | Form Body (Login/Register) | User Input | Used solely during initial authentication. Once authenticated, email is derived from the JWT claims or broker record. |

---

## 3. Adversarial Identity Verification Results

The automated script `scripts/verify_identity_truth.py` executed live verification against production PostgreSQL tables:

```
[PASS] 1. Token -> Verified Broker: Aamir Suhail (aamir.fresh@bmu.edu.in) [ID: c193be18-4a6a-4030-9089-f94c42119189]
[PASS] 2. Verified Broker -> Canonical Tenant: a0317351-e076-493e-8b84-182f8c43666e (Role: OWNER)
[PASS] 3. Spoofed Org ID (5651f9f3-2a17-4261-8b22-1989887e25d1) Rejected with 403 ORGANIZATION_ACCESS_DENIED
[PASS] 4. Malformed Org ID Rejected with 400 INVALID_ORGANIZATION_CONTEXT
[PASS] 5. No Header -> Auto-selected Sole Organization: a0317351-e076-493e-8b84-182f8c43666e
```

### Key Security Guarantees:
1. **Zero Trust for Client Org Headers**: When broker `c193be18-...` attempted to access another organization (`5651f9f3-...` Test Agency) by injecting its UUID into `X-WefyLabs-Organization-Id`, the backend immediately rejected the request with HTTP 403 `ORGANIZATION_ACCESS_DENIED`.
2. **UUID Format Strictness**: Any non-UUID string in the organization header triggers HTTP 400 `INVALID_ORGANIZATION_CONTEXT`.
3. **Single Membership Graceful Resolution**: If a user belongs to exactly one organization, omitting the header automatically resolves their legitimate organization without ambiguity or friction.
4. **Platform Operations Isolation**: Super-admin actions are protected by `require_super_admin`, which enforces a strict server-side email allowlist (`SUPER_ADMIN_EMAILS`). Owning a tenant grants zero platform operator privileges.

---

## 4. Tenant Context Lifecycle in Domain Services

Once `get_current_tenant` produces a `TenantContext`, it is injected via Python's `contextvars`:
```python
current_tenant_ctx.set(ctx)
```
Background worker tasks (`Celery`) instantiate explicit background contexts using:
```python
TenantContext.for_background_task(organization_id=org_id, broker_id=broker_id)
```
This guarantees that asynchronous tasks never cross tenant boundaries, and audit entries capture the correct tenant provenance.
