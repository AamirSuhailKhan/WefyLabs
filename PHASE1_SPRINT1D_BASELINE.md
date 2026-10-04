# WefyLabs Phase 1 Sprint 1D — Baseline Audit & System Map

**Date**: 2026-09-29  
**Sprint**: Phase 1 Sprint 1D — Revenue Command Center + Closed-Loop Attribution + Core Revenue Loop Integration  
**Current Commit**: `4bc1a309a522df90fb69477a0715acac3a87c816` docs(phase05): publish Phase 0.5 production acceptance and release certification reports  
**Working Tree Status**: Modified 14 files, 1 untracked component (`FollowUpWorkQueueView.tsx`)  
**TypeScript Status**: 0 errors (`npm run typecheck` passed clean)  
**Backend Pipeline Test Status**: 34/34 tests passed in `apps/api/tests/test_master_build_08_sales_pipeline.py`  
**Command Center Test Status**: 16/16 tests passed in `apps/api/tests/test_part30_api.py`  
**Revenue Autopilot & Intelligence Tests**: All passed in `apps/api/tests/test_part35_api.py` & `test_part11_revenue_intelligence.py`  

---

## 1. Executive Summary

Phase 1 Sprint 1A, 1B, and 1C wired individual capabilities across the revenue lifecycle:
- Lead Creation & Ingestion
- Real-time Auto-Qualification
- SLA / Priority Ranking
- Property Matching Intelligence
- Follow-Up Work Queue & Autopilot
- Site Visit Scheduling & Outcomes
- Multi-Round Offer Negotiation
- Booking Intents & Unit Holds
- Deal OS & Revenue Events

The mission of Sprint 1D is to turn these disparate capabilities into **ONE REVENUE EXECUTION SYSTEM**:
A unified **Revenue Command Center** answering five essential questions:
1. **WHO NEEDS ATTENTION?** (Action Required queue)
2. **WHY?** (Observable business facts)
3. **WHAT SHOULD I DO NEXT?** (Next Best Action with safe execution)
4. **WHAT REVENUE IS MOVING?** (Active Offers, Booking Intents, Realized Revenue vs Pipeline Value)
5. **WHAT HAPPENED AFTER WE ACTED?** (Closed-loop attribution and commercial timeline)

---

## 2. Canonical Frontend Routes (57 Total)

The frontend Next.js 15 App Router contains 57 production routes:
- `/` — Landing page / Marketing
- `/login`, `/register`, `/auth/callback` — Authentication
- `/dashboard` — **The Revenue Command Center** (Target of Sprint 1D consolidation)
- `/dashboard/pipeline` — Canonical pipeline kanban / list
- `/dashboard/leads` — Lead table and management
- `/dashboard/crm/*` — CRM Core (customers, leads, pipeline, tasks, activities)
- `/dashboard/deals` — Deal OS commercial manager
- `/dashboard/follow-ups` — Follow-up automation and queue
- `/dashboard/matching` — AI Property Matching engine
- `/dashboard/revenue-intelligence` — Executive revenue intelligence, leakage & attribution
- `/dashboard/autopilot` — Revenue Autopilot
- `/dashboard/calendar` — Appointments and site visits
- `/dashboard/inventory` & `/dashboard/properties` — Real estate supply & unit management
- `/dashboard/analytics/*` — Analytics, predictions, executive insights
- `/dashboard/lead-capture/*` — Webhook, form, and ingestion hubs
- `/dashboard/settings/*` — Organization settings, team, billing, security
- `/portal/*` — Customer portal & deal rooms

---

## 3. Canonical Backend APIs & Architecture

