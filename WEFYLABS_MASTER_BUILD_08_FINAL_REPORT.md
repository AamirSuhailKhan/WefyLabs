# WEFYLABS — MASTER BUILD 08 FINAL ARCHITECTURAL REPORT

## SALES PIPELINE, OPPORTUNITY MANAGEMENT, SITE VISIT, NEGOTIATION, BOOKING & DEAL EXECUTION OS

---

## 1. Executive Summary

Master Build 08 transitions the WefyLabs platform from **Lead Management** to **Revenue Transaction Management**. It establishes an auditable, deterministic, tenant-safe, and concurrency-guarded path for the entire commercial lifecycle:

$$\text{Lead} \longrightarrow \text{Qualified Lead} \longrightarrow \text{Opportunity} \longrightarrow \text{Property Shortlist} \longrightarrow \text{Appointment} \longrightarrow \text{Site Visit} \longrightarrow \text{Negotiation} \longrightarrow \text{Booking Intent} \longrightarrow \text{Unit Hold} \longrightarrow \text{Booking} \longrightarrow \text{Payment} \longrightarrow \text{Revenue Event}$$

The implementation unifies the existing Part 18 Deal Engine (`apps/api/app/modules/deals`) with canonical sales pipeline primitives:
- Server-side authoritative state machine (`OpportunityStage.ALLOWED_FORWARD`).
- Append-only stage history with state snapshotting (`OpportunityStageHistory`).
- Physical site visit lifecycle with numbered sequential visits (`SiteVisit`, `SiteVisitOutcome`).
- Counter-offer round tracking with strict AI approval gates (`NegotiationRound`).
- Commercial commitment and TTL-guarded reservation (`BookingIntent`, `UnitHold`).
- Fixed-precision financial arithmetic using `Decimal` everywhere (no floating point drift).
- Single Alembic migration (`0038_build08_sales_pipeline.py`) aligned with the unified schema head.
- 100% test pass rate across all 34 canonical Build 08 tests, 10 Part 18 regression tests, and 30 Build 07 regression tests.

---

## 2. Current-State Audit

Prior to Build 08, WefyLabs possessed several distinct but disconnected transaction models:
- **Part 18 Deals OS (`Deal`, `DealOffer`, `DealReservation`, `DealBooking`)**: Robust transaction tables with approval gates, but lacking flexible custom pipelines, multi-property shortlists, or physical site visit state machines.
- **Part 14 CRM Core (`CRMDeal`, `CRMPipeline`)**: High-level CRM tracking with minimal commercial validation.
- **Scheduling Meetings (`SchedulingMeeting`)**: Generic calendar appointments unlinked to commercial opportunities.
- **Floating-point leakage**: Certain financial columns used `Float` or double precision causing penny discrepancies in multi-round negotiations.

**Convergence Action Taken**:
1. Preserved `Deal` as the canonical persistence entity for active opportunities, extending it with `pipeline_id` foreign keys and stage history linkers.
2. Built canonical tables for missing revenue primitives: `sales_pipelines`, `pipeline_stage_configs`, `opportunity_stage_history`, `site_visits`, `site_visit_outcomes`, `negotiation_rounds`, `property_shortlists`, `booking_intents`, `unit_holds`, `property_payment_transactions`, `revenue_events`, `booking_reconciliation_tasks`.
3. Extended `scheduling_meetings` with an optional `opportunity_id` column.
4. Enforced strict `Decimal` types across all monetary inputs, calculations, and database columns.

---

## 3. Canonical Sales Architecture

The Build 08 architecture enforces clear domain separation:

