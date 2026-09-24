# WEFYLABS — PART 9 ATTRIBUTION MAP
## End-to-End Revenue Provenance & Attribution Traceability

This document traces the complete lifecycle of customer acquisition and revenue provenance across the WefyLabs Operating System, documenting how attribution is captured, preserved, and carried through downstream conversion stages.

```
SOURCE
  ↓ [IMPLEMENTED]
LEAD
  ↓ [IMPLEMENTED]
CUSTOMER (IDENTITY)
  ↓ [IMPLEMENTED]
CONVERSATION
  ↓ [IMPLEMENTED]
PROPERTY (INTEREST / MATCH)
  ↓ [IMPLEMENTED]
APPOINTMENT (CALENDAR)
  ↓ [IMPLEMENTED]
SITE VISIT (ITINERARY)
  ↓ [IMPLEMENTED]
OPPORTUNITY (DEAL)
  ↓ [IMPLEMENTED]
BOOKING (TRANSACTION)
  ↓ [IMPLEMENTED]
REVENUE (COMMISSION)
```

---

### Detailed Provenance Traceability Matrix

| Stage | From Node | To Node | Status | Implementation Details |
| :--- | :--- | :--- | :--- | :--- |
| **1. Ingestion** | **SOURCE** | **LEAD** | **IMPLEMENTED** | Captured via `UniversalIntakeService`. Origin (`WEBSITE`, `PAID_AD`, `CSV`, `API`, `WEBHOOK`) recorded in `Lead.source` and `SourceAttribution.channel` / `provider`. First-touch UTMs permanently recorded in `source_attributions`. |
| **2. Identity Linking** | **LEAD** | **CUSTOMER** | **IMPLEMENTED** | Linked via `IdentityLink` (`link_method="intake_ingestion"`, `confidence=1.0`) connecting canonical `Lead.id` to permanent `Identity.id`. Prevents identity fragmentation across repeat submissions. |
| **3. Conversational Context** | **CUSTOMER** | **CONVERSATION** | **IMPLEMENTED** | Omnichannel conversations (`OmnichannelConversation`) store `lead_id` and `organization_id`. In conversational lead capture, anonymous web visitor session is atomically linked to newly created canonical `Lead`. |
| **4. Property Matching** | **CONVERSATION** | **PROPERTY** | **IMPLEMENTED** | `LeadPropertyInterest` and `PropertyRecommendationService.generate_recommendations` link property inventory (`PropertyListing`) to `lead_id`. Extracted requirements (BHK, budget, location) feed deterministic matching. |
| **5. Appointment Scheduling** | **PROPERTY** | **APPOINTMENT** | **IMPLEMENTED** | `Meeting` / calendar slots record `lead_id`, `property_id`, and `broker_id`. SLA tasks (15-min first response) enforce scheduling speed. |
| **6. Site Visit** | **APPOINTMENT** | **SITE VISIT** | **IMPLEMENTED** | `ViewingItinerary` records physical property tours, linking `lead_id`, `property_id`, and viewing feedback. |
| **7. Revenue Opportunity** | **SITE VISIT** | **OPPORTUNITY** | **IMPLEMENTED** | `RevenueAutopilotEngine` evaluates high-intent leads and generates `RevenueOpportunity` records tied to `lead_id` and `organization_id`. |
| **8. Deal Booking** | **OPPORTUNITY** | **BOOKING** | **IMPLEMENTED** | Deal pipeline transitions (`PipelineStageEnum`) track progression to `closed_won` with explicit transaction value. |
| **9. Revenue Realization** | **BOOKING** | **REVENUE** | **IMPLEMENTED** | Brokerage commission attribution computed from deal value, preserving the original acquisition source (`utm_source`, `channel`, `campaign`) in `SourceAttribution`. |

---

### Attribution Immutability Guarantees

1. **First Touch Preservation**:
   - `SourceAttribution.first_touch_at` is set at initial lead ingestion and never modified.
   - `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`, and `landing_page` from initial acquisition remain immutable.

2. **Last Touch Enrichment**:
   - Subsequent submissions by the same customer update `SourceAttribution.last_touch_at`.
   - Re-engagement activity logged in `activities` table with latest touch metadata without erasing first-touch provenance.

3. **Multi-Touch Reporting Readiness**:
   - Every acquisition attempt is recorded in `LeadAcquisitionEvent` with cryptographic idempotency key, timestamp, and raw payload snapshot.
