# WEFYLABS ARCHITECTURE GAP ANALYSIS

## Current Architecture

The repository is a modular monolith, not microservices: Next.js calls a FastAPI API; SQLAlchemy models persist to configured SQL; Redis/Celery are configured for async work; integrations sit inside the same API process. It is capable of incremental evolution.

Current duplication/ambiguity is the dominant architectural problem:

- Lead scoring exists across `models/score.py`, lead intelligence, predictive, and qualification services.
- Conversation is represented by legacy `Conversation`, `UnifiedConversation`/`UnifiedMessage`, `OmnichannelConversation`/`ChannelMessage`, Copilot messages, and agent state.
- Follow-up models coexist with legacy follow-up and sales-action/autonomous-loop paths.
- Matching/recommendation exists in property recommendation, recommendation models, discovery matching, and AI matching modules.
- AI has an LLM router but direct calls are distributed elsewhere.

## Schema and Data Gaps

The Alembic head is `0026_revenue_autopilot`; model count is materially larger than the migration set and development startup calls `create_all`. This is a schema-drift warning, not proof of drift. Actual PostgreSQL schema was not available. The inspected API-local SQLite file is empty, so it must not be treated as an integration database.

`PropertyListing` is broad but flat: developer/project/building/unit are nullable strings, inventory is a status field, and the tenant alias is `broker_id`. It is not a normalized property graph or an authoritative inventory integration. Price/availability authority needs an explicit update contract and audit trail.

## Security Gaps

1. `require_permission()` defaults to `Role.ADMIN`; permission checks are not intrinsically tied to an authenticated identity.
2. Organization filtering is not proven for every endpoint, worker, cache key, retrieval, file, or AI context.
3. External credentials and real webhooks were not verified. Runtime adapter initialization is not connection verification.
4. Mock media storage loads in the inspected runtime, so message media cannot be claimed durable.

## Reliability Gaps

- Calendar router is included twice in `main.py`, creating duplicate OpenAPI operation IDs.
- Health reported dependencies as “ok/configured” in local execution; that is not end-to-end connection proof.
- Celery schedules scan jobs frequently. Idempotency and tenant scope must be proven per task, especially `__all__` tenant scans.
- Google generative SDK is deprecated at test runtime.

## Architecture Decisions

| Problem | Options | Chosen direction | Reason / migration risk |
|---|---|---|---|
| Authorization | frontend gates; role default; principal-derived dependency | principal-derived backend policy | only independently enforceable choice; staged route migration |
| Tenant scope | broker aliases; ad hoc filters; scoped repository/policy | canonical `organization_id` plus scoped repositories | makes jobs/cache/AI context auditable; data migration needed |
| AI calls | retain direct calls; one gateway | one gateway facade gradually wrapping existing calls | policy, tracing and cost controls; do not rewrite agents first |
| Property facts | LLM/strings; canonical listing with feeds | listing remains authority, eventual normalized inventory domain | protects live facts; migrate incrementally |
| Events | scans only; durable outbox/event table | transactional event/outbox in existing Postgres + Celery | no Kafka needed; requires idempotent consumers |
| Conversations | keep all parallel paths; canonical envelope | choose unified conversation/message as canonical | preserve/import legacy data with adapters |

## Build Order

Foundation → authority/scope → events and deterministic revenue engine → one customer channel → learning/analytics. Do not rewrite FastAPI, Next.js, Postgres, Redis, or Celery; the existing stack is sufficient for the next stages.
