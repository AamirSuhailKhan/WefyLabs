# WEFYLABS — REVENUE INTELLIGENCE OPERATING SYSTEM (PART 11)
**Architectural Specification, Canonical Metrics, 15-Category Leakage Engine, Source Attribution & Learning Loop**

---

## 1. System Architecture & Conceptual Flow

WefyLabs transforms from an operational CRM into the **Real Estate AI Revenue Operating System**. Revenue Intelligence acts as the analytical brain and feedback loop that turns raw operational events and business outcomes into explainable, actionable revenue optimization:

```
CHANNELS (Web, Meta, Google, Portal, CSV, Manual)
      ↓
INGESTION & IDENTITY RESOLUTION
      ↓
LEAD INTELLIGENCE & QUALIFICATION
      ↓
PROPERTY INTELLIGENCE & MATCHING
      ↓
CONVERSATION & FOLLOW-UP AUTOMATION
      ↓
APPOINTMENT & SITE VISIT EXECUTION
      ↓
OPPORTUNITY PROGRESSION (Revenue Autopilot)
      ↓
BOOKING & DEAL TRANSACTIONS (Authoritative Revenue)
      ↓
CANONICAL REVENUE INTELLIGENCE LAYER
   ├─ Funnel Progression & Advancement Rates
   ├─ 15-Category Operational Leakage Radar
   ├─ Source Attribution & True Channel ROI
   ├─ Outcome Tracking & Feedback Capture
   ├─ Deterministic Learning Loop (Heuristic v1)
   ├─ Data Quality & Governance Audit Panel
   └─ Revenue Copilot Tools for AI Workforce
      ↓
FUTURE PREDICTIVE & CALIBRATION FOUNDATIONS
```

### Core Architectural Mandate
- **Non-Authoritative Read Layer**: Revenue Intelligence is strictly an observational engine. It never overwrites or mutates domain entities (`leads`, `properties`, `scheduling_meetings`, `deal_transactions`, `revenue_opportunities`).
- **Authoritative Sources**:
  - Lead State & Identity → `leads`, `customers`
  - Property Pricing & Inventory → `properties`
  - Bookings & Appointments → `scheduling_meetings`
  - Financial & Deal State → `deal_transactions`, `revenue_opportunities`
- **Zero Fabrication**: All conversion rates, win rates, and stage velocities require explicit denominators. If the sample size is zero, values return `null` (`None` in Python), never synthetic `0%` or `100%`. All pipeline metrics carry the `_estimate` suffix.

---

## 2. Canonical Funnel Representation & Metrics

The system maps all lead stages into a standardized 6-stage canonical revenue funnel:

| Stage Name | Canonical ID | Definition / Entry Criteria | Dropoff Identification |
| :--- | :--- | :--- | :--- |
| **New Lead** | `new` | Ingested lead awaiting initial qualification or engagement | SLA breach if uncontacted > SLA hours |
| **Contacted** | `contacted` | Initial communication sent/attempted | No response or stalled before qualification |
| **Qualified** | `qualified` | Met budget, location, property type, and timeline criteria | Qualified without active follow-up scheduled |
| **Site Visit** | `site_visit` | Physical viewing or property tour scheduled/in-progress | No-show, cancelled, or visit without debrief |
| **Negotiation** | `negotiation` | Active deal, commercial offer, or contract drafting | Stalled deal beyond stage dwell SLA |
| **Converted** | `converted` | Signed booking, closed transaction, or recorded revenue | Closed-won authoritative outcome |

### Funnel Metrics Formulas
- **Stage Count**: Total leads currently in or advanced through stage $S$ within the date window:
  $$N_S = \sum \mathbb{I}(\text{lead.stage} = S)$$
- **Advancement Rate**:
  $$\text{Rate}_{S \to S+1} = \begin{cases} \frac{N_{S+1}}{N_S} \times 100 & \text{if } N_S > 0 \\ \text{null} & \text{if } N_S = 0 \end{cases}$$
- **Overall Win Rate**:
  $$\text{WinRate} = \begin{cases} \frac{N_{\text{converted}}}{N_{\text{total}}} \times 100 & \text{if } N_{\text{total}} > 0 \\ \text{null} & \text{if } N_{\text{total}} = 0 \end{cases}$$
- **Pipeline Value Estimate**:
  $$\text{PipelineEstimate} = \sum_{l \in \text{ActiveQualified}} l.\text{budget\_max}$$
- **Confirmed Revenue**:
  $$\text{Revenue} = \sum_{d \in \text{CompletedDeals}} d.\text{estimated\_commission\_amount}$$

---

## 3. The 15-Category Operational Revenue Leakage Engine

Revenue leakage is classified deterministically into 15 specific operational failure categories:

