# PHASE 1 — REVENUE OUTCOME TAXONOMY

**Sprint**: Phase 1 Sprint 1E  
**Status**: Canonical Reference  

---

## 1. Taxonomy Approach

This document maps:
1. What Sprint 1E requires as commercial outcome events (from the master prompt)
2. What already exists in `OutcomeEventType` (92 types in `intelligence_models.py`)
3. What exists in `RevenueEventType` (sales_pipeline_models.py — operational events)
4. The `StandardDomainEvents` (event_bus.py)
5. The final canonical mapping and any gaps

---

## 2. Sprint 1E Required Outcome Events (from spec)

The specification requires tracking:

```
LEAD_CREATED
LEAD_IDENTIFIED
LEAD_CONTACTED
LEAD_RESPONDED
LEAD_QUALIFIED
PROPERTY_MATCHED
PROPERTY_SHARED
FOLLOWUP_SCHEDULED
FOLLOWUP_EXECUTED
SITE_VISIT_SCHEDULED
SITE_VISIT_ATTENDED
SITE_VISIT_NO_SHOW
SITE_VISIT_CANCELLED
OFFER_CREATED
OFFER_NEGOTIATED
OFFER_ACCEPTED
BOOKING_INTENT_CREATED
BOOKING_CONFIRMED
DEAL_WON
DEAL_LOST
REVENUE_RECORDED
LEAD_RECOVERED
DEAL_RECOVERED
```

---

## 3. Existing OutcomeEventType Enum (intelligence_models.py)

The `OutcomeEventType` enum already contains 92 event types. Mapped against spec requirements:

| Spec Event | OutcomeEventType Match | Status |
|:---|:---|:---:|
| `LEAD_CREATED` | Not directly present; `OPPORTUNITY_CREATED` exists | ⚠️ Partial |
| `LEAD_IDENTIFIED` | Not present | ➕ Add |
| `LEAD_CONTACTED` | Not present | ➕ Add |
| `LEAD_RESPONDED` | `MESSAGE_REPLIED` (close match) | ⚠️ Approximate |
| `LEAD_QUALIFIED` | `LEAD_QUALIFIED` | ✅ Exact |
| `PROPERTY_MATCHED` | `PROPERTY_MATCH_ACCEPTED` / `PROPERTY_MATCH_REJECTED` | ✅ Covered |
| `PROPERTY_SHARED` | Not present | ➕ Add |
| `FOLLOWUP_SCHEDULED` | `APPOINTMENT_BOOKED` (broader) | ⚠️ Approximate |
| `FOLLOWUP_EXECUTED` | `FOLLOWUP_COMPLETED` | ✅ Exact |
| `SITE_VISIT_SCHEDULED` | `APPOINTMENT_CONFIRMED` (broader) | ⚠️ Approximate |
| `SITE_VISIT_ATTENDED` | `SITE_VISIT_COMPLETED` | ✅ Exact |
| `SITE_VISIT_NO_SHOW` | `SITE_VISIT_NO_SHOW` | ✅ Exact |
| `SITE_VISIT_CANCELLED` | `APPOINTMENT_CANCELLED` (broader) | ⚠️ Approximate |
| `OFFER_CREATED` | `OFFER_CREATED` | ✅ Exact |
| `OFFER_NEGOTIATED` | Not present | ➕ Add |
| `OFFER_ACCEPTED` | `OFFER_ACCEPTED` | ✅ Exact |
| `BOOKING_INTENT_CREATED` | `BOOKING_CREATED` (broader — includes confirmed) | ⚠️ Approximate |
| `BOOKING_CONFIRMED` | `BOOKING_CREATED` (needs distinction) | ⚠️ Approximate |
| `DEAL_WON` | Not present (only `OPPORTUNITY_LOST` exists) | ➕ Add |
| `DEAL_LOST` | `OPPORTUNITY_LOST` | ✅ Exact (rename alias) |
| `REVENUE_RECORDED` | `REVENUE_REALIZED` | ✅ Exact |
| `LEAD_RECOVERED` | `LEAD_REACTIVATED` | ✅ Exact |
| `DEAL_RECOVERED` | Not present | ➕ Add |

---

## 4. Existing RevenueEventType Constants (sales_pipeline_models.py)

These are the operational event strings used in `RevenueEvent.event_type`:

