# WEFYLABS BUILD 08 — SALES PIPELINE CURRENT-STATE AUDIT

Generated: 2026-09-26 | Auditor: Build 08 Principal Engineer

---

## AUDIT METHODOLOGY

Every file in `apps/api/app/` was inspected for the following domain concepts:
opportunity, deal, pipeline, stage, appointment, site_visit, booking, reservation, hold, payment, transaction, revenue, invoice, commission.

Each implementation is classified as:
CANONICAL | DUPLICATE | LEGACY | PARTIAL | FRONTEND-ONLY | BACKEND-ONLY | MOCKED | HARDCODED | STUBBED | DEAD | PRODUCTION-RISK | PRODUCTION-READY | UNKNOWN

---

## 1. OPPORTUNITY / DEAL SYSTEM

### 1.1 `app/models/deal_models.py` — CANONICAL (PARTIAL)

**Status:** PRODUCTION-READY for a real-estate broker agency model.

**Tables:** deals, deal_stage_history, deal_offers, deal_reservations, deal_bookings, deal_commissions, deal_closings, deal_post_sales, deal_documents, deal_approval_requests, deal_commercial_audit_logs

**What it has:**
- Deal entity with DealStage class (opportunity -> negotiation -> offer -> reservation -> booking -> transaction -> commission -> closing -> post_sale)
- Stage history with from_stage, to_stage, transitioned_by, reason, duration_hours
- DealOffer with versioned offer history (JSONB), counter-offer, acceptance tracking
- DealReservation with TTL (expires_at), property FK, agent attribution
- DealBooking with booking reference, payment plan, cancellation
- DealCommission with percentage, splits, payment status
- DealClosing with title deed, registration, handover
- DealApprovalRequest with idempotency, expiry, reviewer attribution
- DealCommercialAuditLog append-only, immutable
- Decimal/Numeric monetary precision (Numeric(20, 4))
- Outbox integration (via _write_outbox in service)

**What it LACKS vs Build 08 spec:**
- No pipeline_id / Pipeline model — stages are hardcoded, not configurable
- No primary_unit_id (unit-level FK, only property-level)
- broker_id is overloaded (org owner + assigned agent) — ambiguous
- No probability / expected_close_at on Deal
- No identity_id / correlation_id separate from lead_id
- No BookingIntent model (separate from DealBooking)
- No canonical SiteVisit — visits are embedded in SchedulingMeeting.meeting_type
- No PropertyShortlist / per-opportunity property comparison history
- No UnitHold canonical model (only calendar MeetingHold for slot locking)
- DealStage is a Python class constant, not a DB-backed configurable entity
- Stage transitions allow forward jumps without validation beyond irreversibility
- lost_reason is a free text field with no controlled vocabulary

**Classification:** CANONICAL (PARTIAL) — Build 08 must EXTEND, not replace.

---

### 1.2 `app/models/transaction_models.py` — LEGACY / DUPLICATE

**Status:** PRODUCTION-RISK

**Tables:** deal_transactions, deal_milestones, deal_payment_schedules

**Issues:**
- Parallel to deal_models.py — two separate Deal-equivalent entities
- Uses Float for monetary fields (agreed_price, commission_percentage) — PRECISION VIOLATION
- 13 "stages" in a string field with no state machine
- DealTransaction is referenced by CRMPipelineService for the Kanban board
- No outbox integration
- No audit trail

**Classification:** LEGACY — must be converged. CRMPipelineService must migrate to Deal model.

---

### 1.3 `app/models/revenue_autopilot_models.py::RevenueOpportunity` — DUPLICATE NAME / DIFFERENT DOMAIN

**Table:** revenue_opportunities

**Issues:**
- RevenueOpportunity is named like a canonical opportunity but is actually an AI-generated action queue
- It has opportunity_type like STALE_HOT_LEAD, SITE_VISIT_FOLLOW_UP — signal types, not pipeline stages
- Not the same entity as Build 08's Opportunity (commercial sales process)
- Referenced by CRMPipelineService (wrong domain coupling)

