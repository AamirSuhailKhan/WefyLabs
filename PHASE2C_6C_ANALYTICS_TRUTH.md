# WEFYLABS PHASE 2C.6C — ANALYTICS TRUTH & LINEAGE SPECIFICATION

**Certified At:** 2026-10-06T15:00:00+05:30  
**Repository Branch:** `level-3`  
**Git Commit:** `9bc40ca9ccf853c1ee02be54f63c33564a7d8410`  
**Governance Runtime:** `STAGE_1_SHADOW` | **Autonomy:** 0  
**Status:** FULLY RECONCILED AGAINST AUTHORITATIVE POSTGRESQL

---

## 1. Analytics Architecture & Transformation Pipeline

Every analytical metric presented on WefyLabs follows an unbroken, tenant-scoped four-stage lineage:

```
[PostgreSQL Supabase (ap-south-1)]
              ↓ (SQL / AsyncPG with tenant filter)
[FastAPI Analytics & Revenue Services]
              ↓ (Deterministic transformation & aggregation in Python)
[FastAPI REST Response (Pydantic DTO)]
              ↓ (Typed JSON via HTTPS)
[React / Next.js Presentation View]
```

### Absolute Rules Enforced:
1. **Zero Double Counting:** Deduplication is enforced by primary keys (`lead.id`, `deal.id`, `booking.id`).
2. **Deterministic Timezones:** All timestamps are stored and aggregated in UTC (`DateTime(timezone=True)`). Date filtering strictly parses ISO 8601 UTC strings.
3. **No Synthetic Extrapolations:** Denominators of zero return `null` / `None`, not fabricated default numbers (e.g., 0% vs null conversion rate).
4. **Currency Truth:** All amounts are explicitly typed with their currency code (INR for pilot tenant, AED for UAE properties). No cross-currency mixing without exchange rate normalization.
5. **Stage 1 Shadow Attribution:** All AI-driven autonomous revenue attribution is locked at ₹0.00.

---

## 2. Comprehensive Metric Lineage Matrix

| Metric Name | Authoritative Source Table | Filtering & Grouping Criteria | Python Transformation / Aggregation | API Endpoint | Frontend Screen | Reconciled Value |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Total Active Leads** | `leads` | `organization_id = tenant_id` AND `deleted_at IS NULL` | `count(Lead.id)` | `GET /api/v1/leads/overview/metrics` | Command Center & Leads | **3** |
| **Pipeline Stage Distribution** | `leads` | Grouped by `pipeline_stage` | `{stage: count}` mapping | `GET /api/v1/revenue-intelligence/funnel` | Revenue Funnel | **new: 3, others: 0** |
| **Stage Conversion Rates** | `leads` | Next stage count / current stage count | `round((next / curr) * 100, 2)` or `null` if denominator = 0 | `GET /api/v1/revenue-intelligence/funnel` | Revenue Funnel | **new->contacted: 0.0% (rest null)** |
| **Estimated Pipeline Value** | `leads` | `pipeline_stage IN ('qualified', 'site_visit', 'negotiation')` | `sum(budget_max)` | `GET /api/v1/revenue-intelligence/funnel` | Revenue Intelligence | **null (no leads past new)** |
| **Active Deal Pipeline Value** | `deal_transactions` | `organization_id = tenant_id` AND `current_stage != 'cancelled'` | `sum(agreed_price)` | `GET /api/v1/deals/summary` | Deals / Pipeline | **₹22,000,000** |
| **Realized / Confirmed Revenue** | `deal_transactions` | `organization_id = tenant_id` AND `current_stage = 'commission_received'` | `sum(estimated_commission_amount)` | `GET /api/v1/revenue-intelligence/funnel` | Revenue Intelligence | **null / ₹0 (Deal at booking stage)** |
| **Gross Commission Approved** | `commissions` | `booking_id = BKG-2026-001` | Record amount | `GET /api/v1/commissions` | Revenue / Commissions | **₹440,000** |
| **Net Commission Payable** | `commissions` | `booking_id = BKG-2026-001` (TDS 10% deducted) | Record net amount | `GET /api/v1/commissions` | Revenue / Commissions | **₹396,000** |
| **Stage 1 Causal AI Revenue** | Governance Ledger | Strict autonomy 0 constraint | Identity: `0.00` | System Governance | Revenue OS | **₹0.00 (Certified)** |
| **Revenue at Risk Estimate** | `leads` | `pipeline_stage = 'new'` AND age > 14 days | `sum(budget_max)` for stale leads | `GET /api/v1/revenue-intelligence/leakage` | Revenue Leakage | **₹18,000,000** |
| **Data Health Score** | `leads` + `properties` | Completeness of source, budget, contact info | `round((audited - issues) / audited * 100, 1)` | `GET /api/v1/revenue-intelligence/data-quality` | Data Quality Report | **100.0%** |
| **Active Revenue Opportunities** | `revenue_opportunities` | `status IN ('NEW', 'RECOMMENDED', 'ACTIONED')` | `count(RevenueOpportunity.id)` | `GET /api/v1/revenue/action-queue` | Command Center & Action Queue | **2** |
| **Demand Gaps Deficit** | `leads` vs `property_listings` | Grouped by `locality` + `bedrooms` | `active_buyers - matching_listings` | `GET /api/v1/revenue/demand-intelligence` | Demand Intelligence | **Indiranagar 2BHK: Deficit 1** |

---

## 3. Boundary & Integrity Verification

### A. Date Boundaries & Timezones
- In `RevenueIntelligenceService`:
  ```python
  if date_from:
      filters.append(Lead.created_at >= date_from)
  if date_to:
      filters.append(Lead.created_at <= date_to)
  ```
- All datetime comparisons use timezone-aware UTC. Malformed datetime strings are trapped with HTTP 422 Unprocessable Entity, preventing silent truncation or corrupt queries.

### B. Deduplication & Unique Constraints
- Leads are unique by `id` (UUID PK).
- Deals are unique by `id` (UUID PK) and display unique readable code `deal_reference = DEAL-2026-001`.
- Bookings are unique by `id` (UUID PK) and unique readable number `booking_reference = BKG-2026-001`.
- Site visits are unique by `id` (UUID PK). DLF Magnolias site visit exists exactly once (`1232912f-4db5-4f20-a3f8-c33454ed6b48`).

### C. Rounding & Currency Safety
- Monetary amounts in INR (Indian Rupee) are modeled as `Float` or `Numeric(14,2)` and displayed with locale formatting (e.g. `₹2,20,00,000` / `₹22M`).
- Rates are rounded deterministically to 1 or 2 decimal places using `round(val, 2)`.

---

## 4. UI State Grounding (Zero vs Loading vs Error)
1. **Real Zero:** When a count is legitimately 0 (e.g., 0 completed deals, 0 contacted leads), the API returns `0` or `null`, and the UI presents an informative zero/empty state.
2. **Error Isolation:** If an API endpoint fails, HTTP error status (4xx/5xx) is caught by `api-client.ts` and displays an explicit error toast/banner, never substituting false zeros.
3. **Loading States:** Skeletons and spinners are rendered during fetch promises and only transition upon fulfilled responses.