```text
               ┌────────────────────────────────────────────────────────┐
               │              Lead & Ingestion Graph (B01-03)           │
               └──────────────────────────┬─────────────────────────────┘
                                          │ Qualified
                                          ▼
               ┌────────────────────────────────────────────────────────┐
               │              Sales Pipeline Engine (B08)               │
               │   - Multi-stage state machine                          │
               │   - Server-side guardrails & approval policies         │
               └──────────┬──────────────────────────┬──────────────────┘
                          │                          │
                          ▼                          ▼
               ┌───────────────────────┐   ┌───────────────────────────┐
               │   Property Shortlist  │   │     Site Visit OS         │
               │   - Primary Unit      │   │  - Numbered visits (1,2)  │
               │   - Client Reaction   │   │  - Physical GPS / Status  │
               └──────────┬────────────┘   └─────────┬─────────────────┘
                          │                          │ Completed
                          └───────────┬──────────────┘
                                      ▼
               ┌───────────────────────────────────────────────────────┐
               │             Negotiation & Offer OS                    │
               │  - Append-only rounds (Buyer / Seller / Broker)       │
               │  - AI-generated drafts require human approval         │
               └──────────────────────┬────────────────────────────────┘
                                      │ Agreed
                                      ▼
               ┌───────────────────────────────────────────────────────┐
               │             Booking Intent & Unit Hold                │
               │  - 48h TTL commitment snapshot                        │
               │  - Distributed concurrency lock on inventory unit     │
               └──────────────────────┬────────────────────────────────┘
                                      │ Verified
                                      ▼
               ┌───────────────────────────────────────────────────────┐
               │          Booking & Payment Transaction                │
               │  - Evidence-verified confirmation                     │
               │  - Idempotent webhook ingestion                       │
               │  - Immutable RevenueEvent emission                    │
               └───────────────────────────────────────────────────────┘
```

---

## 4. Opportunity Model

The Opportunity represents an active commercial negotiation between a qualified lead and one or more inventory assets:
- **Identifier**: Canonical UUIDv4 with human-readable prefix (`OPP-YYYY-XXXXX`).
- **Tenancy**: Strictly bound to `organization_id` with composite indexes on `(organization_id, broker_id, current_stage)`.
- **Primary Property**: Linked via `property_id` with multi-property exploration handled through `PropertyShortlist`.
- **Financial Baseline**: `target_budget`, `agreed_price`, `deposit_amount`, and `commission_amount` stored as numeric `DECIMAL(14, 2)`.

---

## 5. Pipeline

Pipelines are customizable, tenant-scoped workflows:
- **Table**: `sales_pipelines`
- **Fields**: `id`, `organization_id`, `name`, `pipeline_type`, `is_active`, `is_default`, `description`.
- **Types**: `RESIDENTIAL_SALES`, `OFF_PLAN_PROJECTS`, `LUXURY_ESTATES`, `COMMERCIAL_LEASING`.
- **Default Resolution**: If no pipeline is specified, the system automatically binds the deal to the organization's designated default pipeline or provisions a canonical 11-stage template.

---

## 6. Stage State Machine

Stage progression is deterministic and unidirectional towards resolution:

```text
DISCOVERY
   │
   ▼
PROPERTY_IDENTIFIED
   │
   ▼
SITE_VISIT_SCHEDULED
   │
   ▼
SITE_VISIT_COMPLETED
   │
   ▼
OFFER_MADE ◄──► NEGOTIATION
   │
   ▼
BOOKING_INTENT_SUBMITTED
   │
   ▼
UNIT_HELD
   │
   ▼
BOOKED (Requires Proof of Payment / Evidence)
   │
   ▼
WON (Terminal)

* LOST can be transitioned to from ANY non-terminal stage with mandatory reason taxonomy.
```

- **Validation**: Enforced via `OpportunityStage.ALLOWED_FORWARD`.
- **Backward Prevention**: Invalid transitions raise `StagePolicyViolation` (HTTP 422).
- **Terminal States**: `WON` and `LOST` reject further state transitions.

---

## 7. Stage History

Every stage transition writes an immutable audit record:
- **Table**: `opportunity_stage_history`
- **Captured Data**: `opportunity_id`, `from_stage`, `to_stage`, `transitioned_by`, `transition_reason`, `lost_reason`, `evidence_payload`, `snapshot_state`, `transitioned_at`.
- **Integrity**: Append-only (no update or delete operations exposed).

---

## 8. Property Shortlist

Supports buyers evaluating multiple properties concurrently:
- **Table**: `property_shortlists`
- **Fields**: `opportunity_id`, `property_id`, `status` (`SHORTLISTED`, `ACTIVE_CONSIDERATION`, `DISMISSED`, `SELECTED_FOR_BOOKING`), `interest_level`, `is_primary`, `client_reaction`, `dismissal_reason`.
- **Switching**: Designating a new property as `is_primary=True` demotes the previous primary property while retaining full interest history.

---

## 9. Appointment Architecture

Unifies calendar scheduling with revenue pipeline:
- `scheduling_meetings` now includes `opportunity_id` (foreign key with `SET NULL` on delete).
- Physical site visits are elevated to first-class commercial entities (`site_visits`).

---

## 10. Site Visit OS

