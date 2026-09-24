# WEFYLABS PART 14 — NATIVE CRM OPERATIONS MANUAL
============================================================
**Standard Operating Procedures, Lead Workflows & Lifecycle Governance**
*WefyLabs Revenue Operating System*

---

## 1. Core Operator Daily Workflow

The native WefyLabs CRM is engineered for maximum operator velocity and decision efficiency.

```
                  OPEN CRM DASHBOARD
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
  INSPECT "MY WORK"                      REVIEW ALERTS
(Today's appts, Overdue tasks)         (SLA Risks, Hot Leads)
       │                                       │
       └───────────────────┬───────────────────┘
                           ▼
                 OPEN CUSTOMER 360
         (Read preferences, inspect budget)
                           │
                           ▼
                VIEW PROPERTY MATCHES
      (Check suitability scores & explanations)
                           │
                           ▼
               TAKE OPERATIONAL ACTION
    (Send message via Comm Hub / Schedule Visit)
                           │
                           ▼
                  LOG ACTIVITY & NOTE
      (Document call debrief, objections, next step)
                           │
                           ▼
                ADVANCE PIPELINE STAGE
   (NEW -> CONTACTED -> QUALIFIED -> APPOINTMENT...)
                           │
                           ▼
             REVENUE INTELLIGENCE UPDATES
     (Funnel velocity, win rate, attribution logged)
```

---

## 2. Lead Lifecycle & Stage Transition Rules

### 2.1 Canonical Stages
1. **NEW**: Fresh lead acquired via Meta Ads, Google Ads, manual entry, or API.
2. **CONTACTED**: Initial outreach initiated via Communication Hub (Email/Web Chat).
3. **ENGAGED**: Two-way customer dialogue established.
4. **QUALIFIED**: Budget, timeline, property type, and transaction intent verified by AI or agent.
5. **MATCHED**: Curated property recommendations dispatched to customer.
6. **APPOINTMENT**: Phone or video consultation confirmed on calendar.
7. **SITE_VISIT**: Physical property viewing scheduled and attended.
8. **OPPORTUNITY**: Buyer demonstrates commercial intent for a specific property listing.
9. **NEGOTIATION**: Offer submitted, terms under negotiation, escrow/deposit drafted.
10. **BOOKING**: Reservation fee deposited, booking form executed.
11. **WON / LOST**: Transaction closed and commission recorded, or lost with structured reason.

### 2.2 Controlled Backward Transitions
Sales interactions frequently require regression (e.g. from `NEGOTIATION` back to `QUALIFIED` if loan financing falls through). Backward transitions are supported but **strictly audited**:
- Every transition creates an `Activity` record with `old_stage`, `new_stage`, and `reason`.
- Every transition emits an immutable `AuditLog` entry.
- Domain event `lead.stage_changed` notifies Revenue Intelligence to compute accurate cycle times and prevent false velocity metrics.

---

## 3. Team Assignment & Reassignment Workflow

1. **Auto-Routing**: Inbound leads are auto-routed using the Part 13 SLA and territory routing rules.
2. **Manual Reassignment**:
   - A manager or agent reassigns the lead to a target broker within the organization.
   - The system verifies the target broker exists, is active, and belongs to the same organization.
   - An activity of type `ASSIGNMENT` is generated documenting `old_broker_id`, `new_broker_id`, and `reason`.
   - AuditLog is recorded with full actor identity.

---

## 4. Tasks, Activities & Notes Governance

### 4.1 Tasks
- **Creation**: Tasks originate from humans, AI agents (e.g. Follow-Up Assistant), or Revenue Autopilot.
- **Priority Rules**:
  - `CRITICAL`: Stalled high-value deal or SLA expiration imminent.
  - `HIGH`: Site visit follow-up or escrow agreement delivery.
  - `NORMAL`: General inquiry or reminder.
  - `LOW`: Routine housekeeping or contact detail verification.
- **Overdue Determination**: Evaluated strictly on the server: `status != 'completed'` and `due_at < now()`.

### 4.2 Activities vs Events
- **Activity**: Authoritative operational business record (e.g. "Called customer", "Sent contract draft", "Attended site visit").
- **Event**: Low-level canonical telemetry signal (e.g. `lead.stage_changed`, `message.delivered`).

### 4.3 Notes
- Rich-text briefing documents authored by operators or AI assistants.
- Visibility levels: `INTERNAL` (confidential internal notes) and `TEAM` (shared across brokerage team).
- AI summaries cannot silently overwrite human notes; all AI-generated notes carry `AI_GENERATED` provenance.

---

## 5. Safe Bulk Operations

To protect tenant databases against accidental bulk corruption:
1. **Batch Size Limit**: Hard ceiling of 100 records per operation.
2. **Atomic Verification**: Every lead ID in the batch is pre-verified for tenant ownership. Unauthorized IDs cause immediate batch rejection (HTTP 403) with zero partial writes.
3. **Allowed Bulk Operations**:
   - `change_stage`: Moves verified batch to target pipeline stage.
   - `change_priority`: Updates score (`hot`, `warm`, `cold`).
   - `assign`: Bulk reassigns batch to a designated broker within the organization.
4. **Auditability**: Records total targets, successes, failures, and correlation IDs in `AuditLog`.
