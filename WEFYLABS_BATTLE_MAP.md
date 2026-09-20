# WEFYLABS BATTLE MAP

Evidence key: C = code; T = selected tests (30 passing); R = local in-process runtime. “Competitor benchmark” is intentionally capability-level only; no subjective ranking was performed.

| Capability | Current implementation | Evidence | Competitor benchmark | Gap | Risk | Business impact | Effort | Priority | Dependency |
|---|---|---|---|---|---|---|---|---|---|
| Lead CRM | Models/routes/UI | C,T | CRM CRUD + ownership | canonical ownership unclear | tenant/RBAC | high | M | P0 | auth scope |
| Property CRM | flat `PropertyListing` + media/history | C | live inventory graph | no normalized developer/project/unit graph | stale facts | high | L | P1 | property authority |
| Matching | recommendation + AI matching modules | C,T | explainable ranked alternatives | multiple paths/canonical engine unproven | mismatch | high | M | P1 | identity/property |
| Qualification | facts/policy/conversation modules | C | structured qualification | real LLM and policy outcomes unverified | hallucinated extraction | high | M | P1 | AI gateway |
| Follow-up | policies/sequences/executions/Celery | C | SLA, consent, overrides | runtime workers unverified | duplicate sends | high | M | P0 | delivery/tenant |
| Revenue Autopilot | opportunities, scans, UI/tests | C,T | actionable revenue risk queue | production outcome loop absent | false automation | high | M | P1 | canonical events |
| Customer AI | agent/communication modules | C | grounded customer agent | no live channel + inventory proof | unsafe promise | high | L | P1 | gateway/handoff |
| Human handoff | escalation/takeover models/services | C | history/context transfer | end-to-end channel verification absent | lost context | high | M | P1 | unified conversation |
| Calendar | booking/holds/providers | C | live availability and booking | dev uses mock; provider unverified | double-booking | high | M | P1 | OAuth/provider |
| Omnichannel | adapters/queues | C,R(mock storage) | reliable two-way channels | credentials and delivery unverified | false delivery | high | L | P0 | provider activation |
| RAG | knowledge models/workers/pgvector SQL | C | grounded citations | retrieval-to-response unverified | hallucination | medium | M | P2 | storage/vector |
| Identity/dedup | identity/discovery modules | C,T(selected) | canonical contact merge | global coverage unproven | duplicate lead actions | high | M | P0 | tenant model |
| Analytics | BI/CRM intelligence/UI | C | funnel-to-revenue attribution | source/revenue links unverified | bad decisions | medium | M | P2 | canonical events |
| Billing | Razorpay code/UI | C | payment + entitlement enforcement | live webhooks/plan gates unverified | entitlement bypass | medium | M | P1 | RBAC/webhooks |
| RBAC | role map exists | C | backend action authorization | defaults admin | critical exposure | critical | M | P0 | authenticated principal |
| Tenant isolation | org/member models/tests | C,T | all resources/jobs/cache scoped | property and async proof absent | data leakage | critical | L | P0 | policy layer |
| Storage | media abstraction | C,R | durable signed object storage | runtime is mock | data loss | medium | M | P0 | storage provider |

## Exact Top 10 Engineering Initiatives

1. **P0: Replace default-admin RBAC dependency with authenticated principal + permission checks.** Dependency: session/JWT claims. Value: prevents unauthorized operations. Risk: compatibility. Effort: M.
2. **P0: Tenant-scope audit and enforcement middleware/repositories.** Dependency: canonical organization ID. Value: prevents cross-tenant leakage. Risk: broad query changes. Effort: L.
3. **P0: Establish Alembic-to-Postgres schema baseline and CI drift gate.** Dependency: staging schema access. Value: prevents deployment failures/data corruption. Risk: migration repair. Effort: M.
4. **P0: Make delivery and media truthful.** Disable mock success in non-demo paths; provision storage; verify provider webhooks. Dependency: secrets/accounts. Value: trustworthy outreach. Effort: M.
5. **P0: Consolidate and test canonical lead identity + deduplication.** Dependency: tenant policy. Value: eliminates duplicate actions. Effort: M.
6. **P1: Name one property authority and inventory update workflow.** Dependency: property data source. Value: reliable recommendations. Effort: L.
7. **P1: Consolidate matching into one deterministic, explainable engine.** Dependency: buyer preferences/property authority. Value: conversion relevance. Effort: M.
8. **P1: Introduce one governed AI gateway and retire/broker direct calls.** Dependency: permission/context policy. Value: safe and observable AI. Effort: L.
9. **P1: Prove a single channel-to-human-handoff vertical slice.** Dependency: delivery, conversation model, calendar. Value: appointment conversion. Effort: L.
10. **P2: Build canonical events and funnel attribution from outcomes.** Dependency: above source-of-truth choices. Value: measurable learning. Effort: L.

## What Not to Build Yet

- Voice, additional social channels, or a second CRM/property model.
- Kafka, microservices, Kubernetes expansion, another vector DB, or generic “MLOps.”
- More AI agents before authorization, grounding, channel delivery, handoff, and outcomes are verified.
- Cross-tenant learning; it needs legal basis, anonymization, opt-out, and governance.