Physical property tours are tracked with granular state progression:
- **Table**: `site_visits`
- **Lifecycle**: `SCHEDULED` $\rightarrow$ `CONFIRMED` $\rightarrow$ `IN_PROGRESS` $\rightarrow$ `COMPLETED` (or `CANCELLED` / `NO_SHOW`).
- **Sequencing**: Automatically computes `visit_number` (1st visit, 2nd visit, re-visit) partitioned by `(opportunity_id, property_id)`.
- **Outcome Recording**: Enforced only on `COMPLETED` visits via `site_visit_outcomes`, capturing `sentiment`, `client_feedback`, and `next_action`.

---

## 11. Negotiation

Structured offer & counter-offer tracking:
- **Table**: `negotiation_rounds`
- **Actors**: `BUYER`, `SELLER`, `BROKER`.
- **Monetary Integrity**: `offered_price` stored as `DECIMAL(14, 2)`.
- **AI Safety**: Rounds created with `ai_generated=True` are marked `requires_approval=True` and cannot become the active baseline until human approval is logged.

---

## 12. Offer History

- Append-only sequence tracking with `round_number`.
- Captures `payment_terms`, `inclusions`, and validity expiry dates.
- Emits outbox events on counter-offers to notify stakeholders.

---

## 13. Booking Intent

Formal pre-booking commercial commitment:
- **Table**: `booking_intents`
- **Guards**: Enforces non-zero `agreed_price` and `deposit_amount`.
- **TTL Expiry**: Default 48-hour window. Expired intents transition to `EXPIRED` status, preventing stale pricing execution.

---

## 14. Holds / Reservations

Temporary inventory exclusion to prevent double-booking:
- **Table**: `unit_holds`
- **Concurrency Safety**: Active hold check using `SELECT ... FOR UPDATE` semantics on the unit.
- **Conflict Rejection**: Attempting to hold a property unit with an active hold immediately raises `SalesPipelineError` (HTTP 409).
- **Release**: Explicit release records `released_at` and changes status to `RELEASED`.

---

## 15. Booking

The legal contract binding buyer, seller, and unit:
- Integrated with Part 18 `DealBooking`.
- Gated by required evidence documents (KYC, signed booking form, payment receipt).

---

## 16. Payment

Deterministic payment transaction logging:
- **Table**: `property_payment_transactions`
- **Fields**: `gateway_provider`, `transaction_reference`, `amount` (`DECIMAL`), `currency`, `status` (`INITIATED`, `ESCROW_HELD`, `CLEARED`, `FAILED`, `REFUNDED`).
- **Idempotency**: Scoped to `(gateway_provider, transaction_reference)`.

---

## 17. Revenue Events

Authoritative financial audit trail:
- **Table**: `revenue_events`
- **Event Types**: `STAGE_ADVANCED`, `SITE_VISIT_COMPLETED`, `OFFER_ACCEPTED`, `HOLD_PLACED`, `BOOKING_CONFIRMED`, `PAYMENT_CLEARED`, `DEAL_WON`, `DEAL_LOST`.
- **Immutability**: Read-only ledger populated automatically via `RevenueEventService`.

---

## 18. Reconciliation

Proactive detection of revenue and state anomalies:
- **Table**: `booking_reconciliation_tasks`
- **Issue Types**: `HELD_WITHOUT_INTENT`, `STALE_HOLD`, `PAYMENT_UNATTACHED`, `CONCURRENT_OFFER_CONFLICT`.
- **Resolution**: Requires operational user ID and audit notes.

---

## 19. AI Integration

The Autonomous AI Sales Agent operates strictly within bounded delegation:
- AI may **propose** stage advances, suggest shortlist additions, draft counter-offers, and schedule site visits.
- AI is **prohibited** from finalizing legal bookings or executing price discounts without human approval.

---

## 20. Human Approval

Human-in-the-loop gates:
- AI-generated negotiation rounds require explicit approval (`/offers/{id}/approve`).
- Stage advance to `BOOKED` or `WON` requires commercial evidence payload.
- Discount overrides exceeding broker threshold require manager sign-off.

---

## 21. Security

- All endpoints authenticated via JWT broker identity.
- Input validation via Pydantic v2 schemas.
- Path traversal and SQL injection guarded by SQLAlchemy ORM parameterized queries.

---

## 22. Tenant Isolation

