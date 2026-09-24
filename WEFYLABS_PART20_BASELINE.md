# WEFYLABS PART 20 — REALITY AUDIT & BASELINE
## Date: 2026-09-24 | Alembic Head Verified: 0032_supply_side_inventory_os

---

## 1. Verified Current State

| Fact | Verified Value |
| :--- | :--- |
| Alembic Head | `0032_supply_side_inventory_os (head)` — Single clean head |
| Part 19 Test Result | 19/19 PASS |
| Parts 17–18 Regression | 26/26 PASS |
| Combined | 45/45 PASS |
| Frontend Build | PASS — 46 routes, 0 errors |
| TypeScript | `npx tsc --noEmit` — 0 errors |

---

## 2. Existing Marketing/Campaign Infrastructure Audit

### 2.1 LeadCampaign (acquisition_models.py) — PARTIAL
**Status: BACKEND ONLY — PARTIAL**
- `LeadCampaign` model: EXISTS with fields: name, description, status (draft/active/paused/completed/cancelled), source_id, budget, currency, channel, start_at, end_at.
- `CampaignPropertyLink` model: EXISTS — links campaigns to property listings.
- `LeadCampaignService`: EXISTS — CRUD, property linking.
- **MISSING**: State machine enforcement, approval workflow, campaign_code, objective, inventory_scope, approval_state, campaign_type (LEAD_GENERATION vs PROJECT_LAUNCH vs INVENTORY_SALES), budget controls, audit trail.
- **MISSING**: Controlled state transitions with audit log.
- **MISSING**: Campaign approval entity (requester, reviewer, budget, approval_timestamp).

### 2.2 LeadSource (acquisition_models.py) — VERIFIED
**Status: VERIFIED**
- Full model: id, organization_id, name, channel, provider, status, webhook support, rate limiting.
- Used by acquisition pipeline.

### 2.3 SourceAttribution (acquisition_models.py) — VERIFIED
**Status: VERIFIED**
- Full UTM model: utm_source, utm_medium, utm_campaign, utm_term, utm_content.
- landing_page, referrer, first_touch_at, last_touch_at.
- Linked to lead_id, source_id, campaign_id, acquisition_event_id.

### 2.4 LeadAcquisitionEvent — VERIFIED
**Status: VERIFIED**
- Immutable provenance record per incoming signal.
- Idempotency via (source_id, external_id) or idempotency_key.

### 2.5 Property Listing (property_models.py) — VERIFIED
**Status: VERIFIED**
- `PropertyListing` exists as the canonical property entity.
- Used by matching, recommendation, CRM, Deal OS.

### 2.6 Revenue Intelligence (revenue_intelligence_models.py) — VERIFIED
**Status: VERIFIED**
- `RevenueFunnelSnapshot`, `RevenueLeakageEvent` exist.
- FunnelAnalyzer, LeakageAnalyzer, SourceQualityAnalyzer — all implemented.
- Attribution integrated with SourceAttribution.

### 2.7 Revenue Autopilot (revenue_autopilot_models.py) — VERIFIED
**Status: VERIFIED**
- `RevenueOpportunity`, `RevenueFeedbackLog` models exist.
- Opportunity types include: UNDER_MARKETED_INVENTORY, NEW_INVENTORY_DEMAND.

---

## 3. MISSING — Not Implemented in Parts 1–19

### 3.1 Marketing OS (ENTIRELY MISSING)
| Component | Status |
| :--- | :--- |
| MarketingCampaign (full OS entity with state machine, approval, objectives) | **MISSING** |
| CampaignApproval entity | **MISSING** |
| CampaignBudget tracking (planned/approved/spent/remaining) | **MISSING** |
| Campaign state machine (DRAFT→IN_REVIEW→APPROVED→SCHEDULED→ACTIVE→PAUSED→COMPLETED→CANCELLED) | **MISSING** |
| Campaign objective classification (LEAD_GENERATION, PROJECT_LAUNCH, INVENTORY_SALES, REMARKETING) | **MISSING** |
| Campaign inventory scope (project/phase/BHK/unit subset targeting) | **MISSING** |
| CampaignEvent (impressions, clicks, sessions, conversions — when data exists) | **MISSING** |
| Campaign audit trail | **MISSING** |

### 3.2 Listing Studio (ENTIRELY MISSING)
| Component | Status |
| :--- | :--- |
| PropertyListingPublication (marketing representation of canonical unit) | **MISSING** |
| ListingDistribution (channels: WEBSITE, PARTNER_PORTAL, SOCIAL, etc.) | **MISSING** |
| Publication state machine (DRAFT→READY→APPROVED→PUBLISHED→PAUSED→UNPUBLISHED) | **MISSING** |
| Stale listing detection | **MISSING** |
| Listing versioning | **MISSING** |
| AI listing content generation (grounded in canonical data) | **MISSING** |

