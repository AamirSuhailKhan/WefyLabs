# WefyLabs Sales Intelligence, Coaching & Objection OS

## 1. Role-Based Sales Intelligence
WefyLabs structures sales intelligence into three targeted, operational views:
- **Executive Intelligence**: Macro pipeline velocity, realized revenue, gross margin FinOps metrics, channel attribution, and system bottlenecks.
- **Manager Intelligence**: Team workload distribution, stage drop-offs, site visit no-show rates, follow-up SLA risks, and evidence-based coaching insights.
- **Sales User Command**: Prioritized next-best-actions, high-intent follow-up triggers, top property fits for active leads, and personal conversion benchmarking.

## 2. Canonical Objection Intelligence
To eliminate guesswork, buyer hesitations are normalized into a 13-category canonical taxonomy:
```
PRICE | LOCATION | TRUST | TIMING | FINANCING | AVAILABILITY | LAYOUT
AMENITIES | DEVELOPER | LEGAL | POSSESSION | NEGOTIATION | OTHER
```

For every objection raised, the system tracks:
1. `frequency`: Incidence count per 100 qualified conversations.
2. `resolution_rate`: Percentage where customer agreed to move to site visit or offer.
3. `winning_rebuttal`: The specific message template or financial incentive producing successful resolution.
4. `human_vs_ai_efficacy`: Comparative resolution rate between human agents and autonomous copilot.

## 3. Evidence-Backed Coaching Signals
Coaching insights must cite underlying event IDs—never general criticism. Examples:
- **Signal**: `SLOW_FIRST_RESPONSE`
  - *Metric*: Average 28 minutes vs target 5 minutes.
  - *Evidence*: `[evt_lead_01, evt_lead_02]` inbound portal inquiries.
  - *Action*: Configure WhatsApp auto-qualification trigger.
- **Signal**: `UNRESOLVED_PRICE_OBJECTION`
  - *Evidence*: `[evt_conv_33]` customer cited high price per sq ft.
  - *Action*: Offer developer 1% monthly post-handover payment plan.
