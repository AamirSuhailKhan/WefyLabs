# PHASE 0 ROUTE DUPLICATES & CONSOLIDATION STRATEGY

**Execution Date:** 2026-09-28T18:01:00+05:30  
**Target:** `apps/api/app/main.py` Route Registrations  
**Scope:** Duplicate Mounts, Dual Prefixes, and Legacy Endpoint Inventory  

---

## 1. DUPLICATE ROUTE MOUNT INVENTORY IN `main.py`

| Router Identifier | Mount Location 1 | Mount Location 2 | Canonical Route | Legacy / Duplicate Route | Consumers & Behavior Difference | Recommended Deprecation Action |
|---|---|---|---|---|---|---|
| **Health Router** (`health_router`) | Line 223 (`/health/*`) | Line 224 (`/api/v1/health/*`) | `/api/v1/health/readiness` & `/api/v1/health/liveness` | Root `/health/*` | Cloud orchestrators / render probes. Identical handlers. | Keep `/api/v1/health/*` as canonical. Retain `/health` as legacy alias for load balancer compatibility. |
| **Auth Router** (`auth_router`) | Line 225 (`/api/v1/auth/*`) | Line 226 (`/auth/*`) | `/api/v1/auth/*` | Root `/auth/*` | Frontend `api-client.ts` targets `/api/v1/auth/*`. Root mount is legacy. | Canonicalize all callers to `/api/v1/auth/*`. Log deprecation warning on root `/auth/*`. |
| **Invitations Router** (`invitations_router`) | Line 227 (`/api/v1/invitations/*`) | Line 228 (`/invitations/*`) | `/api/v1/invitations/*` | Root `/invitations/*` | Team invite redemption links. Identical handlers. | Canonicalize to `/api/v1/invitations/*`. |
| **Calendar Router** (`calendar_router`) | Line 284 (`/api/v1/calendar/*`) | Line 304 (`/api/v1/calendar/*`) | Line 284 mount | Line 304 redundant include | Literal exact duplicate include in `main.py`. | Remove line 304 redundant `app.include_router(calendar_router, prefix=settings.API_V1_STR)`. |
| **Portal Router** (`portal_router`) | Line 301 (`/api/v1/portal/*`) | Line 412 (`/api/v1/portal/*`) | Line 412 (`app.modules.portal`) | Line 301 (`presentation.api.v1.portal`) | Build 08 portal vs Part 21 digital deal room portal. | Consolidate to Part 21 canonical deal room portal. |
| **Leads Routers** | `clean_leads_v1_router` (Line 231) | `hex_leads_v1_router` (Line 232) | `clean_leads_v1_router` (`/api/v1/leads`) | `hex_leads_v1_router` | Hexagonal lead controller vs presentation leads router. | Retain `clean_leads_v1_router` as public API; hex as internal domain service. |

---

## 2. CANONICAL ROUTE STRATEGY

1. **Prefix Standard:** All business operations MUST be routed under `/api/v1/...`.
2. **Duplicate Mount Removal:** Remove redundant `calendar_router` include at line 304 in `main.py`.
3. **OpenAPI Schema Hygiene:** Eliminates redundant duplicate operations in generated `openapi.json`, bringing total operations down from 913 to canonical clean count.
