# WefyLabs Phase 1 — Revenue Attribution & Commercial Chain Architecture

**Version**: 1.0.0  
**Status**: Canonical Standard  
**Document**: `PHASE1_REVENUE_ATTRIBUTION.md`

---

## 1. Closed-Loop Commercial Attribution Model

Real estate deals are complex, high-value transactions involving multiple automated and human touchpoints over weeks or months. WefyLabs rejects simplistic single-source or "AI-only" attribution.

The canonical attribution graph connects:

```
[LEAD ACQUIRED]
      ↓
[AUTO QUALIFICATION] (AI: Budget, timeline, intent extraction)
      ↓
[AI PROPERTY MATCH] (Matched against live verified inventory)
      ↓
[COMMUNICATION & FOLLOW-UP] (Automated nurture + Agent outreach)
      ↓
[SITE VISIT] (Scheduled, attended, outcome recorded)
      ↓
[COMMERCIAL OPPORTUNITY] (Deal created with target budget)
      ↓
[OFFER NEGOTIATION] (Multi-round buyer/seller positions)
      ↓
[BOOKING INTENT & HOLD] (Unit secured, deposit pledged)
      ↓
[CONFIRMED BOOKING] (Token verified, inventory locked)
      ↓
[REVENUE REALIZED] (Immutable RevenueEvent recorded)
```

---

## 2. Touchpoint Taxonomy & Evidence Requirements

| Touchpoint Phase | Type | Actor | Data Source & Evidence | Attribution Weighting |
|---|---|---|---|---|
| **Acquisition** | Source | Channel | `leads.source` (`portal`, `whatsapp`, `meta`, `walk_in`) | 15% Baseline |
| **Qualification** | Automated | WefyLabs AI | `scores`, `qualification_logs`, extracted budget & locations | 15% Intent Clarity |
| **Matching** | Automated | Recommendation Engine | `lead_property_interest` (score $\ge 85\%$) | 15% Property Fit |
| **Nurture / SLA** | Hybrid | Dispatcher / Broker | `follow_up_tasks`, `conversations`, SLA response | 15% Speed to Lead |
| **Site Visit** | Human | Sales Agent | `site_visits` with verified outcome record | 20% Field Conversion |
| **Negotiation** | Human / Assisted | Manager / Agent | `negotiation_rounds`, offer gap resolution | 10% Deal Structuring |
| **Closing & Booking**| Human / Financial | Transaction Admin | `booking_intents`, `deal_bookings`, deposit verification | 10% Execution |

---

## 3. Attribution Rules & Guardrails

### 3.1 No Autonomous Financial Claims
WefyLabs AI never claims sole credit for a closed transaction. If an agent conducted 3 site visits and negotiated an offer gap, the system attributes revenue to the **collaborative partnership** of AI enablement and human sales execution.

### 3.2 Time-Decay Window
Touchpoints older than **90 days** without subsequent buyer engagement lose attribution weight unless a renewed commercial action occurs.

### 3.3 Re-Engagement / Recovery Attribution
For dormant leads ($>14$ days inactivity) re-activated by an automated re-engagement workflow:
- The recovery touchpoint is credited **only** if the lead takes a measurable commercial step (replies, books a site visit, submits an offer) within 14 days of the re-engagement dispatch.
- Simply dispatching an unread WhatsApp or email message earns **zero** attribution credit.

---

## 4. Audit Trail & Provenance

Every `RevenueEvent` record in `sales_pipeline` contains:
```json
{
  "event_id": "rev_7f9b8c2e...",
  "organization_id": "org_110293...",
  "opportunity_id": "opp_334211...",
  "lead_id": "lead_992102...",
  "property_id": "prop_882019...",
  "booking_intent_id": "bk_440192...",
  "event_type": "BOOKING_CONFIRMED",
  "amount": "250000.0000",
  "currency": "AED",
  "provenance": {
    "source_channel": "meta_ads",
    "qualification_score": "hot",
    "property_match_score": 92.5,
    "total_site_visits": 2,
    "negotiation_rounds": 3,
    "assigned_agent_id": "broker_441...",
    "closed_at": "2026-09-29T12:00:00Z"
  }
}
```
This guarantees complete end-to-end traceability for every single currency unit moving through WefyLabs.
