# WEFYLABS PART 17 — ENTERPRISE PRODUCTION RUNTIME ARCHITECTURE
# Technical Specification & Hardening Architecture

---

## 1. Architectural Philosophy

Part 17 hardens the existing WefyLabs platform into a resilient, enterprise-grade multi-tenant runtime.
It does **NOT** reinvent or duplicate Parts 1–16. It fortifies the foundation with:
1. **Zero-Trust Multi-Tenancy**: ContextVar-backed `TenantContext`, server-derived memberships, and IDOR assertions at all boundaries.
2. **Transactional Outbox Consistency**: Atomically recording side-effects inside the domain database transaction, eliminating dual-write failure modes.
3. **Cluster-Safe Background Automation**: Distributed Redis locks with randomized tokens preventing overlapping Celery Beat runs across multi-worker deployments.
4. **Multi-Tier Rate Limiting**: Dedicated quotas for `PUBLIC`, `AUTHENTICATED`, `AI_EXPENSIVE`, `ADMIN`, `WEBHOOK`, and `BACKGROUND` workloads with graceful in-memory fallback.
5. **AI Runtime Safety & Cost Governance**: Concurrency semaphores, circuit breakers with half-open canaries, and token/cost accounting without storing customer prompts.
6. **Unified Health Probes & Diagnostics**: Standardized `/health/live`, `/health/ready`, and `/health/deep` reporting DB latency, Redis latency, Alembic migration head, and Outbox queue health.

---

## 2. Component Architecture Diagram

```
                                  Client Request
                                        │
           ┌────────────────────────────┴────────────────────────────┐
           ▼                                                         ▼
    Public Endpoints                                       Protected Endpoints
 (Lead Capture / Health)                                   (CRM / AI / Revenue)
           │                                                         │
   [PublicCaptureGuard]                                      [get_current_tenant]
  - Honeypot Verification                                   - Server-side membership validation
  - Anti-replay freshness                                   - TenantContext with contextvars
  - Prompt injection filter                                 - IDOR ownership assertions
           │                                                         │
           └────────────────────────────┬────────────────────────────┘
                                        │
                           [Tiered Rate Limiter]
                      (PUBLIC, AUTHENTICATED, AI_EXPENSIVE,
                       ADMIN, WEBHOOK, BACKGROUND)
                                        │
                                        ▼
                               FastAPI Route Handler
                                        │
                    ┌───────────────────┴───────────────────┐
                    ▼                                       ▼
             Domain Operations                       AI Operations
         (Leads, Deals, Calendar)                (AI Workforce, Copilot)
                    │                                       │
                    │                             [AIRuntimeGovernor]
                    │                            - Global & tenant semaphores
                    │                            - Circuit breaker (OPEN/CLOSED)
                    │                            - PII-free token & cost tracker
                    ▼                                       │
            SQLAlchemy AsyncSession                         ▼
        ┌───────────────────────────────┐             Google Gemini
        │  1. Business Entity Mutation   │
        │  2. OutboxEvent Atomically     │
        │     Recorded in same TX       │
        └───────────────────────────────┘
                        │
                        ▼ (Database Commit)
                 [PostgreSQL DB]
                        │
                        ▼ (Polled or Dispatched)
                 [OutboxService]
                        │ (Retry with AWS full jitter backoff)
                        ▼
               [Celery Task Queues]
          (lead_queue, ai_queue, etc.)
                        │
                        ▼
               [Distributed Lock]
          (Singleton task execution)
```

---

## 3. Core Modules Introduced in Part 17

| Module | Location | Purpose |
|---|---|---|
| **Outbox Models** | `apps/api/app/models/outbox_models.py` | `OutboxEvent` declarative model & status enums |
| **Outbox Service** | `apps/api/app/infrastructure/outbox/outbox_service.py` | Transactional event recording, backoff dispatch, DLQ |
| **Alembic Migration** | `apps/api/alembic/versions/0030_enterprise_runtime.py` | Schema migration for `outbox_events` and composite indexes |
| **Distributed Lock** | `apps/api/app/common/redis/distributed_lock.py` | Redis SET NX EX distributed locking & singleton decorator |
| **Task Reliability** | `apps/api/app/common/tasks/reliability.py` | Reliability tier matrix (`CRITICAL`, `IMPORTANT`, `BEST_EFFORT`) |
| **Multi-Tier Limiter** | `apps/api/app/common/redis/rate_limiter.py` | 6 rate limit tiers with tenant namespacing & in-memory fallback |
| **Tenant Guard** | `apps/api/app/infrastructure/security/tenant_guard.py` | Anti-IDOR ownership assertions and tenant cache keying |
| **SecOps Taxonomy** | `apps/api/app/infrastructure/security/secops.py` | Security event logger, metrics, and incident ring buffer |
| **PII Redaction** | `apps/api/app/common/logger/redaction.py` | Scrubbing emails, phones, passwords, and tokens from logs |
| **AI Governor** | `apps/api/app/modules/ai_agent/safety/runtime_governor.py` | AI concurrency semaphore, circuit breaker, cost tracker |
| **Public Guard** | `apps/api/app/modules/lead_acquisition/security/public_guard.py` | Honeypot traps, replay defense, prompt injection neutralization |
| **Integrity Diagnostic**| `apps/api/app/modules/diagnostics/integrity_checker.py` | Non-destructive read-only DB diagnostic suite |
| **Health Probes** | `apps/api/app/presentation/api/health.py` | `/health/live`, `/health/ready`, `/health/deep` |

---
_Status: ARCHITECTURE LIVE & VERIFIED IN PRODUCTION RUNTIME._
