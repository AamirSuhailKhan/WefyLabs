# WefyLabs Phase 1 — Revenue Command Center Design & Specification

**Version**: 1.0.0  
**Target File**: `PHASE1_COMMAND_CENTER.md`  
**Purpose**: Architectural and UX blueprint for the unified home dashboard of WefyLabs CRM.

---

## 1. The Core Purpose: Five Immediate Answers

When a salesperson or sales manager opens WefyLabs, the Revenue Command Center immediately answers five questions:

```
1. WHO NEEDS ATTENTION?      → Action Required Queue (real database entities)
2. WHY?                      → Observable business facts (SLA, matching score, gap)
3. WHAT SHOULD I DO NEXT?    → Next Best Action with safe one-click execution
4. WHAT REVENUE IS MOVING?   → Real-time pipeline, offers, bookings, recorded revenue
5. WHAT HAPPENED AFTER ACT?  → Closed-loop commercial timeline & attribution
```

---

## 2. Command Center Structural Layout

```
┌────────────────────────────────────────────────────────────────────────┐
│ REVENUE COMMAND CENTER — OPERATIONAL COCKPIT                           │
│                                                                        │
│ 🔴 3 SLA Breaches   ⚠️ 5 Overdue Follow-ups   📅 4 Events Today        │
├────────────────────────────────────────────────────────────────────────┤
│ 1. DAILY REVENUE BRIEFING                                              │
│    Top Priority: 3 high-intent leads uncontacted (> 15m)               │
│    Why: Active 90%+ property matches and immediate purchase timeline   │
│    Action: Contact via WhatsApp / Call within 10 minutes               │
├────────────────────────────────────────────────────────────────────────┤
│ 2. ACTION REQUIRED                                                     │
│    [All] [Urgent Leads] [Follow-ups] [Site Visits] [Offers] [At-Risk]  │
│                                                                        │
│    Item Card:                                                          │
│    - Identity: Lead / Deal name & budget                               │
│    - Why Now: Grounded business fact (e.g., "SLA breached by 22 mins") │
│    - Next Best Action: [Call Now] [Schedule Visit] [Review Offer]      │
│    - Snooze / Dismiss controls                                         │
├────────────────────────────────────────────────────────────────────────┤
│ 3. PIPELINE FUNNEL (Canonical Stages)                                  │
│    New → Contacted → Qualified → Site Visit → Offer → Booking → Won    │
│    (Shows Count, Conversion %, and Active Financial Value per Stage)   │
├────────────────────────────────────────────────────────────────────────┤
│ 4. TODAY'S SCHEDULE & OPERATIONAL TIMELINE                             │
│    Morning / Afternoon / Evening chronological event sequence          │
│    - Site Visits, Zoom meetings, scheduled follow-up phone calls       │
├────────────────────────────────────────────────────────────────────────┤
│ 5. REVENUE & COMMERCIAL RISK                                           │
│    Pipeline Value | Active Offers | Booking Intents | Recorded Revenue │
│    + At-Risk Deals & Recoverable Opportunities (with [Re-Engage])      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Section Specifications

### 3.1 Daily Revenue Briefing
- **Source**: `api.commandCenter.getBriefing()` and `api.followups.getDailyBriefing()`
- **Content**:
  - `Top Priority`: The single highest leverage task today
  - `Grounded Rationale`: Business facts explaining why this matters
  - `Target Action`: Specific recommended workflow step
  - `Expected Revenue Impact`: Potential protected or advanced value

### 3.2 Action Required Queue
- **Categorization**:
  - `URGENT`: First-contact SLA breaches, high-intent leads awaiting response.
  - `OVERDUE_FOLLOWUP`: Tasks with `due_at < now`.
  - `UPCOMING_VISIT`: Site visits scheduled in next 2 hours.
  - `OFFER_REVIEW`: Negotiation rounds pending counter-proposal or approval.
  - `AT_RISK_OPPORTUNITY`: Inactive deals with high budget.
- **Strict Data Rule**: Every card represents a live record in PostgreSQL. No hardcoded or placeholder cards.

### 3.3 Next Best Action Execution
Every actionable item surfaces a 1-click execution modal or deep-link:
- `CALL`: Launches phone call / tel URI and pre-opens conversation logger.
- `WHATSAPP / OUTREACH`: Opens AI-drafted, human-reviewed outreach modal.
- `SCHEDULE VISIT`: Opens site visit booking drawer with property pre-selected.
- `REVIEW OFFER`: Opens negotiation modal with asking price, latest offer, and gap.
- `DISMISS / SNOOZE`: Safely defers the item via `POST /api/v1/command-center/items/dismiss` without mutating core CRM entities.

### 3.4 Canonical Pipeline Funnel
- Displays the canonical 6-stage progression:
  1. `New`
  2. `Contacted`
  3. `Qualified`
  4. `Site Visit Scheduled / Completed`
  5. `Negotiation / Offer`
  6. `Booking / Won`
- Clicking any funnel stage filters the underlying records or opens the pipeline board.

### 3.5 Revenue Section
- Clearly separates:
  - **Pipeline Value**: Total open opportunities.
  - **Active Offers**: Formal submitted negotiation amounts.
  - **Booking Value**: Confirmed booking intents holding inventory.
  - **Recorded Revenue**: Actual realized income from `RevenueEvent`.
  - **At-Risk Revenue**: Deals with inactivity signals.

---

## 4. UI/UX & Reliability Standards

1. **Zero-Data State**:
   - If no urgent items exist: "Your priority queue is clear. All leads contacted within SLA."
   - Never display broken empty layouts.
2. **Error State**:
   - If an API fails: Distinct error card with retry button.
   - Never fabricate `0` or fake numbers when an API is unreachable.
3. **Responsive**:
   - Full desktop 3-column layout, compact tablet 2-column, and prioritized 1-column mobile view with priority action cards on top.
4. **Color Urgency Standards**:
   - Red: Critical / SLA Breached
   - Amber: High / Due Soon / Pending Review
   - Teal/Emerald: Clean / Completed / Revenue Won
   - Slate: Medium / Low / Operational info