**Classification:** DUPLICATE name, different domain. Keep as-is for Build 08. Do NOT use as the canonical Opportunity.

---

## 2. PIPELINE / STAGE SYSTEM

### 2.1 `app/models/crm_models.py::PipelineStage` — LEGACY / PARTIAL

**Table:** pipeline_stages

**Issues:**
- Only has: name, order_index, color, is_default, broker_id
- No semantic_type, no SLA, no required_fields, no allowed_actions
- Not linked to Deal.current_stage at all
- Deal.current_stage uses DealStage Python constants, not FK to pipeline_stages
- Two incompatible stage models exist side by side

**Classification:** LEGACY — not connected to the deal lifecycle.

### 2.2 `app/modules/crm/services/crm_pipeline_service.py::STANDARD_PIPELINE_STAGES` — HARDCODED

Issues:
- 11 hardcoded display stages for the Kanban view
- Reads from Lead.pipeline_stage (a string field), not from Deal.current_stage
- Leads and Deals are conflated in the pipeline view
- No backend validation on stage changes

**Classification:** HARDCODED FRONTEND ADAPTER — must be converged to use canonical Deal stages.

---

## 3. APPOINTMENT / CALENDAR SYSTEM

### 3.1 `app/models/calendar_models.py::SchedulingMeeting` — CANONICAL

**Table:** scheduling_meetings

**Status:** PRODUCTION-READY for calendar scheduling. Aliased as Meeting = SchedulingMeeting.

Has: organization_id, broker_id, lead_id, meeting_type, start/end UTC, timezone, location, virtual provider, idempotency_key, external_event_id, outcome, reminders, no-show prediction.

**Missing for Build 08:**
- No opportunity_id FK — meeting not linked to the commercial opportunity
- No appointment_purpose enum (CONSULTATION|PROPERTY_PRESENTATION|SITE_VISIT|FOLLOW_UP|NEGOTIATION|DOCUMENT_REVIEW|BOOKING_MEETING)
- Viewing sub-entity links to property but not to a SiteVisit canonical entity

**Classification:** CANONICAL — Build 08 must ADD opportunity_id column and introduce SiteVisit canonical wrapper.

### 3.2 `app/models/crm_models.py::Meeting` — DUPLICATE / LEGACY

**Table:** meetings

**Issues:**
- Second Meeting table parallel to scheduling_meetings
- Simpler schema (no timezone, no external calendar, no reminders)
- Status uses lowercase vs scheduling_meetings uppercase
- No cross-reference to scheduling_meetings

**Classification:** LEGACY DUPLICATE — mark deprecated.

---

## 4. SITE VISIT SYSTEM — MISSING

Current state: NO CANONICAL SITE VISIT MODEL

Site visit is currently represented as:
- SchedulingMeeting.meeting_type == "SITE_VISIT" — not a first-class entity
- Viewing sub-entity on SchedulingMeeting — has property_id but no check_in/check_out, no attendance, no outcome linked to opportunity
- MeetingOutcome — captures outcome but no opportunity linkage
- Various references to site_visit as a string in workflow taxonomies

**Classification:** MISSING — Build 08 must create canonical SiteVisit model.

---

## 5. NEGOTIATION SYSTEM — PARTIAL

### 5.1 Negotiation in `deal_models.py`

DealOffer carries negotiation state (offer_price, counter_offer_price, status: DRAFT|SUBMITTED|COUNTERED|ACCEPTED|REJECTED). offer_history JSONB preserves historical offers.

**Missing:**
- No Negotiation entity distinct from DealOffer
- No structured customer_offer vs counter_offer vs asking_price as separate records
- Cannot reconstruct full negotiation timeline from JSONB blob

**Classification:** PARTIAL — must extend to NegotiationRound append-only log.