| Category Code | Default Severity | Detection Condition / Rule | Recommended Next Action |
| :--- | :--- | :--- | :--- |
| `NEW_LEAD_NO_RESPONSE` | **CRITICAL** | `stage = 'new'` & age > 24 hours without contact attempt | "Initiate immediate contact attempt via phone/chat" |
| `QUALIFIED_NO_FOLLOWUP` | **HIGH** | `stage = 'qualified'` & updated > 3 days ago with no pending task | "Schedule priority follow-up task for qualified buyer" |
| `MATCH_WITHOUT_CONTACT` | **HIGH** | Lead has >3 high-confidence property matches but no outreach in 5 days | "Present matched properties shortlist to buyer" |
| `APPOINTMENT_NOT_CONFIRMED`| **HIGH** | Meeting scheduled within next 24 hours with `status = 'REQUESTED'` | "Send appointment confirmation reminder to lead" |
| `APPOINTMENT_NO_SHOW` | **HIGH** | Meeting passed scheduled end time with `status = 'NO_SHOW'` | "Reach out to reschedule missed appointment" |
| `SITE_VISIT_NO_DEBRIEF` | **CRITICAL** | Meeting completed > 24 hours ago without recorded feedback outcome | "Conduct site visit debrief and record buyer interest" |
| `HOT_LEAD_GOING_COLD` | **HIGH** | Lead score = 'hot' but inactive > 5 days | "Trigger re-engagement outreach with newly listed units" |
| `STALLED_OPPORTUNITY` | **HIGH** | Revenue opportunity in active status without stage update > 14 days | "Conduct pipeline review and advance or disqualify opportunity" |
| `LOST_AFTER_HIGH_INTENT` | **CRITICAL** | Lead reached `site_visit` or `negotiation` then marked lost | "Conduct loss interview to document price/timing/inventory objection" |
| `REPEATED_UNSUCCESSFUL_FOLLOWUP` | **MEDIUM** | > 4 contact attempts without customer response | "Transition to automated long-term nurturing cadence" |
| `SOURCE_QUALITY_PROBLEM` | **MEDIUM** | Source with > 20 leads but 0% conversion past qualified | "Review channel campaign targeting and intake validation" |
| `MATCH_QUALITY_PROBLEM` | **MEDIUM** | High match count with repeated buyer rejections | "Recalibrate buyer requirement profile preferences" |
| `AI_RECOMMENDATION_FAILURE`| **MEDIUM** | Multiple AI recommendations dismissed or overridden by broker | "Calibrate agent recommendation threshold & criteria weights" |
| `HUMAN_ACTION_FAILURE` | **MEDIUM** | Action assigned to representative past SLA without execution | "Reassign action item to secondary broker on duty" |
| `WORKLOAD_RISK` | **LOW** | Agent active lead capacity exceeds threshold (> 50 uncontacted) | "Balance lead intake routing across available team members" |

---

## 4. Lead Source Attribution Framework

Attribution connects revenue outcomes back to acquisition origins without fabricating causality:

1. **First-Touch Attribution**: Credits the channel that brought the lead into the system.
2. **Last-Touch Attribution**: Credits the channel of the most recent interaction prior to conversion.
3. **Linear Attribution**: Distributes credit evenly across all recorded touchpoints in the event log.

### Attribution Tracking Metrics
- **Total Leads per Source**
- **Converted Leads per Source**
- **True Conversion Rate %** (with explicit sample size $N$)
- **Attributed Pipeline Value (Estimate)**
- **Attribution Coverage %**:
  $$\text{Coverage} = \frac{\text{Leads with identifiable source}}{\text{Total Leads}} \times 100$$
- **Unattributed Revenue Bucket**: Surfaced explicitly so data blind spots are never hidden.

---

## 5. Outcome Tracking & The Deterministic Learning Loop

The system tracks every interaction and recommendation through an outcome loop:
$$\text{Observe} \longrightarrow \text{Recommend} \longrightarrow \text{Action} \longrightarrow \text{Outcome} \longrightarrow \text{Feedback} \longrightarrow \text{Evaluate}$$

### Heuristic Scoring (`heuristic_v1`)
Rather than black-box machine learning, Part 11 implements the auditable `heuristic_v1` formula:
- Recency Weight: $+20$ pts for contact within 24 hours; decays $-5$ pts per week of inactivity.
- Qualification Weight: $+25$ pts for fully declared budget, timeline, and location.
- Engagement Weight: $+15$ pts for attended site visit or appointment.
- Match Depth Weight: $+15$ pts for verified shortlisted property units.
- Deal Stage Weight: $+25$ pts for active negotiation.
- Maximum Score: $100.0$ pts. Full mathematical breakdown returned with every propensity score.

---

## 6. Data Quality & Completeness Audit Panel

