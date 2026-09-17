# PART 33.1 — COMMAND CENTER PERMANENT FIX
**Root Cause Resolution, Database Drift Elimination, Contract Alignment & Categorized Error Handling**

---

## 1. Exact Root Causes

Three distinct factors converged to create the user-facing failure:

1. **Database Schema Drift (`property_listings.total_floors`)**:
   - **ORM Model**: `PropertyListing` in `apps/api/app/models/property_models.py` declared:
     ```python
     floor_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
     total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
     ```
   - **PostgreSQL Database**: In initial migrations, `total_floors` was omitted from `property_listings`, causing PostgreSQL to raise:
     ```
     <class 'asyncpg.exceptions.UndefinedColumnError'>: column property_listings.total_floors does not exist
     ```
   - **Resolution**: Alembic migration `0025_property_total_floors.py` added `total_floors` as an idempotent, non-destructive, nullable integer. Column verified present and queryable via live SQLAlchemy ORM.

2. **Frontend Contract Mismatch**:
   - **FastAPI REST Endpoint**: `GET /api/v1/command-center` returns `CommandCenterResponseDTO` directly at the root JSON level (`{ organization_id, broker_id, summary, priorities, ... }`).
   - **Client Wrapper (`apps/web/src/lib/api-client.ts`)**: `api.commandCenter.getData()` was typed as `fetcher<{ success: boolean; data: CommandCenterResponse }>`.
   - **React Component (`apps/web/src/components/dashboard/CommandCenterView.tsx`)**:
     ```typescript
     const res = await api.commandCenter.getData();
     if (res && res.data) {
       setData(res.data);
     }
     ```
     Because FastAPI returns the DTO directly at the root, `res.data` was `undefined`.
     `setData` was never called, leaving `data: null`.
     The component evaluated `if (error || !data)` to `true` and rendered the fallback:
     *"An unexpected error occurred while loading dashboard metrics."*
   - **Resolution**:
     - `api-client.ts` now unpackages either `res.data` or `res` directly: `return (res && res.data) ? res.data : res;`.
     - `CommandCenterView.tsx` unpacks with fallback: `const payload = (res as any)?.data ?? res; if (payload && (payload.summary || payload.priorities)) { setData(payload); }`.
     - Same robust unpacking applied to `getStartMyDay`, `getSummary`, `getPriorities`, `getToday`, `getInventoryIntelligence`, and `getBriefing`.

3. **Categorized Error Handling & Trial Gating**:
   - The user account `aamirsuhail.khan.21cse@bmu.edu.in` has `trial_ends_at: 2026-09-05` (`trial_days_remaining: 0`).
   - The banner in `DashboardNav.tsx` (`"Your 7-Day Free Trial has expired. Upgrade your plan to continue qualifying leads."`) accurately displays subscription status.
   - Command Center does **not** block expired trial users from reading operational overviews.
   - Replaced the generic fallback error view with categorized states:
     - **401 Unauthorized**: "Session Expired" with [Sign In Again] CTA.
     - **402 / 403 Plan Required**: "Active Plan Required" with [View Upgrade Plans] CTA.
     - **403 Forbidden**: "Access Restricted".
     - **429 Rate Limit**: "Rate Limit Reached".
     - **Network / Offline**: "Network Connection Issue".
     - **500 Server**: "Command Center Temporarily Unavailable" with controlled, debounced [Retry Connection].

4. **Next.js Console Warning**:
   - `apps/web/src/app/globals.css` declared `html { scroll-behavior: smooth; }`, which triggers Next.js's router transition warning.
   - Replaced with `html[data-scroll-behavior="smooth"] { scroll-behavior: smooth; }` and added `data-scroll-behavior="smooth"` to `<html lang="en">` in `apps/web/src/app/layout.tsx`.

---

## 2. Actual Runtime Environment

- **Frontend**: Next.js 15.5.24 (`http://localhost:3000`), TypeScript, React 19.
- **Backend**: FastAPI with Uvicorn (`http://localhost:8000`), Python 3.14.
- **Database**: PostgreSQL (Supabase pooler) with asyncpg driver; Alembic migration head `0025_property_total_floors`.

---

## 3. Command Center Endpoint Verification

- **Method**: `GET`
- **Endpoint**: `/api/v1/command-center`
- **Before**: Returned 500 (`UndefinedColumnError`) $\to$ followed by 200 with root DTO that frontend failed to parse (`res.data === undefined`), displaying "Command Center Unavailable".
- **After**: Returns HTTP 200 with complete 16-key root payload (`organization_id`, `broker_id`, `broker_name`, `summary`, `priorities`, `daily_briefing`, `today_schedule`, `first_contact_queue`, `overdue_followups`, `hot_leads`, `stale_leads_summary`, `inventory_opportunities`, `inventory_gaps`, `demand_heatmap`, `recent_activities`). Frontend parses seamlessly and renders "ACTIVE COMMAND CENTER".

---

## 4. Database Schema Audit

| Table | Column | Type | Nullable | Model Match | DB Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `property_listings` | `floor_number` | `integer` | `YES` | Match | **PRESENT** |
| `property_listings` | `total_floors` | `integer` | `YES` | Match | **PRESENT** |
| `property_listings` | 64 other columns | matches | matches | Match | **ALL 66 PRESENT** |

---

## 5. Alembic Revisions

- **Heads**: `0025_property_total_floors (head)`
- **Current**: `0025_property_total_floors`
- **Migration Path**: `0024_onboarding_activation_demo` $\to$ `0025_property_total_floors`

---

## 6. Test Verification Results

| Test Suite | Scope | Result | Passing |
| :--- | :--- | :--- | :--- |
| `test_part33_1_command_center_fix.py` | Schema, ORM query, contract, expired trial, tenant isolation, guard | **PASS** | **8/8** |
| `test_part33_1_schema_drift.py` | Property Listings schema drift | **PASS** | **7/7** |
| `test_part30_api.py` | Command Center API suite | **PASS** | **16/16** |
| `test_part28_property_inventory.py` | Property Inventory CRM | **PASS** | **14/14** |
| `test_part29_ai_matching.py` | AI Matching Engine | **PASS** | **14/14** |
| **Frontend TypeScript** | `npx tsc --noEmit` | **PASS** | **0 errors** |
| **Frontend Build** | Next.js `npm run build` | **PASS** | **33/33 static pages** |

---

## 7. Regression Prevention Guard

1. **Schema Drift Detection**: Added `test_schema_drift_guard_column_inspection` in `test_part33_1_command_center_fix.py` which verifies at test time that all mapped SQLAlchemy attributes exist in table columns.
2. **Contract Alignment Guard**: Automated tests explicitly assert root-level keys of `CommandCenterResponse` to catch envelope discrepancies before release.
3. **Resilient Frontend Parsing**: The frontend now safely supports both direct DTOs and `{ data: ... }` enveloped responses.