### 5.2 `conversation_intelligence/negotiation_detector.py` — BACKEND-ONLY

Detects negotiation signals in conversations. Does NOT write to any deal/negotiation entity.

**Classification:** PARTIAL — must be wired to create negotiation records.

---

## 6. BOOKING SYSTEM — CANONICAL (PARTIAL)

### 6.1 `app/models/deal_models.py::DealBooking`

**Table:** deal_bookings

Has: booking_reference, booked_price, currency (Decimal), status, payment plan, cancellation.

**Missing:**
- No BookingIntent entity (separate from DealBooking)
- Status vocabulary incomplete — needs: INITIATED|PENDING_DOCUMENTS|PENDING_PAYMENT|PAYMENT_RECEIVED|CONFIRMED|CANCELLED|REFUNDED|COMPLETED
- No inventory_effect — booking doesn't trigger unit state change
- No payment_id FK to payment_models
- No source field

**Classification:** CANONICAL (PARTIAL) — must add BookingIntent + unit inventory integration.

### 6.2 `app/models/deal_models.py::DealReservation` — CANONICAL (PARTIAL)

References property_id (PropertyListing), NOT unit_id (ProjectUnit). No FK to canonical inventory ProjectUnit.

**Classification:** PARTIAL — must add unit_id FK to ProjectUnit.

---

## 7. PAYMENT SYSTEM — CANONICAL (SCOPED TO BILLING)

### 7.1 `app/models/payment_models.py`

**Tables:** payment_orders, payment_transactions, payment_refunds, payment_webhook_events, payment_audit_logs

**Status:** PRODUCTION-READY for Razorpay billing/subscription payments.

**Issues for Build 08:**
- Designed for platform billing (subscription plans), NOT real estate transaction payments
- PaymentOrder.plan_id points to subscription context
- No deal_id or booking_id FK — disconnected from the sales pipeline
- Webhook signature verification should be validated (router-level)

**Classification:** CANONICAL for platform billing. Build 08 needs SEPARATE PropertyPaymentTransaction model linked to DealBooking.

---

## 8. INVENTORY SYSTEM — CANONICAL

### 8.1 `app/models/inventory_models.py`

**Status:** PRODUCTION-READY inventory state machine.

UnitInventoryStatus.VALID_TRANSITIONS enforces: available -> hold -> reserved -> booked -> sold

ProjectUnitStatusLog — append-only status audit trail.

**Issues for Build 08:**
- DealReservation.property_id -> PropertyListing.id (old model), NOT ProjectUnit.id
- No FK from DealBooking to ProjectUnit
- Inventory state change not triggered by booking confirmation
- No hold_id linking a UnitHold to a DealReservation

**Classification:** CANONICAL — Build 08 must add FK bridges from deal models to inventory models.

---

## 9. REVENUE EVENTS — CANONICAL INFRASTRUCTURE

OutboxEvent infrastructure is CANONICAL. Current events emitted by DealService:
deal.created, deal.stage_advanced, deal.offer.submitted, deal.offer.accept/reject/counter, deal.reservation.created, deal.booking.approved, deal.booking.confirmed, deal.closed_won, deal.closed_lost

**Missing event types for Build 08:**
opportunity.created, opportunity.stage_changed, site_visit.completed, booking_intent.created, unit.held, payment.received, booking.cancelled, refund.created, opportunity.won, opportunity.lost

**Classification:** CANONICAL infrastructure — event vocabulary needs extension.

---

## 10. MOCKED / HARDCODED / STUBBED PATTERNS

