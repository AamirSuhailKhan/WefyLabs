# WefyLabs Phase 1 Sprint 1D — System Architecture & Integration Blueprint

**Version**: 1.0.0  
**Target File**: `PHASE1_SPRINT1D_ARCHITECTURE.md`

---

## 1. Architectural Mission

Unify the existing subsystem capabilities implemented across Sprint 1A, 1B, and 1C into a single, cohesive, enterprise-grade **Revenue Execution System**.

```
[LEAD CREATION & INGESTION]
          ↓
[AUTO-QUALIFICATION WORKER]
          ↓
[PRIORITY & SLA RANKING ENGINE]
          ↓
[AI PROPERTY MATCHING ENGINE]
          ↓
[AUTONOMOUS FOLLOW-UP QUEUE]
          ↓
[SITE VISIT SCHEDULER & OUTCOMES]
          ↓
[DEAL OS & OFFER NEGOTIATIONS]
          ↓
[BOOKING INTENTS & UNIT HOLDS]
          ↓
[IMMUTABLE REVENUE EVENT LOG]
          ↓
[REVENUE COMMAND CENTER (UNIFIED DASHBOARD)]
```

---

## 2. Component Integration Matrix

| Subsystem | Existing Canonical Location | Role in Command Center |
|---|---|---|
| **Command Center Engine** | `apps/api/app/modules/command_center` | Central aggregator for priority queue, SLA items, today's schedule, inventory intelligence, and morning briefings. |
| **Sales Pipeline OS** | `apps/api/app/modules/sales_pipeline` | Manages site visits, negotiation rounds, offers, booking intents, unit holds, and revenue events. |
| **Deal OS** | `apps/api/app/modules/deals` | Commercial lifecycle: opportunity, negotiation, reservation, booking, commission, closing. |
| **Revenue Intelligence** | `apps/api/app/modules/revenue_intelligence` | Calculates funnel conversion rates, revenue at risk, leakage detection, source attribution, and learning loops. |
| **Revenue Autopilot** | `apps/api/app/modules/revenue_autopilot` | Evaluates action triggers, generates outreach drafts, demand intelligence, and feedback learning. |
| **Follow-Up Automation** | `apps/api/app/modules/follow_up` | Follow-up rules, scheduling, dispatch queue, suppression logic, and daily briefing. |
| **Lead Qualification** | `apps/api/app/modules/lead_qualification` | Asynchronous Celery qualification worker, intent extraction, and qualification policy evaluation. |

---

## 3. Data Flow & Event Spine

All major commercial transitions emit an `OutboxEvent` and append an immutable entry to `audit_logs` and `revenue_events`:

1. `LEAD_CREATED`:
   - Emitted by lead ingestion controller.
   - Subscriber dispatches Celery task `auto_qualify_new_lead_task`.
   - Lead score updated to `hot` / `warm` / `cold`.
   - Command Center SLA timer initialized (15 min default).

2. `SITE_VISIT_RECORDED`:
   - Sales agent logs visit outcome (`completed`, `interested`, `not_interested`, `no_show`).
   - If `interested`: Triggers deal creation or property shortlisting; surfaces "Prepare Offer" in Command Center.
   - If `not_interested`: Triggers "Send Alternative Property" recommendation.

3. `OFFER_SUBMITTED`:
   - Negotiation round logged with offered price and actor (`buyer` or `seller`).
   - Command Center surfaces "Offer Review Required" for manager approval.

4. `BOOKING_CONFIRMED`:
   - Unit hold converted to confirmed booking intent.
   - `RevenueEvent(event_type='BOOKING_CONFIRMED', amount=deposit)` emitted.
   - Dashboard increments `Booked Value` and records attribution.

5. `REVENUE_RECORDED`:
   - Deal moves to `closing` / `closed_won`.
   - Immutable `RevenueEvent` persists final transaction amount.
   - Dashboard reflects verified `Recorded Revenue`.

---

## 4. Security, Multi-Tenancy & RBAC

1. **Multi-Tenancy Guardrail**: Every query includes `organization_id == current_broker.organization_id`.
2. **Role Boundaries**:
   - `ADMIN / OWNER`: Full command center view, company-wide revenue metrics, approval rights on high-value offers, team performance analytics.
   - `AGENT`: Personalized command center view ("My Urgent Leads", "My Follow-Ups", "My Visits", "My Deals"), execution of calls and messages, outcome logging.
   - `READ_ONLY`: View-only access without execution or dismissal actions.