### 3.3 Marketing Assets (ENTIRELY MISSING)
| Component | Status |
| :--- | :--- |
| MarketingAsset (IMAGE, VIDEO, BROCHURE, FLOOR_PLAN, PRICE_SHEET, etc.) | **MISSING** |
| Asset versioning | **MISSING** |
| Asset approval workflow | **MISSING** |
| Asset publication state | **MISSING** |

### 3.4 Landing Pages (ENTIRELY MISSING)
| Component | Status |
| :--- | :--- |
| LandingPage entity (project-scoped) | **MISSING** |
| LandingPage content blocks | **MISSING** |
| LeadCaptureForm (connected to canonical lead ingestion pipeline) | **MISSING** |
| Public landing page API | **MISSING** |
| SEO fields (slug, title, description, canonical_url, indexing_state) | **MISSING** |

### 3.5 Tracking & UTM Governance (PARTIAL)
| Component | Status |
| :--- | :--- |
| UTM persistence (in SourceAttribution) | VERIFIED |
| UTM validation/normalization | **MISSING** |
| Tracking link builder | **MISSING** |
| QR campaign generation | **MISSING** |
| Partner-specific tracking links | **MISSING** |

### 3.6 Project Launch OS (ENTIRELY MISSING)
| Component | Status |
| :--- | :--- |
| ProjectLaunch entity with checklist | **MISSING** |
| Launch readiness gate system | **MISSING** |
| Launch approval workflow | **MISSING** |
| Partner distribution for launch | **MISSING** |

### 3.7 Frontend Marketing Workspace (ENTIRELY MISSING)
| Component | Status |
| :--- | :--- |
| `/dashboard/marketing` — Campaign Command Center | **MISSING** |
| Campaign detail workspace | **MISSING** |
| Listing Studio workspace | **MISSING** |
| Project Launch checklist UI | **MISSING** |
| Asset management UI | **MISSING** |
| Landing page builder UI | **MISSING** |

---

## 4. What Part 20 MUST Build

1. `marketing_models.py` — MarketingCampaign, CampaignApproval, CampaignBudget, PropertyListingPublication, ListingDistribution, MarketingAsset, LandingPage, LeadCaptureForm, CampaignEvent, ProjectLaunch, TrackingLink.
2. Alembic migration `0033_marketing_os.py`
3. Service layer: `apps/api/app/modules/marketing/service.py`
4. REST router: `apps/api/app/modules/marketing/router.py`
5. Frontend: `apps/web/src/app/dashboard/marketing/page.tsx`
6. Test suites: 6 files covering campaigns, listings, attribution, AI safety, security, concurrency.
7. Documentation: 8 markdown files.

---

## 5. Integration Points (Existing — Must Reuse)

| System | Integration | How |
| :--- | :--- | :--- |
| LeadCampaign (Part 9) | Extend — do NOT duplicate | MarketingCampaign references LeadCampaign.id |
| SourceAttribution (Part 9) | Reuse canonical UTM | tracking_link → utm params → SourceAttribution |
| Universal intake (Part 9) | Canonical lead ingestion | Landing page form → public_capture_controller |
| RealEstateProject (Part 19) | Campaign links to project | FK to real_estate_projects.id |
| ProjectUnit (Part 19) | Listing grounded in unit | FK to project_units.id |
| ProjectPriceBook (Part 19) | Pricing sourced from price book | FK to project_price_books.id |
| Deal OS (Part 18) | Revenue attribution | campaign_id on deal creation |
| OutboxService (Part 17) | Event emission | All mutations emit outbox events |
| RevenueFunnelSnapshot (Part 11) | Attribution chain | marketing → lead → deal → revenue |
| RevenueOpportunity (Part 35) | Marketing intelligence | Add UNDER_MARKETED_INVENTORY etc. |

---

## 6. Non-Negotiable Constraints Confirmed

- No HubSpot, Salesforce, Zoho, Pipedrive dependencies.
- No autonomous paid campaign launches.
- No autonomous budget spending.
- No fabricated impressions, clicks, or ROI.
- No external listing portals unless actual credentials/API exist.
- WhatsApp remains disabled.
- Razorpay LIVE remains disabled.
- Multi-tenant isolation on every query.
- Decimal arithmetic for all money (`Numeric(20, 4)`).