| Location | Issue | Risk |
|---|---|---|
| calendar/booking/booking_service.py:117 | account_email = "broker@wefylabs.com" hardcoded fallback | LOW — fallback only |
| payment_models.py:amount=Integer | Integer paise for Razorpay | SCOPED — billing only |
| calendar/providers/provider_interface.py | MockCalendarProvider exists | LOW — dev only |
| storage_provider=mock in two models | Mock storage provider default | MEDIUM — must not reach prod |
| EMERGENCY_ALLOW_MOCK_OCR flag | Emergency bypass | MEDIUM — gated |
| DealTransaction.agreed_price=Float | Float precision for money | HIGH — must fix |
| DealPaymentSchedule.amount=Float | Float precision for money | HIGH — must fix |
| crm_pipeline_service.py::total_pipeline_value=float | Float aggregation | MEDIUM — display only |
| STANDARD_PIPELINE_STAGES hardcoded list | Not from DB | MEDIUM |

---

## 11. DUPLICATE / CONFLICTING IMPLEMENTATIONS

| Concept | Implementation 1 | Implementation 2 | Resolution |
|---|---|---|---|
| Meeting/Appointment | crm_models.py::Meeting (table: meetings) | calendar_models.py::SchedulingMeeting (table: scheduling_meetings) | Deprecate meetings, use scheduling_meetings |
| Deal/Opportunity | deal_models.py::Deal | transaction_models.py::DealTransaction | Deprecate DealTransaction, use Deal |
| Opportunity (AI) | deal_models.py::Deal | revenue_autopilot_models.py::RevenueOpportunity | Different domains — keep both, fix naming confusion in Build 09 |
| Pipeline stages | crm_models.py::PipelineStage (DB) | DealStage class constants | Extend DealStage constants; PipelineStage table is unused by Deal |
| Site Visit | SchedulingMeeting.meeting_type=SITE_VISIT | No canonical entity | Create canonical SiteVisit |
| Booking (calendar) | calendar/booking/booking_service.py::BookingService | deal_models.py::DealBooking | Different domains — keep both |
| Hold | deal_models.py::DealReservation | calendar_models.py::MeetingHold | Different domains — DealReservation = inventory hold, MeetingHold = calendar slot hold |

---

## 12. SECURITY FINDINGS

| Attack Vector | Status | Evidence |
|---|---|---|
| Tenant A reads Tenant B deal | PROTECTED | DealService._get_deal_or_raise checks org_id |
| Cross-tenant booking | PROTECTED | BookingService validates lead.organization_id |
| Cross-tenant property | PROTECTED | Property org validation in BookingService |
| Arbitrary stage jump | PARTIAL | advance_stage checks irreversibility but not forward-only policy for all transitions |
| Price manipulation in booking | PARTIAL | DealApprovalRequest gate exists for booking stage |
| Frontend price trust | RISK | submit_offer accepts actor price without re-checking inventory list price |
| Float precision on DealTransaction | HIGH RISK | DealTransaction.agreed_price=Float |

---

## 13. WHAT BUILD 08 MUST CREATE (NET NEW)

1. SiteVisit model — canonical, linked to opportunity_id + SchedulingMeeting.id
2. BookingIntent model — between negotiation and DealBooking
3. PropertyShortlist model — per-opportunity property interest history
4. NegotiationRound model — append-only negotiation history
5. Pipeline model — configurable pipeline configuration (org-level)
6. Build 08 OpportunityStage vocabulary extension to DealStage
7. PropertyPaymentTransaction model — real-estate payment distinct from billing
8. Migration — add opportunity_id to SchedulingMeeting, unit_id to DealReservation/DealBooking
9. Revenue event contracts extension
10. Test suite — test_master_build_08_sales_pipeline.py

## 14. WHAT BUILD 08 MUST CONVERGE (ADAPTERS/DEPRECATION)

1. DealTransaction + DealMilestone + DealPaymentSchedule — DEPRECATE (float precision violations)
2. crm_models.py::Meeting — DEPRECATE (use SchedulingMeeting)
3. PipelineStage DB table — ADAPTER (use DealStage constants for now)
4. CRMPipelineService — MIGRATE from DealTransaction to Deal

---

Audit completed: 2026-09-26 | Classification: VERIFIED IN CODE
