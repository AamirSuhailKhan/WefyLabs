# WEFYLABS PART 17 — ENTERPRISE PRODUCTION RUNTIME BASELINE
# Architecture Reality Audit & Operational Baseline

---

## 1. Executive Summary

WefyLabs is an AI-native Real Estate Revenue Operating System.
This audit establishes the concrete, verified architectural baseline of the repository prior to the execution of **Part 17: Enterprise Production Runtime**.

All claims in this document have been verified against active source code, SQLAlchemy models, Alembic migrations, Celery tasks, test runners, and configuration modules.

---

## 2. Verified Baseline Metrics

| Metric | Verified Value | Evidence |
|---|---|---|
| **Alembic Migration Head** | `0029_native_crm_indexes` | `alembic current` / `alembic heads` (Single head) |
| **Backend Test Suite (Milestone)** | 418 / 418 PASSED (100%) | Parts 1–3, 6–14, 16, 35 |
| **Full Repo Test Suite** | 1,897 passed, 1 skipped, 0 failures | Full regression test run across 40+ suites |
| **TypeScript Strict Compilation** | 0 errors | `npx tsc --noEmit` in `apps/web` |
| **Next.js Production Build** | 37 / 37 routes compiled | Next.js production build |
| **Pydantic V2 Deprecation Warnings** | 0 in application codebase | Migrated all DTOs and Schemas to `ConfigDict` |
| **Active Python Version** | 3.14 (Local Environment) | Python runtime |
| **ORM / Engine** | SQLAlchemy 2.0 Async (`asyncpg` / `aiosqlite`) | `apps/api/app/database.py` |
| **Cache & Distributed Queue** | Redis / Celery 5.x | `apps/api/app/celery_app.py` |
| **Primary AI Provider** | Google Gemini (`gemini-3.5-flash`) | Strict: Google Gemini is sole active provider |
| **External Communication Status** | WhatsApp disabled; Brevo/SMTP configured | Hard kill-switches active |
| **CRM System of Record** | WefyLabs Native CRM (Part 14) | Zero external CRM dependency |

---

## 3. Architecture Reality

```
Client Tier: Next.js 14 Web (37 routes, TypeScript strict)
    │
    ▼ (HTTP / JSON / Supabase JWT / X-WefyLabs-Organization-Id / X-Request-ID)
API Gateway Tier: FastAPI (apps/api/app/main.py)
    ├── Middleware Stack: Observability, Correlation, SecurityHeaders, Tracing, Idempotency, CORS
    ├── Health Probes: /health/liveness, /health/readiness, /health
    └── Routers: 40+ modular domain routers (/api/v1/*)
    │
    ├── Database Tier: PostgreSQL + asyncpg (NullPool in tests, 10-conn pool in prod)
    │     └── 490+ SQLAlchemy models across 25 domain modules
    │
    ├── Cache Tier: Redis (Key-value, sliding window rate limiting)
    │     └── Graceful fallback to in-memory on Redis disconnect
    │
    ├── Worker Tier: Celery (30+ task queues, Celery Beat periodic schedules)
    │     └── Redis broker & backend, task routes for knowledge, calendar, CRM, predictive
    │
    └── AI Tier: Google Gemini Gateway (AI Workforce: 8 canonical roles, token budgets, safety matrix)
```

---

## 4. Current Isolation Model & Gaps

### Current State
1. **Tenant Resolution**:
   - `get_current_tenant` in `app/dependencies.py` resolves `TenantContext(organization_id)` via JWT + server-side DB query on `OrganizationMember`.
   - Client header `X-WefyLabs-Organization-Id` allows selecting between valid memberships, but is validated server-side against authorized memberships.
   - If user has multiple memberships and provides no header, a 409 Conflict is raised (fail-closed).
2. **Entity Scoping**:
   - Models inherit either `TenantMixin` (`organization_id`, `workspace_id`) or have `broker_id` (legacy foundation).
   - In Part 14, Native CRM bridged `broker_id` and `organization_id` to ensure customer identity isolation.
3. **Current Risks & Gaps (Addressed in Part 17)**:
   - No `ContextVar`-based ambient tenant context for deep service layers and background tasks.
   - Background tasks must pass `tenant_id` explicitly; if omitted or untrusted, risk of cross-tenant task execution exists.
   - Cache keys in Redis do not universally follow a standardized tenant-namespaced pattern `wefylabs:{tenant_id}:{subsystem}:{key}`.

---

## 5. Background Jobs & Worker Architecture

### Current State
- `celery_app.py` defines 30+ dedicated queues: `lead_queue`, `webhook_queue`, `ai_queue`, `calendar-sync`, `prediction`, `workflow-execution`, etc.
- Celery Beat schedule contains 18 periodic tasks (e.g. `evaluate-followups-periodic`, `monitor-sla-breaches`, `refresh-active-lead-predictions`).