```python
OPPORTUNITY_CREATED      = "opportunity.created"
OPPORTUNITY_STAGE_CHANGED = "opportunity.stage_changed"
OPPORTUNITY_WON          = "opportunity.won"
OPPORTUNITY_LOST         = "opportunity.lost"
SITE_VISIT_COMPLETED     = "site_visit.completed"
SITE_VISIT_NO_SHOW       = "site_visit.no_show"
OFFER_CREATED            = "offer.created"
OFFER_ACCEPTED           = "offer.accepted"
BOOKING_INTENT_CREATED   = "booking_intent.created"
UNIT_HELD                = "unit.held"
UNIT_HOLD_RELEASED       = "unit.hold_released"
BOOKING_CREATED          = "booking.created"
BOOKING_CONFIRMED        = "booking.confirmed"
BOOKING_CANCELLED        = "booking.cancelled"
PAYMENT_RECEIVED         = "payment.received"
PAYMENT_FAILED           = "payment.failed"
REFUND_ISSUED            = "refund.issued"
DEAL_WON                 = "deal.won"
DEAL_LOST                = "deal.lost"
```

---

## 5. Canonical Mapping Decision

### 5.1. Reuse Without Change

These `OutcomeEventType` values are sufficient and MUST be reused:

| Canonical Name | Source | Use For |
|:---|:---|:---|
| `LEAD_QUALIFIED` | OutcomeEventType | Lead passes qualification policy |
| `LEAD_DISQUALIFIED` | OutcomeEventType | Lead fails qualification |
| `LEAD_REACTIVATED` | OutcomeEventType | Previously lost/stale lead re-engages |
| `LEAD_CHURNED` | OutcomeEventType | Lead permanently lost without deal |
| `PROPERTY_MATCH_ACCEPTED` | OutcomeEventType | Buyer accepts a property recommendation |
| `PROPERTY_MATCH_REJECTED` | OutcomeEventType | Buyer rejects a property recommendation |
| `PROPERTY_SHORTLISTED` | OutcomeEventType | Property added to shortlist |
| `PROPERTY_VISITED` | OutcomeEventType | Physical/virtual property visit completed |
| `PROPERTY_BOOKED` | OutcomeEventType | Property booking confirmed |
| `MESSAGE_REPLIED` | OutcomeEventType | Lead replies to any outbound message |
| `MESSAGE_IGNORED` | OutcomeEventType | No reply to outbound message |
| `FOLLOWUP_COMPLETED` | OutcomeEventType | Scheduled follow-up was executed |
| `FOLLOWUP_IGNORED` | OutcomeEventType | Follow-up skipped/ignored by agent |
| `FOLLOWUP_OVERDUE` | OutcomeEventType | Follow-up exceeded SLA |
| `APPOINTMENT_BOOKED` | OutcomeEventType | Site visit / meeting appointment booked |
| `APPOINTMENT_CONFIRMED` | OutcomeEventType | Appointment confirmed by both parties |
| `APPOINTMENT_CANCELLED` | OutcomeEventType | Appointment cancelled |
| `APPOINTMENT_NO_SHOW` | OutcomeEventType | Customer no-show |
| `SITE_VISIT_COMPLETED` | OutcomeEventType | Site visit completed |
| `SITE_VISIT_NO_SHOW` | OutcomeEventType | Buyer no-show at site visit |
| `SITE_VISIT_RESCHEDULED` | OutcomeEventType | Site visit rescheduled |
| `OPPORTUNITY_CREATED` | OutcomeEventType | New commercial opportunity created |
| `OPPORTUNITY_ADVANCED` | OutcomeEventType | Opportunity moved to a later stage |
| `OPPORTUNITY_STALLED` | OutcomeEventType | Opportunity paused or inactive |
| `OPPORTUNITY_LOST` | OutcomeEventType | Opportunity closed as lost |
| `OFFER_CREATED` | OutcomeEventType | Formal offer submitted |
| `OFFER_ACCEPTED` | OutcomeEventType | Offer accepted by buyer/seller |
| `OFFER_REJECTED` | OutcomeEventType | Offer rejected |
| `BOOKING_CREATED` | OutcomeEventType | Booking intent created (pre-hold) |
| `BOOKING_CANCELLED` | OutcomeEventType | Booking cancelled |
| `REVENUE_REALIZED` | OutcomeEventType | Final revenue event recorded |
| `AI_ACTION_ACCEPTED` | OutcomeEventType | Agent accepted AI recommendation |
| `AI_ACTION_REJECTED` | OutcomeEventType | Agent rejected AI recommendation |
| `AI_ACTION_OVERRIDDEN` | OutcomeEventType | Agent overrode AI action |
| `AI_ACTION_IGNORED` | OutcomeEventType | Agent ignored AI recommendation |
| `OBJECTION_RAISED` | OutcomeEventType | Customer raised a sales objection |
| `OBJECTION_RESOLVED` | OutcomeEventType | Objection resolved with response |
| `OBJECTION_UNRESOLVED` | OutcomeEventType | Objection left unresolved |

