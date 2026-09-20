# P0 Change: Fail-Closed RBAC Resolution

## Problem

The reusable FastAPI RBAC guard accepted `Role.ADMIN` as its default. The CRM RBAC evaluator also returned agent permissions when no organization membership was found. Both behaviors could grant access without a server-verified role assignment.

## Change

- `app/infrastructure/security/rbac.py` now derives the role from the authenticated broker's `OrganizationMember` row.
- Missing membership and invalid role values return explicit 403 domain errors.
- `app/services/rbac_service.py` now returns no permissions for missing or unknown membership roles.
- Existing owner/admin/manager/agent permission mappings are preserved.

## Scope and Compatibility

No schema, API contract, frontend, or provider change was made. Accounts that previously used CRM routes without an organization membership will now receive a 403 instead of implicit agent access; this is intentional fail-closed behavior. The lightweight FastAPI guard has no active production router consumers yet, so its corrected behavior is available for gradual route adoption.

## Verification

- `python -m pytest tests/test_rbac_dependency.py tests/test_enterprise_foundation.py -q` — 18 passed.
- `python -m pytest tests/test_part26_lead_capture_hub.py -q` — 23 passed (existing AsyncMock coroutine warnings remain outside this change).
- Next.js production build compiled successfully and entered type validation; the environment ended the command before its final completion status, so a completed frontend build is **not** claimed.

## Remaining Work

- Establish explicit organization/tenant context for every request; legacy `Broker.organization_id` currently aliases broker ID.
- Apply principal-derived policy dependencies to every sensitive route and add API-level owner/admin/manager/agent/read-only coverage.
- Add two-tenant integration coverage for workers, storage, retrieval, caches, and exports.

## Follow-up P0: Calendar API Registration

The audit also found `calendar_router` mounted twice in `app/main.py`, which produced duplicate OpenAPI operation IDs. The duplicate mount was removed and `tests/test_openapi_calendar_contract.py` now prevents duplicate Calendar operation IDs. No Calendar route path or request/response contract changed.

## Follow-up P0: Calendar Object Authorization

Calendar meeting lookup, reschedule, cancellation, briefing, no-show prediction, and outcome routes now load the meeting through an organization-scoped query before operating. A foreign meeting now returns a generic 404, rather than exposing or mutating another tenant's record. Generic Calendar errors are logged server-side and return safe customer messages instead of raw exception text. No migration or public request-shape change was required.

## Follow-up P0: Tenant-Bound RBAC

The server-derived RBAC role lookup is now bound to the resolved organization
context. This prevents a user with different roles in two workspaces from being
authorized using an arbitrary membership row. No schema or public API shape
changed: the existing `X-WefyLabs-Organization-Id` tenant selection remains
server-validated by `get_current_tenant`. Regression coverage creates one owner
and one agent membership for the same broker and proves the selected tenant
determines the resulting role.
