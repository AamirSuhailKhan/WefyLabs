# WEFYLABS MULTI-TENANT ZERO-TRUST SECURITY ARCHITECTURE
# Security Specification & IDOR Boundary Enforcement

---

## 1. Zero-Trust Multi-Tenancy Principles

1. **Server-Side Authority Only**: Never trust `tenant_id`, `organization_id`, or `broker_id` supplied in request bodies, query strings, or headers as authorization authority.
2. **Ambient & Validated Context**: Every tenanted request derives its active context via [`TenantContext`](file:///c:/Users/aamir/OneDrive/Desktop/crm%20real%20state/apps/api/app/dependencies.py) from the validated Supabase JWT and server-side `OrganizationMember` records.
3. **Fail-Closed on Context Absence**: If an account has no organization membership, or has multiple memberships without an explicit, authorized selection header (`X-WefyLabs-Organization-Id`), access is strictly denied (403 Forbidden or 409 Conflict).
4. **IDOR Assertion at Data Access Layer**: All mutating and retrieval endpoints enforce [`TenantSecurityGuard.assert_ownership`](file:///c:/Users/aamir/OneDrive/Desktop/crm%20real%20state/apps/api/app/infrastructure/security/tenant_guard.py) before returning or mutating entity state.
5. **Partitioned Cache & Queue Namespacing**: All Redis cache keys and queue locks follow the pattern `wefylabs:{tenant_id}:{subsystem}:{identifier}`.

---

## 2. Tenant Context Resolution Lifecycle

```
Client Request
      │  (Authorization: Bearer <JWT> + optional X-WefyLabs-Organization-Id)
      ▼
get_current_broker (dependencies.py)
      │  Validates token signature, expiration (exp), and broker existence in DB.
      ▼
get_current_tenant (dependencies.py)
      │  Queries DB: SELECT organization_id FROM organization_members WHERE broker_id = broker.id
      │  Validates requested org against authorized memberships.
      │  Constructs TenantContext(organization_id, broker_id, user_id).
      │  Stores context in contextvars (current_tenant_ctx).
      ▼
Router / Service Execution
      │  Applies TenantSecurityGuard.assert_ownership(entity, tenant_context).
      │  Executes scoped queries: WHERE organization_id = tenant.organization_id.
```

---

## 3. IDOR Defense Matrix

| Attack Vector | Defense Mechanism | Verified Result |
|---|---|---|
| **Path Parameter IDOR** (`GET /leads/{id}`) | `TenantSecurityGuard.assert_ownership` compares entity `organization_id` / `broker_id` with active `TenantContext` | 403 Forbidden on mismatch |
| **Header Spoofing** (`X-WefyLabs-Organization-Id: <victim-org>`) | `get_current_tenant` verifies membership in server DB | 403 Forbidden on unauthorized org |
| **Malformed / SQLi UUID** (`/leads/' OR '1'='1`) | `TenantSecurityGuard.validate_uuid` validates strict RFC 4122 format | Rejected before query |
| **Cache Key Confusion** (`rl:lead:101`) | `TenantSecurityGuard.build_cache_key` prefixes `wefylabs:{tenant_id}:...` | Zero cross-tenant cache collision |
| **Background Task IDOR** | `TenantContext.for_background_task(org_id)` validates tenant boundary in worker | Scope preserved in worker threads |

---

## 4. RBAC Permission Mapping

```
OWNER:     Full tenant authority (Leads, Orgs, Billing, Audit, API Keys)
ADMIN:     Full operational authority excluding ownership transfer
MANAGER:   Lead Read/Write/Export, Audit Log Read
AGENT:     Lead Read/Write (Assigned entities only)
READ_ONLY: Read-only access to CRM records
```

Server-derived via `app.infrastructure.security.rbac.get_current_role`. Client cannot escalate or request roles in payloads.

---
_Status: VERIFIED IN RUNTIME & TESTED (`apps/api/tests/test_part17_security.py`)._
