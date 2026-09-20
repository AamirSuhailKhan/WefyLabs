# WEFYLABS P0 BACKLOG

| Initiative | Acceptance evidence | Owner action / dependency |
|---|---|---|
| Principal-derived RBAC | Lightweight dependency now resolves membership role server-side and both RBAC paths fail closed without membership; route-by-route adoption remains | auth claim design |
| Tenant policy | Two-tenant integration suite covers leads, properties, matches, opportunities, tasks, calendar, files, analytics, caches, jobs and AI context | staging DB/Redis |
| Schema baseline | `alembic upgrade head` on clean Postgres; model/migration drift report in CI; existing production schema diff reviewed | read-only staging/prod schema |
| Remove duplicate Calendar mount | Unique OpenAPI IDs and one route registration; contract tests remain green | code change |
| Honest delivery/storage | Production rejects mock provider/storage; signed durable media; webhook verification + provider smoke test | storage and channel credentials |
| Canonical identity/dedup | normalized email/phone + merge policy + auditable merge; duplicate-source tests | data ownership decision |
| Async job safety | Every task has tenant input, idempotency key, retry policy and audit record; no `__all__` processing without bounded tenant iteration | Redis/Celery staging |
| AI safety baseline | direct calls routed through facade; input guard, provenance, timeout/cost logs, permissions outside LLM, safe fallback | provider credentials |

Exit condition: no serious customer exposure until each item has code, negative tests, staging runtime proof, and an operational runbook.