Revenue Intelligence provides real-time governance over underlying CRM records:
1. **Missing Source Attribution** (Severity: HIGH)
2. **Missing Budget Parameters** (Severity: HIGH)
3. **Missing Contact Timestamps** (Severity: CRITICAL)
4. **Deals Missing Value / Commission** (Severity: CRITICAL)
5. **Site Visits Missing Outcome Debrief** (Severity: HIGH)
6. **Overall Data Health Score %**:
   $$\text{HealthScore} = \left( 1 - \frac{\text{Total Missing Fields}}{\text{Total Required Fields Audited}} \right) \times 100$$

---

## 7. Security & Multi-Tenant Boundary Controls

1. **Strict Organization Scoping**: All database queries enforce `WHERE organization_id = :org_id`.
2. **Server-Side Authentication**: Auth token strictly verified via `get_current_broker`; client-supplied tenant overrides are rejected.
3. **Audit Trails**: Every recomputation and snapshot capture writes an auditable record with timestamps and caller identities.
4. **PII Minimization**: Analytics endpoints return aggregated IDs and metrics, never raw customer chat transcripts or payment tokens.

---

## 8. Versioned REST API Endpoints

Base URL: `/api/v1/revenue-intelligence`

| HTTP Method | Route | Description | Response Model |
| :--- | :--- | :--- | :--- |
| `GET` | `/overview` | High-level realized revenue, pipeline estimates, revenue at risk | `RevenueOverviewDTO` |
| `GET` | `/funnel` | Canonical 6-stage funnel counts and step advancement rates | `FunnelSummaryDTO` |
| `GET` | `/leakage` | Stage dropoffs, staleness breakdown, total value at risk | `LeakageReportDTO` |
| `GET` | `/leakage/items` | Itemized leakage records across 15 failure categories | `List[ExtendedLeakageItemDTO]` |
| `GET` | `/attribution` | Channel and source conversion performance | `AttributionReportDTO` |
| `GET` | `/sources` | Alias for lead sources performance | `AttributionReportDTO` |
| `GET` | `/opportunities`| Active opportunity volume and evaluation summary | `JSON Object` |
| `GET` | `/outcomes` | Outcome taxonomy distribution and true win rates | `OutcomeSummaryDTO` |
| `GET` | `/actions` | Learning loop action effectiveness summary | `LearningLoopSummaryDTO` |
| `GET` | `/learning-loop`| Canonical learning loop summary | `LearningLoopSummaryDTO` |
| `GET` | `/data-quality` | Entity completeness audit and health score | `DataQualityReportDTO` |
| `GET` | `/team` | Agent operational throughput and activity metrics | `TeamIntelligenceDTO` |
| `GET` | `/journey/{lead_id}` | Chronological journey for an individual buyer | `LeadRevenueJourneyDTO` |
| `GET` | `/property/{property_id}` | Conversion journey and demand for a listing | `PropertyRevenueJourneyDTO` |
| `GET` | `/propensity/{lead_id}` | Deterministic heuristic propensity calculation | `PropensityScoreDTO` |
| `POST`| `/snapshots/capture` | Capture or refresh point-in-time funnel snapshot | `FunnelSnapshotDTO` |
| `GET` | `/snapshots` | Retrieve historical snapshots for trend graphs | `SnapshotListDTO` |
| `POST`| `/recompute` | Trigger full deterministic recomputation | `JSON Object` |

---

## 9. AI Workforce & Revenue Copilot Tools Integration

All 12 Revenue Copilot tools are registered in the Workforce tool registry (`app.modules.ai_agent.tool_executor.registry.TOOLS`), assigned to `REVENUE_COPILOT` and `MANAGER_COMMAND_AGENT`, and executed through `ToolExecutor`:
1. `get_revenue_overview`
2. `get_funnel_metrics`
3. `get_leakage_summary`
4. `get_source_attribution`
5. `get_opportunity_flow`
6. `get_action_effectiveness`
7. `get_outcome_history`
8. `get_data_quality`
9. `get_lead_revenue_journey`
10. `get_property_conversion_history`
11. `get_agent_action_history`
12. `get_revenue_at_risk`

---

## 10. Future Predictive Roadmap

- **Phase 1 (Current - Part 11)**: Deterministic heuristic intelligence (`heuristic_v1`), 15-category operational leakage radar, true conversion rates with explicit denominators, and multi-touch attribution.
- **Phase 2 (Upcoming)**: Statistical cohort survival models measuring lead stage half-life and velocity distributions ($P_{25}, P_{50}, P_{75}$).
- **Phase 3 (Enterprise ML)**: Supervised win propensity models trained on tenant-isolated outcome datasets, with explicit calibration curves ($Brier$ score) and automated feature drift detection.