### Current Risks & Gaps (Addressed in Part 17)
- **Overlapping Periodic Tasks**: When multiple Celery workers run, Celery Beat periodic triggers can be consumed concurrently without distributed lock protection, leading to redundant work or race conditions.
- **Task Classification**: Tasks lack explicit reliability tiers (`CRITICAL`, `IMPORTANT`, `BEST_EFFORT`) with tuned retry limits and jittered exponential backoff.
- **Transactional Outbox**: Currently, side-effects (e.g. notifications, AI dispatch, webhook retries) are dispatched in application code outside of domain DB transactions. If DB commits but dispatch fails (or vice versa), state can drift.

---

## 6. Current Database & Reliability Model

### Current State
- `app/database.py` manages an async engine with `pool_pre_ping=True`, `pool_recycle=1800`.
- NullPool is used under test runners to prevent connection leaks across event loops.
- Current Alembic head is `0029_native_crm_indexes`.

### Current Risks & Gaps (Addressed in Part 17)
- No `outbox_events` table exists to guarantee atomic domain-to-event transitions.
- Check-then-act patterns in high-concurrency ingestion can race if unique constraints are not enforced.
- Database query timeouts are set on asyncpg (`command_timeout=20`), but need explicit testing under concurrency.

---

## 7. Current Observability, Health & SecOps

### Current State
- `/metrics` exposes Prometheus text format metrics via `ObservabilityTracingMiddleware`.
- `/health/liveness` returns 200 process alive.
- `/health/readiness` checks DB `SELECT 1` and Redis `PING`.
- `/health` provides deep operator status.

### Current Risks & Gaps (Addressed in Part 17)
- Health endpoints lack `/health/live`, `/health/ready`, and `/health/deep` path standardization.
- Deep health check does not inspect Celery worker health, Beat schedule health, or Alembic migration head alignment.
- Security event taxonomy (`AUTH_FAILURE`, `AUTHZ_FAILURE`, `RATE_LIMIT`, `INVALID_WEBHOOK`, `TENANT_BOUNDARY_VIOLATION`, etc.) is not centralized into a dedicated SecOps logger and metrics collector.

---

## 8. What Part 17 Will Change

1. **Transactional Outbox Engine (`OutboxEvent`)**:
   - Add `outbox_events` model, migration (`0030_enterprise_runtime`), and transactional outbox service.
   - Atomically record events within the same DB transaction as business entities.
2. **Distributed Redis Lock & Beat Safety**:
   - Introduce safe distributed locking with TTL, randomized ownership tokens, and automatic release.
   - Singleton task execution decorator to prevent duplicate/overlapping Celery periodic jobs.
3. **Multi-Tier Tenant-Aware Rate Limiting**:
   - `PUBLIC`, `AUTHENTICATED`, `AI_EXPENSIVE`, `ADMIN`, `WEBHOOK`, `BACKGROUND` tiers with graceful in-memory fallback.
4. **Enhanced Health Architecture**:
   - Standardized `/health/live`, `/health/ready`, `/health/deep` reporting DB, Redis, Celery, and Alembic migration status.
5. **AI Runtime Safety & Cost Governance**:
   - Global and per-tenant AI concurrency semaphores, circuit breakers with fallback, and PII-free token/cost tracking.
6. **SecOps Event Taxonomy & Redaction**:
   - Centralized security event emitter and PII log redaction filter.
7. **Comprehensive Test Suites**:
   - `test_part17_security.py` (Tenant isolation, RBAC, IDOR, token tampering)
   - `test_part17_concurrency.py` (Ingestion races, appointment booking races, distributed lock races)
   - `test_part17_reliability.py` (Redis outage fallback, DB retry, circuit breakers, outbox retry)
   - `test_part17_scale.py` (Practical local load and throughput benchmarking)
8. **Operational Runbooks & Matrices**:
   - Disaster recovery runbook with verified/unverified classifications.
   - Incident response runbook, security incident runbook, failure mode matrix, production dependency matrix.

---

## 9. What Part 17 Intentionally Will NOT Change

1. **Will NOT Rebuild Parts 1–16**: All existing features (CRM, Revenue Intelligence, AI Workforce, Predictive Engine, Lead Acquisition, Communication Hub) remain intact.
2. **Will NOT Introduce Unnecessary Infrastructure**: No Kubernetes manifests, no external data warehouses, no extra databases.
3. **Will NOT Activate WhatsApp or Razorpay LIVE**: Safety kill-switches remain strictly enforced.
4. **Will NOT Store Chain-of-Thought or Log Secrets**: Zero secrets in logs, zero raw credentials stored.
5. **Will NOT Modify Shipped Alembic Migrations**: All schema changes will be additive via new migration `0030_enterprise_runtime`.

---
_Baseline certified by Enterprise Architecture & Production Readiness Owner. Date: 2026-09-24._