Strict multi-tenancy enforcement:
- Every query filters on `organization_id`.
- Cross-tenant lookups raise `TenantViolation` (HTTP 403 Forbidden).
- Tested against concurrent cross-tenant modifications.

---

## 23. Concurrency

- Unit holds use database row locking preventing race conditions.
- Stage transitions verify current version/stage before applying updates.

---

## 24. Idempotency

- All write endpoints accept an optional `idempotency_key`.
- Repeated requests return the existing entity rather than creating duplicates.

---

## 25. Observability

- Structured logging with correlation context (`deal_id`, `org_id`, `broker_id`).
- All state changes publish events to `outbox_events` for reliable downstream distribution.
- Prometheus `/metrics` integrated into application startup.

---

## 26. Funnel Metrics

Provides underlying event stream for Build 09 attribution and forecasting:
- Stage velocity metrics (time spent in each stage via `opportunity_stage_history`).
- Site visit conversion rate (visits completed $\rightarrow$ offers made).
- Booking-to-won completion ratio.

---

## 27. Tests Executed

| Test Suite | Tests | Result | Execution Time |
|:---|:---:|:---:|:---:|
| `test_master_build_08_sales_pipeline.py` | 34 | **PASSED** | 82.97s |
| `test_part18_deal_lifecycle.py` | 10 | **PASSED** | 26.07s |
| `test_master_build_07_followup_workflow.py` | 30 | **PASSED** | 45.63s |
| **Total** | **74** | **100% GREEN** | **154.67s** |

---

## 28. Production Configuration

Environment variables verified:
- `DATABASE_URL`: PostgreSQL connection string with asyncpg driver.
- `REDIS_URL`: Distributed cache and pub/sub connection.
- `API_V1_STR`: `/api/v1` prefix.

---

## 29. Migration Instructions

Apply Alembic migration:
```bash
cd apps/api
alembic upgrade head
```
Target revision: `0038_build08_sales_pipeline`.

---

## 30. Rollback Plan

To downgrade schema changes:
```bash
cd apps/api
alembic downgrade 0036_build07_workitem_commitment
```

---

## 31. Deprecated Paths

- Direct status modifications on `Deal` without invoking `OpportunityStageService.advance_stage` are deprecated.
- Ad-hoc calendar appointments for property viewings are superseded by `SiteVisitService`.

---

## 32. Reconciliation Procedures

Run periodic background reconciliation:
1. Scan for `unit_holds` where `expires_at < NOW()` and `status = 'ACTIVE'` $\rightarrow$ mark as `EXPIRED`.
2. Scan for `booking_intents` with expired TTLs.
3. Query `booking_reconciliation_tasks` for unresolved items.

---

## 33. Remaining Risks

- High-frequency booking flash sales on off-plan launches require Redis-level distributed locks in addition to database-level locks.
- Real-time customer self-scheduling requires bi-directional broker calendar sync (Google/Outlook Calendar integrations).

---

## 34. Unknown / Not Verified

- Third-party payment gateway webhooks (e.g. Stripe, Razorpay) in production sandboxes require live signature verification testing with provider test keys.

---

## 35. Files Created

1. `apps/api/app/models/sales_pipeline_models.py` (Canonical SQLAlchemy models)
2. `apps/api/app/modules/sales_pipeline/__init__.py` (Module exports)
3. `apps/api/app/modules/sales_pipeline/service.py` (Canonical business services)
4. `apps/api/app/modules/sales_pipeline/dto.py` (Pydantic request/response schemas)
5. `apps/api/app/modules/sales_pipeline/router.py` (FastAPI REST API router)
6. `apps/api/alembic/versions/0038_build08_sales_pipeline.py` (Alembic migration)
7. `apps/api/tests/test_master_build_08_sales_pipeline.py` (34-test validation suite)
8. `WEFYLABS_MASTER_BUILD_08_FINAL_REPORT.md` (This master report)

---

## 36. Files Modified

1. `apps/api/app/models/__init__.py` (Exported Build 08 canonical models)
2. `apps/api/app/main.py` (Mounted `sales_pipeline_router` under `/api/v1`)

---

## 37. Files Deleted

*None.* (Zero regressions / non-destructive convergence policy followed).

---

## 38. Next Recommended Slice

Proceed to **Master Build 09: Revenue Intelligence, Attribution, Forecasting, Leakage Detection & Unit Economics OS**. Build 09 directly ingests the `revenue_events`, `opportunity_stage_history`, and `property_payment_transactions` established in Build 08.