### 5.2. New Types to Add to OutcomeEventType

These are missing and required. They will be added as an **extension** to the existing enum — NOT replacing any existing values:

| New Event Type | Rationale | Maps From |
|:---|:---|:---|
| `LEAD_FIRST_CONTACTED` | Marks the precise first agent contact with a lead | `StandardDomainEvents.LEAD_ASSIGNED` + first message |
| `LEAD_RESPONDED_FIRST` | First buyer response — key SLA learning signal | First inbound message after assignment |
| `PROPERTY_SHARED` | Property deck/details shared with buyer | `StandardDomainEvents.PROPERTY_SHARED` |
| `OFFER_NEGOTIATED` | Counter-offer round (negotiation in progress) | `NegotiationRound` with counter-offer |
| `BOOKING_INTENT_CONFIRMED` | Booking intent confirmed and unit hold created | `BookingIntent.CONFIRMED` |
| `DEAL_WON` | Final deal won with revenue event | `RevenueEventType.DEAL_WON` |
| `DEAL_RECOVERED` | Lost deal recovered and re-opened | Re-opened opportunity from LOST |
| `NBA_GENERATED` | Next Best Action recommendation generated | Command center priority card creation |
| `NBA_ACTED_UPON` | Agent acted on a specific NBA | Agent executed the recommended action |
| `NBA_EXPIRED` | NBA recommendation expired without action | TTL exceeded on priority card |
| `FOLLOWUP_SCHEDULED` | Follow-up explicitly scheduled | Work item creation in queue |
| `REVENUE_ATTRIBUTED` | Revenue attribution calculation completed | Attribution job completion |
| `DATA_QUALITY_ISSUE` | Data quality issue detected | `DataQualityScanner` detection |

---

## 6. Event → Learning Chain

Each operational event should produce:
1. An `OutcomeEvent` record (the factual what happened)
2. A `SalesOutcomeEdge` record (the graph edge: what came before, what comes next)
3. A `FunnelTransitionRecord` if the event represents a funnel stage change
4. An `AIActionOutcome` update if the event was triggered by an AI recommendation

---

## 7. Correlation Fields

Every `OutcomeEvent` must carry, where applicable:

| Field | Purpose |
|:---|:---|
| `lead_id` | Primary commercial entity |
| `opportunity_id` | Linked Deal/Opportunity |
| `property_id` | Related property (if applicable) |
| `agent_id` | Agent who performed or authorized the action |
| `channel` | Communication channel (WHATSAPP, EMAIL, PHONE, IN_PERSON) |
| `source_event_id` | FK to the operational event that triggered this outcome |
| `source_table` | The table/model that was the source of truth |
| `occurred_at` | Business timestamp (NOT system capture time) |
| `captured_at` | System ingestion time (auto-set) |
| `metadata_json` | Context-specific data (reason, property score, SLA elapsed, etc.) |

---

## 8. Anti-Fabrication Rules

1. **Never record an OutcomeEvent without a `source_event_id` or `source_table`**. Every learning signal must be traceable.
2. **`occurred_at` must use the operational timestamp** (e.g., `SiteVisit.completed_at`) — not `datetime.now()` of the recording call.
3. **Revenue-related OutcomeEvents must have `revenue_impact`** sourced from `RevenueEvent.amount` — never estimated.
4. **No AI model may create OutcomeEvents for outcomes that have not been observed**. Prediction is separate from outcome recording.
5. **`outcome_score` must be NULL unless derived from a documented formula** — never a random float.

---

## 9. Taxonomy Governance

- This taxonomy is **versioned**. Changes require adding new types (never removing or renaming existing ones).
- Any new `OutcomeEventType` must have: definition, source, population, time window, tenant scope, and test coverage.
- Deprecated event types are marked with a `DEPRECATED_` prefix in metadata but kept in the enum.