| Domain | Canonical Router Path | Backend Module | Primary DTOs / Entities |
|---|---|---|---|
| **Command Center** | `/api/v1/command-center` | `apps/api/app/modules/command_center` | `PriorityItemDTO`, `DailyBriefingDTO`, `TodayScheduleItemDTO`, `FirstContactSlaItemDTO` |
| **Sales Pipeline** | `/api/v1/site-visits`, `/offers`, `/booking-intents`, `/revenue-events` | `apps/api/app/modules/sales_pipeline` | `OpportunityStage`, `SiteVisit`, `NegotiationRound`, `BookingIntent`, `RevenueEvent` |
| **Deal OS** | `/api/v1/deal-os` | `apps/api/app/modules/deals` | `Deal`, `DealOffer`, `DealReservation`, `DealBooking` |
| **Revenue Intelligence** | `/api/v1/revenue-intelligence` | `apps/api/app/modules/revenue_intelligence` | `FunnelSummaryDTO`, `RevenueOverviewDTO`, `LeakageReportDTO`, `AttributionReportDTO` |
| **Revenue Autopilot** | `/api/v1/revenue` | `apps/api/app/modules/revenue_autopilot` | `ActionQueueResponseDTO`, `RevenueOpportunityDTO`, `RevenueBriefingDTO` |
| **Follow-Up Automation** | `/api/v1/followups` | `apps/api/app/modules/follow_up` | `FollowUp`, `FollowUpSummary`, `DailyBriefing` |
| **Leads & Qualification**| `/api/v1/leads`, `/scoring` | `apps/api/app/modules/leads`, `lead_qualification` | `Lead`, `Score`, `QualificationState` |

---

## 4. Controlled Vocabularies & Stage Integrity

### 4.1 Canonical Lead Pipeline Stages (`Lead.pipeline_stage`)
Validated by `RegionalPipelineService`:
- `new`
- `contacted`
- `viewing_scheduled`
- `negotiating`
- `closed_won`
- `closed_lost`

### 4.2 Canonical Opportunity Stages (`OpportunityStage`)
In `apps/api/app/models/sales_pipeline_models.py`:
- `NEW`
- `QUALIFIED`
- `PROPERTY_SHORTLISTED`
- `APPOINTMENT_SET`
- `SITE_VISIT_SCHEDULED`
- `SITE_VISIT_COMPLETED`
- `NEGOTIATION`
- `BOOKING_PENDING`
- `BOOKED`
- `WON`
- `LOST`

### 4.3 Canonical Deal Stages (`DealStage`)
In `apps/api/app/models/deal_models.py`:
- `opportunity`
- `negotiation`
- `offer`
- `reservation`
- `booking`
- `transaction`
- `commission`
- `closing`
- `post_sale`

---

## 5. Audit Findings & Known Defects to Resolve

1. **Dashboard View Fragmentation**:
   `apps/web/src/app/dashboard/page.tsx` currently presents 5 distinct view modes (`command_center`, `autopilot`, `followup_queue`, `kanban`, `table`). The user must toggle between views rather than seeing **ONE unified Revenue Command Center** composed of:
   - Daily Revenue Briefing (Top priority, why, recommended action)
   - Action Required (Urgent Leads, Overdue Follow-ups, Site Visits, At-risk Deals)
   - Pipeline Funnel (Real counts and conversions)
   - Today's Timeline (Site visits, appointments, calls)
   - Revenue Section (Pipeline Value vs Active Offers vs Booking Intents vs Recorded Revenue)
   - Revenue Risk & Recovery

2. **Stage ID Casing & Naming Drift**:
   In `KanbanBoard.tsx`, columns were capitalized (`New`, `Contacted`, `Viewing Scheduled`, `Negotiating`, `Closed Won`, `Closed Lost`), whereas DB storage and other components used lowercase (`new`, `contacted`, `viewing_scheduled`, `negotiating`, `closed_won`, `closed_lost`). Drag-and-drop or status updates would cause desynchronization.

3. **Ad-Hoc / Untyped API Calls**:
   `FollowUpWorkQueueView.tsx` utilized an internal raw `fetch` (`callFollowUpAPI`) rather than standard typed bindings on `api.followups`.

4. **Lead Drawer Tab Hierarchy**:
   `LeadDrawer.tsx` had fragmented tabs (`overview`, `matches`, `schedule`, `deal`, `notes`, `tasks`, `chat`). This needs consolidation into:
   - `Overview` (Lead identity, owner, status, intent, SLA, next best action)
   - `Conversation` (Timeline, AI/human message history, channels)
   - `AI Match` (LeadPropertyMatchesPanel with match score, price, availability)
   - `Follow-up` (Follow-up work queue, overdue tasks, scheduled reminders)
   - `Visits` (Site visit history, upcoming visits, outcome recording)
   - `Deal` (Offers, negotiation rounds, booking intent, booking status)
   - `Activity` (System activity & audit log)

5. **Revenue Terminology Conflation Prevention**:
   Pipeline value must never be labeled as realized revenue.
   Booked value must require a valid booking state.
   Recorded revenue must only reflect immutable `RevenueEvent` records.
