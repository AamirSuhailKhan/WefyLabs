# WefyLabs Phase 1 Sprint 1D — Revenue Metric Contract

**Version**: 1.0.0  
**Status**: Canonical Production Standard  
**Scope**: All backend aggregations, analytics engines, API contracts, and frontend dashboards across WefyLabs CRM & Revenue Intelligence.

---

## 1. Core Financial Principles

1. **Precision**: All financial calculations MUST use arbitrary-precision decimals (`Decimal` in Python, numeric types in SQL). Floating-point arithmetic is prohibited for currency.
2. **Zero vs Unknown**: An absence of data or a failure to compute is NEVER coerced to `0` or `0.00`. If a calculation fails or has an undefined denominator, it returns `null` / `None`. `0` strictly indicates an evaluated zero.
3. **Double Counting Prevention**:
   - `Pipeline Value` is an estimate of future potential; it is NEVER added to `Recorded Revenue`.
   - `Booking Value` is committed inventory value under reservation; it is NEVER added to `Recorded Revenue` until a verified `RevenueEvent` occurs.
   - `Influenced Revenue` is an attribution attribution tag, NOT a separate additive ledger line.
4. **Tenant Isolation**: Every financial query must filter strictly by `organization_id`. Cross-tenant data aggregation is an immediate security breach.

---

## 2. Canonical Revenue Metrics

### 2.1 Pipeline Value (`pipeline_value`)
- **Definition**: The total estimated gross transaction value of all open, active opportunities and leads within the sales pipeline.
- **Source of Truth**: `deals.agreed_price` or `deals.offer_price` or `leads.budget_max` for active deals where `status = 'ACTIVE'` and `current_stage NOT IN ('closing', 'post_sale', 'closed_lost')`.
- **Formula**: $\sum (\text{deal.agreed\_price} \lor \text{deal.offer\_price} \lor \text{lead.budget\_max})$
- **Filters**: `status = 'ACTIVE'`, non-terminal stages.
- **Edge Cases**: Where both `agreed_price` and `budget_max` exist, `agreed_price` takes precedence. If `budget_max` is null, use `budget_min`. If both null, value is 0.

### 2.2 Active Offer Value (`offer_value`)
- **Definition**: The total value of active, unexpired purchase or lease offers currently under negotiation with buyers or sellers.
- **Source of Truth**: `negotiation_rounds` where round is latest for the opportunity and `status = 'pending_approval'` or `status = 'submitted'`, OR `deal_offers` where `status = 'ACTIVE'`.
- **Formula**: $\sum (\text{round.offered\_price})$

### 2.3 Booking Value (`booked_value`)
- **Definition**: Gross transaction value associated with verified booking intents or reservations where a deposit/token has been pledged or accepted, but final transaction completion is pending.
- **Source of Truth**: `booking_intents` where `status = 'CONFIRMED'` or `DealBooking` where `status = 'CONFIRMED'`.
- **Formula**: $\sum (\text{booking\_intent.agreed\_price})$
- **Guardrail**: Booking Value MUST NOT be reported as Recorded Revenue.

### 2.4 Recorded Revenue (`recorded_revenue`)
- **Definition**: Irreversible, verified revenue realized by the organization as confirmed by transactions and immutable revenue events.
- **Source of Truth**: `revenue_events` where `event_type IN ('BOOKING_CONFIRMED', 'COMMISSION_RECEIVED', 'DEAL_CLOSED_WON')`.
- **Formula**: $\sum (\text{revenue\_event.amount})$
- **Audit Requirement**: Every unit of Recorded Revenue must link to a valid `organization_id`, `deal_id` or `opportunity_id`, `actor_id`, and `recorded_at` timestamp.

### 2.5 Influenced Revenue (`influenced_revenue`)
- **Definition**: Recorded revenue or booked value from deals where WefyLabs AI or automated workflows performed an actionable intervention (e.g., auto-qualification, property match dispatch, automated follow-up nurture, re-engagement) that preceded the deal closing.
- **Source of Truth**: Closed-loop join between `revenue_events` and `audit_logs` / `outbox_events` matching `lead_id` with an automated action within 90 days of closing.
- **Formula**: $\sum (\text{revenue\_event.amount})$ WHERE $\exists \text{ touchpoint} \in \{\text{AI qualification}, \text{AI match}, \text{Autopilot dispatch}\}$

### 2.6 Recovered Revenue (`recovered_revenue`)
- **Definition**: Revenue derived from opportunities or leads that were previously classified as dormant, stale (no activity > 14 days), or lost, and were successfully re-activated by an automated re-engagement campaign resulting in a site visit, offer, or booking.
- **Strict Limitation**: Generating or sending an AI re-engagement message does NOT constitute recovered revenue. Revenue is only credited as recovered once a site visit is completed, a booking is made, or revenue is recorded.

### 2.7 Revenue at Risk (`revenue_at_risk`)
- **Definition**: Potential transaction value tied to leads or opportunities exhibiting high-risk leakage signals:
  - First contact SLA breached on high-intent lead
  - Stalled negotiation (no activity > 7 days)
  - Expiring booking intent (< 12 hours remaining without token confirmation)
  - Completed site visit without recorded next action > 48 hours
- **Formula**: $\sum (\text{opportunity.value} \times \text{risk\_weight})$

---

## 3. Operational KPI Contracts

| Metric | Definition | Numerator | Denominator | Filters & Exclusions |
|---|---|---|---|---|
| **Response Time** | Median minutes from lead creation to first logged communication | $\sum (\text{first\_contact\_time} - \text{created\_at})$ | Count of contacted leads | Exclude manual imports marked as legacy |
| **Qualification Rate** | % of inbound leads evaluated as qualified (score = hot/warm) | Count of qualified leads | Total inbound leads created | Exclude spam and test leads |
| **Match Rate** | % of qualified leads with at least 1 verified property match ($\ge 80\%$) | Leads with $\ge 1$ match $\ge 80\%$ | Total qualified leads | Active inventory pool only |
| **Follow-Up Compliance** | % of scheduled follow-ups executed within 2 hours of due date | Follow-ups executed on-time | Total follow-ups due | Exclude snoozed/dismissed tasks |
| **Site Visit Rate** | % of qualified leads that complete a physical or virtual site visit | Leads with completed site visit | Total qualified leads | Terminal lost leads before visit excluded |
| **Offer Conversion Rate** | % of site visits that produce a formal offer | Unique visits leading to offer | Total completed site visits | Deduplicate multiple visits per buyer |
| **Booking Rate** | % of active offers that advance to confirmed booking | Confirmed bookings | Total valid offers submitted | Withdrawn offers excluded |

---

## 4. Cohort & Population Consistency

- Funnel conversion rates must use a single population definition:
  - When measuring conversion between Stage $N$ and Stage $N+1$, the denominator must be the population that successfully entered Stage $N$.
  - Rates are never calculated across mismatched date windows or un-scoped organizational boundaries.
