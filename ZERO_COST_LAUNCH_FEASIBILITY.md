# ZERO-COST LAUNCH FEASIBILITY AUDIT
## WefyLabs Real-Estate CRM & AI Revenue OS

**Audit Date:** 2026-10-16  
**Auditor:** Architecture Review (read-only — no production changes made)  
**Repository:** `apps/api` (FastAPI) + `apps/web` (Next.js 15)  
**Scope:** Full repository inspection, provider verification, three-architecture comparison, phased proposal

---

> [!CAUTION]
> This is a feasibility audit only. No production systems, databases, cloud services, security settings, or autonomy parameters were modified. The audit stops at the proposal stage.

---

## Table of Contents

1. [Current Architecture](#1-current-architecture)
2. [Repository Inspection Summary](#2-repository-inspection-summary)
3. [Workload Inventory](#3-workload-inventory)
4. [Verified Provider Limits](#4-verified-provider-limits)
5. [Architecture Options Comparison](#5-architecture-options-comparison)
6. [Cost Comparison Matrix](#6-cost-comparison-matrix)
7. [Non-Negotiable Invariants Assessment](#7-non-negotiable-invariants-assessment)
8. [Recommended Architecture](#8-recommended-architecture)
9. [Minimum Changes Required](#9-minimum-changes-required)
10. [Phased Implementation Plan](#10-phased-implementation-plan)
11. [Known Limitations & Unsupported Features](#11-known-limitations--unsupported-features)
12. [Acceptance Criteria Mapping](#12-acceptance-criteria-mapping)
13. [Honest Conclusion](#13-honest-conclusion)

---

## 1. Current Architecture

### 1.1 Backend (`apps/api`)

| Component | Technology | Version / Config |
|-----------|-----------|-----------------|
| Web framework | FastAPI | ≥0.115.0 |
| ASGI server | Uvicorn (4 workers) | ≥0.30.0 |
| ORM | SQLAlchemy async | ≥2.0.30 |
| Database driver | asyncpg | ≥0.29.0 |
| Database | PostgreSQL + pgvector | 16-alpine (local), Supabase (prod) |
| Migrations | Alembic | 36 migration files, 0013–0043 + merge heads |
| Task broker | Redis (Celery) | ≥5.0.0 |
| Task queue | Celery | ≥5.4.0, 3 processes (web, worker, beat) |
| AI engine | Google Gemini | `google-generativeai ≥0.8.0`, model `gemini-2.5-flash` |
| OCR | Tesseract (local) | `pytesseract ≥0.3.10` |
| Document parse | pdfminer.six, python-docx, openpyxl | Local, no API cost |
| Vector store | pgvector | PostgreSQL extension |
| Payments | Razorpay | ≥1.4.1, test/live modes |
| Email | Brevo SMTP relay | `smtp-relay.brevo.com:587` |
| WhatsApp | 360dialog / Meta Cloud | **Hard-disabled** (`WHATSAPP_ENABLED=false`) |
| OAuth | Google OAuth 2.0 | JWT-validated, session-cookie bound |
| Auth | Supabase JWT (`HS256/RS256`) | No Supabase client dependency — JWT secret only |
| Storage | Local filesystem (`storage_data/`) | `STORAGE_BACKEND=local`, S3-compatible supported |
| Rate limiting | Redis-backed sliding window + in-memory fallback | Tiered: PUBLIC/AUTH/AI/ADMIN/WEBHOOK/BACKGROUND |

### 1.2 Frontend (`apps/web`)

| Component | Technology |
|-----------|-----------|
| Framework | Next.js 15.5.24 |
| Runtime | React 19 |
| UI | TailwindCSS 3, Framer Motion, GSAP, Recharts |
| API proxy | Next.js rewrites → FastAPI at `/api/v1/*` |
| Deployment config | `vercel.json` (Vercel-ready) + `Dockerfile` |

### 1.3 Deployment Infrastructure (current)

Three `render.yaml` services:
1. **`wefylabs-api`** — Render web service (Python), `./entrypoint.sh` → Alembic migrations + Uvicorn (4 workers)
2. **`wefylabs-celery-worker`** — Render worker service, 50+ queues
3. **`wefylabs-celery-beat`** — Render worker service, PersistentScheduler, 25+ cron schedules

**External dependencies (from `render.yaml` + `.env.example`):**
- `DATABASE_URL` — Supabase PostgreSQL (required)
- `REDIS_URL` — Upstash Redis TLS (`rediss://`) (required)
- `SUPABASE_JWT_SECRET` — JWT validation (required)
- `GEMINI_API_KEY` — Google Gemini (required for AI features)
- `SMTP_HOST/USER/PASSWORD` — Brevo (required for email)
- `RAZORPAY_KEY_ID/SECRET/WEBHOOK_SECRET` — Payments
- `GOOGLE_CLIENT_ID/SECRET` — Google OAuth
- `SECRET_KEY` — HMAC/JWT (min 32 chars, auto-generated on Render)

---

## 2. Repository Inspection Summary

### 2.1 Code vs. Verified Deployment

| Area | Code Exists | Known Deployed |
|------|-------------|----------------|
| FastAPI routes (100+ endpoints across 72 modules) | ✅ | Unverified live |
| Authentication & JWT validation | ✅ | Unverified live |
| Multi-tenant RBAC (org-based, header-selected) | ✅ | Evidence in audit docs |
| Alembic migrations (36 files, 0013–merge_heads) | ✅ | `9999_production_baseline.py` exists |
| Celery tasks (follow-up, calendar, CRM intel, predictive, workflow, memory, autonomous loop, revenue autopilot, intelligence) | ✅ | Beat schedule verified in `celery_app.py` |
| Redis rate limiter (with in-memory fallback) | ✅ | Operational in code |
| Google Gemini AI calls | ✅ | Key required, fallback behavior unverified |
| Razorpay billing (HMAC webhook verification, idempotency) | ✅ | Test mode in `.env.example` |
| pgvector knowledge embeddings | ✅ | Migration `b8e2d4f1a9c3_knowledge_engine.py` |
| Tesseract OCR (local) | ✅ | In Dockerfile(s) |
| Production entrypoint + Alembic-first startup | ✅ | `entrypoint.sh` |
| Health endpoints (liveness/readiness/deep) | ✅ | Used by Render health checks |
| WhatsApp | Code stub exists | **Hard-disabled** (`WHATSAPP_ENABLED=false`) |
| Stage-1 shadow mode governance | ✅ (`PILOT_MODE=RECOMMEND_ONLY`) | Autonomy 0 enforced in code |
| Next.js frontend (Vercel-ready) | ✅ | `vercel.json` present |

### 2.2 Critical Architecture Observation

The `apps/api/app/routers/leads.py` (legacy) uses **synchronous SQLAlchemy** (`Session`/`db.query()`) with a hardcoded broker fallback (`get_or_create_default_broker`). This is bypassed in production by the newer `app/modules/leads/router.py` which uses async sessions and proper tenant resolution. Both are mounted simultaneously in `main.py`. **This is a dual-router hazard** — the legacy router does not enforce tenant isolation.

---

## 3. Workload Inventory

### 3.1 Core CRM Features

| Feature | Frontend Route | Backend Endpoint | Tables | External Services | Async Required | Continuous Worker | Latency/Durability | Zero-Cost Compatible | Failure Behavior |
|---------|---------------|-----------------|--------|-------------------|---------------|------------------|-------------------|---------------------|-----------------|
| **Login / Auth** | `/auth` | `POST /api/v1/auth/login`, `POST /api/v1/auth/register` | `brokers`, `users`, `organizations`, `organization_members` | Supabase JWT secret (local validation) | No | No | Low latency, JWT exp enforced | ✅ Yes | 401 on bad token |
| **Google OAuth** | `/auth/callback` | `GET /api/v1/auth/google/url`, `POST /api/v1/auth/google/exchange` | `brokers`, `users` | Google OAuth 2.0 | No | No | Medium, external round-trip | ✅ Yes | CSRF state validated, fail closed |
| **Lead List / Create** | `/leads` | `GET/POST /api/v1/leads` | `leads`, `lead_events`, `audit_events` | None | No (create fires Celery tasks) | **Yes** (scoring, events) | Durable write, eventual background | ⚠️ Partial — core write works; scoring/AI requires worker | Worker loss = no scoring |
| **Lead Detail** | `/leads/:id` | `GET /api/v1/leads/:id` | `leads`, `lead_events`, `conversations` | None | No | Low latency | ✅ Yes | 404 on missing |
| **Properties** | `/properties` | `GET/POST /api/v1/properties` | `properties`, `property_units` | None | No | Low latency | ✅ Yes | 404 / 422 |
| **AI Matching** | `/matching` | `POST /api/v1/leads/:id/match` | `leads`, `properties`, `matching_scores` | Gemini AI | Preferred async | **Yes** (scoring queue) | Eventual, durable | ⚠️ Requires Gemini key + worker |  Gemini failure = graceful error |
| **Communications** | `/communications` | `POST /api/v1/communications/send` | `conversations`, `communication_events` | SMTP (Brevo), WhatsApp (disabled) | **Yes** | **Yes** (email/whatsapp queues) | At-least-once with retry | ⚠️ Requires SMTP config | Retry queue, DLQ |
| **Calendar / Bookings** | `/calendar` | `GET/POST /api/v1/calendar/meetings` | `meetings`, `meeting_holds`, `meeting_reminders`, `calendar_events` | None (external sync optional) | **Yes** (reminders every 5 min) | **Yes** (calendar-sync, reminders, booking queues) | Durable, holds expire in 5 min | ❌ Hold cleanup requires beat | Expired holds → re-released |
| **Tasks** | `/tasks` | `GET/POST /api/v1/crm/tasks` | `crm_tasks`, `task_assignments` | None | No | No | Low latency | ✅ Yes | 404 / 422 |
| **Pipeline** | `/pipeline` | `GET /api/v1/sales-pipeline/stages` | `pipeline_stages`, `pipeline_opportunities`, `site_visits` | None | No | No | Low latency | ✅ Yes | 404 |
| **Billing** | `/billing` | `POST /api/v1/billing/orders`, `POST /api/v1/billing/orders/verify` | `payment_orders`, `payment_transactions`, `subscriptions` | Razorpay API (outbound) | No (webhook async) | No | Synchronous HMAC verify | ✅ Core; requires Razorpay keys | Webhook replay defense |
| **Analytics / BI** | `/analytics` | `GET /api/v1/bi/...` | Multiple aggregation tables | None | No | No | Medium latency | ✅ Yes | Empty dataset |
| **AI Copilot** | `/copilot` | `POST /api/v1/copilot/chat` | `copilot_conversations` | Gemini AI | No (streaming) | No | Request-response | ⚠️ Requires Gemini key | Honest error if no key |
| **Revenue OS** | `/revenue` | `GET /api/v1/revenue-intelligence/...` | `revenue_metrics`, `revenue_outcomes` | Gemini (optional) | Background updates | **Yes** (analytics_queue) | Eventual | ⚠️ Predictions require worker | Stale metrics |
| **Autonomous Sales Loop** | Internal | Background only | `sales_loop_events`, `pilot_metric_snapshots` | Gemini AI | **Yes** | **Yes** (sales-loop-orchestration, every 5 min) | Stage-1 shadow only | ❌ Requires beat + worker | Events queued, not processed |
| **Onboarding / Activation** | `/onboarding` | `POST /api/v1/onboarding/...` | `onboarding_records`, `demo_data` | None | No | No | Low latency | ✅ Yes | Rollback supported |
| **Knowledge Base / OCR** | `/knowledge` | `POST /api/v1/knowledge/documents` | `knowledge_documents`, `knowledge_chunks` | Gemini (embeddings), Tesseract (local OCR) | **Yes** (12 knowledge queues) | **Yes** (knowledge-ingestion pipeline) | Durable multi-step | ❌ Requires worker + Tesseract |  DLQ on failure |
| **Webhooks (inbound)** | N/A | `POST /api/v1/webhooks/ingest` | `webhook_events`, `outbox_events` | External callers | **Yes** (webhook_queue) | **Yes** | Durable, idempotent | ⚠️ Can buffer, requires worker to process | DLQ |
| **Notifications** | N/A | Background + `GET /api/v1/notifications` | `notifications` | SMTP, WhatsApp (disabled) | **Yes** | **Yes** (notification_queue) | Eventual | ⚠️ Requires SMTP | Retry |
| **CRM Intelligence** | Background | Background tasks only | `lead_health_scores`, `sla_events`, `anomaly_events`, `daily_briefs` | Gemini AI | **Yes** | **Yes** (6 queues, every 2–30 min) | Eventual analytics | ❌ Requires worker + beat | Missed scans |
| **Predictive Analytics** | `/predictive` | Background + `GET /api/v1/predictive/...` | `prediction_records`, `forecast_models` | Gemini AI | **Yes** | **Yes** (3 queues, every 15–30 min) | Eventual | ❌ Requires worker | Stale predictions |
| **Workflow Automation** | `/workflows` | `POST/GET /api/v1/workflows/...` | `workflows`, `workflow_executions`, `workflow_waits` | None | **Yes** | **Yes** (5 queues, every 1 min for timers) | Durable state machine | ❌ Timer queue requires beat every 1 min | Waits stall |
| **Memory Engine** | Background | Background only | `customer_memories`, `memory_decay_records` | None | **Yes** | **Yes** (memory-decay, daily 03:00) | Eventual | ❌ Requires beat | Memory not decayed |
| **Follow-Up Automation** | `/follow-ups` | `GET/POST /api/v1/follow-ups/...` | `follow_ups`, `follow_up_rules`, `follow_up_executions` | SMTP | **Yes** (every 5 min) | **Yes** (lead_queue, every 5 min) | Durable | ❌ Requires beat + worker | Follow-ups not sent |
| **Revenue Autopilot** | `/revenue-autopilot` | Background + `GET /api/v1/revenue/...` | `revenue_opportunities`, `revenue_actions` | Gemini AI | **Yes** | **Yes** (every 10 min) | Eventual | ❌ Requires beat + worker | Opportunities not scanned |

---

## 4. Verified Provider Limits

> [!IMPORTANT]
> The following provider limits reflect official documentation as of October 2026. Always verify against current provider terms before deployment.

### 4.1 Render.com (Current API Host)

| Attribute | Free Tier |
|-----------|----------|
| Commercial use | **Allowed** |
| Card required | No (email only) |
| Web services | 1 free "Instance Hours" per month — **spins down after 15 min inactivity** |
| Worker services | **Not available on free tier** — workers require a paid plan |
| CPU/RAM | 512 MB RAM, 0.1 CPU (free) |
| Cold start penalty | ~30–60 seconds after inactivity |
| PostgreSQL | Free: 1 GB storage, **expires after 90 days**, max 1 DB |
| Redis | **Not provided by Render free** |
| Persistent disk | Not on free tier |
| Custom domains | Yes (free) |
| Auto-deploy from Git | Yes |
| **Critical:** Worker processes | ❌ **Free tier does not support background worker processes** |

**Conclusion for current setup:** Render free tier cannot run `wefylabs-celery-worker` or `wefylabs-celery-beat`. Only the web service can run on free, and it will cold-start. The 90-day PostgreSQL expiry is a data-loss risk.

### 4.2 Railway.app

| Attribute | Free Tier ("Hobby Trial") |
|-----------|--------------------------|
| Commercial use | **Trial only; Hobby plan ($5/mo) required for production** |
| Card required | Yes (for Hobby plan) |
| Free credit | $5 one-time trial credit |
| Services | Unlimited processes (web + workers from one repo) |
| Persistent storage | PostgreSQL plugin (512 MB free) |
| Redis | Plugin available (512 MB) |
| Inactivity | Services do not sleep on Hobby plan |
| Overage | Services stop when credit exhausted |
| **Conclusion** | ⚠️ $5 trial not commercially viable for ongoing operation |

### 4.3 Fly.io

| Attribute | Free Tier |
|-----------|----------|
| Commercial use | Allowed |
| Card required | **Yes — card required to deploy** |
| Always-on | 3 shared-CPU VMs with 256 MB RAM free |
| Worker processes | Yes — can run as separate Fly Apps or processes |
| Persistent volume | 3 GB free |
| PostgreSQL | Fly Postgres (own management, not managed) |
| Redis | Upstash Redis on Fly (free tier: 10K commands/day) |
| Cold start | No cold start (always-on within free allowance) |
| Overage | Charged per usage beyond free tier |
| **Conclusion** | ⚠️ Requires credit card. 256 MB RAM per VM is insufficient for Uvicorn (4 workers) + Celery together. Multiple VMs needed. Postgres self-managed. |

### 4.4 Supabase (Database)

| Attribute | Free Tier |
|-----------|----------|
| Commercial use | Allowed |
| Card required | No |
| PostgreSQL | 500 MB storage, pgvector supported |
| Connection limit | 60 concurrent connections |
| Inactivity pause | **Project paused after 1 week of inactivity** |
| Backups | 7-day point-in-time recovery (paid only) |
| Free tier backup | Daily backups for free tier (limited) |
| pgvector | ✅ Available |
| **Conclusion** | ✅ Suitable for pilot database. **Inactivity pause is a production risk** — must keep project active. |

### 4.5 Upstash Redis

| Attribute | Free Tier |
|-----------|----------|
| Commercial use | Allowed |
| Card required | No |
| Commands/day | **10,000 commands/day** |
| Max data size | 256 MB |
| TLS (rediss://) | ✅ Supported |
| Persistence | AOF persistence on paid; limited on free |
| **Celery broker capacity** | At 25 beat schedules × 24 = 600 INCR/day min; ~10K likely insufficient under load |
| **Conclusion** | ⚠️ 10K commands/day is critically low for Celery + rate limiting + queue operations. Real traffic will exhaust this in hours. |

### 4.6 Vercel (Frontend)

| Attribute | Free (Hobby) Tier |
|-----------|-----------------|
| Commercial use | **Hobby tier: personal projects only. Commercial use requires Pro ($20/mo)** |
| Card required | No (Hobby), Yes (Pro) |
| Next.js support | ✅ Full |
| Build minutes | 100 GB-Hours/month (Hobby) |
| Bandwidth | 100 GB/month |
| Functions | 100K invocations/day |
| Custom domain | ✅ |
| **Critical** | ❌ Hobby tier explicitly prohibits commercial use |

### 4.7 Google Gemini API

| Attribute | Free Tier |
|-----------|----------|
| Commercial use | **Allowed on paid tier; free tier for experimentation** |
| Free requests | 15 RPM, 1M tokens/day for Gemini 1.5 Flash |
| Model configured | `gemini-2.5-flash` (verify availability on free tier) |
| Rate limits | Strict — heavy AI workloads will exhaust free quota |
| **Conclusion** | ⚠️ AI features (Copilot, matching, qualification, autonomous loop) will hit rate limits quickly under load |

### 4.8 Brevo SMTP

| Attribute | Free Tier |
|-----------|----------|
| Commercial use | Allowed |
| Card required | No |
| Daily limit | **300 emails/day** |
| Monthly limit | 9,000 emails/month |
| SMTP relay | ✅ Available |
| **Conclusion** | ✅ Suitable for low-volume pilot |

---

## 5. Architecture Options Comparison

### Option A: Preserve FastAPI + PostgreSQL + Redis + Celery (Status Quo)

**Description:** Keep the existing three-process deployment (web + celery-worker + celery-beat) as currently configured in `render.yaml`.

**Capability assessment:**
- All 25 Celery beat schedules run on time (every 1–60 minutes)
- 50+ queues served
- Full follow-up automation, calendar reminders, CRM intelligence, predictive analytics, memory decay, autonomous sales loop, revenue autopilot
- Knowledge ingestion pipeline (12 queues)
- Stage-1 governance intact

**What can be free:**
- Supabase (database) — ✅ free with inactivity caveat
- Upstash Redis — ⚠️ 10K cmd/day exhausted quickly
- Render web service — ⚠️ cold starts, 1 free service
- **Celery worker + beat: NOT on Render free tier**

**Verdict:** Cannot run at zero cost under this architecture. Worker and beat services require Render paid tier (~$14/mo each). Redis 10K command limit is also inadequate.

---

### Option B: Preserve FastAPI + PostgreSQL; Replace Selected Worker Workloads with DB-Backed Jobs

**Description:** Eliminate Celery entirely for governance-critical and simple-cron tasks. Replace with:
1. **PostgreSQL-backed job table** (`background_jobs`) with a lightweight in-process scheduler polling every N seconds via a separate asyncio loop in the API process
2. **Or:** A single APScheduler instance embedded in the FastAPI lifespan (single-replica only)

**What can be moved to in-process scheduling:**
- Follow-up evaluation (every 5 min) — reads/writes DB only
- SLA monitoring (every 2 min) — reads/writes DB only
- Calendar reminder dispatch (every 5 min) — reads DB, sends email via SMTP
- Booking hold cleanup (every 5 min) — reads/writes DB only
- Memory decay (daily) — reads/writes DB only
- Revenue opportunity scan (every 10 min) — reads DB, calls Gemini
- Daily pilot snapshots (daily 00:30) — reads/writes DB only
- Workflow wait timer (every 1 min) — reads/writes DB only

**What CANNOT be safely moved to in-process:**
- Knowledge ingestion pipeline (12 stages with I/O isolation requirements)
- Heavy AI batch jobs (predictive, CRM intelligence, autonomous loop) — risk of blocking event loop
- Email/WhatsApp dispatch (requires retry queues + DLQ)
- Webhook processing (idempotency across restarts)

**Trade-offs:**
- Single-replica constraint: APScheduler in-process scheduling breaks with multiple workers (race conditions). Would require Redis distributed lock, which reintroduces Redis dependency, or a DB-based leader election.
- Uvicorn runs with 4 workers — each worker process runs its own scheduler unless carefully guarded.
- `asyncio.new_event_loop()` pattern in current Celery tasks (see `followup_tasks.py`, `calendar_tasks.py`) would need rewriting for true async in FastAPI context.

**Verdict:** Partially viable for a single-replica deployment with 1 Uvicorn worker and APScheduler. Eliminates need for Celery beat but creates operational fragility. Email dispatch still needs retry semantics. Reduces services from 3 to 1, but **multi-worker Uvicorn must be dropped to 1 worker**, reducing throughput.

---

### Option C: Consolidate API into Serverless-Compatible Architecture

**Description:** Rewrite/adapt FastAPI into serverless-compatible handlers (e.g., Vercel Functions, AWS Lambda via Mangum, or Cloudflare Workers with Python WASM).

**Blockers (make this option non-viable for current codebase):**

1. **Celery cannot run in serverless** — all background processing must be rebuilt
2. **WebSocket support** (`/ai-agent/v1/ws/chat/{org}/{lead}`) — WebSockets are not supported on Vercel Hobby; limited on other serverless platforms
3. **Alembic migrations** — must run as a separate migration step; cannot be embedded in cold-start of a serverless function safely
4. **Tesseract OCR** — binary dependency (~50 MB), not installable in most serverless environments; would require replacement
5. **File storage** — current `STORAGE_BACKEND=local` is ephemeral in serverless; must switch to S3-compatible
6. **Connection pooling** — asyncpg with `pool_size=10` will create new connection pools on every cold start, exhausting Supabase's 60-connection limit instantly
7. **`python-magic`** (libmagic) — native library, not available in most serverless runtimes
8. **pgvector queries** — compatible, but need managed connection pooler (PgBouncer via Supabase)
9. **Session cookies** (`wefylabs_oauth_sid` HttpOnly cookie) — compatible
10. **72 modules + 100+ routes** — cold start time likely 5–10+ seconds

**Verdict:** Not feasible without a substantial rewrite (estimated 3–4 weeks of engineering effort). The codebase is structurally incompatible with serverless execution. **Do not pursue Option C.**

---

## 6. Cost Comparison Matrix

### Assumptions
- "Zero traffic" = 0 active users, system idle
- "Low pilot" = 3–5 concurrent users, 10–50 leads/day, Celery executing scheduled tasks
- "Moderate" = 10–20 users, 100–500 leads/day, all features active
- Render Starter = $7/mo per service; Render Standard = $25/mo
- Upstash Redis = Free (10K cmd/day) or Pay-as-you-go (~$0.2 per 100K commands)
- Supabase = Free (500 MB) or Pro ($25/mo)

### Option A — Full Stack (Current)

| Service | Zero Traffic | Low Pilot | Moderate |
|---------|-------------|-----------|----------|
| Render web (API) | $7/mo (Starter) | $7/mo | $25/mo (Standard) |
| Render worker (Celery) | $7/mo | $7/mo | $25/mo |
| Render beat (Beat) | $7/mo | $7/mo | $25/mo |
| Supabase PostgreSQL | $0 (free) | $0 | $25/mo (Pro, >500 MB) |
| Upstash Redis | $0 (free, if <10K cmd/day) | ~$5/mo | ~$15/mo |
| Vercel (Frontend) | $20/mo (Pro, commercial) | $20/mo | $20/mo |
| Brevo SMTP | $0 | $0 | $0–$25/mo |
| **Total (Option A)** | **$41/mo** | **~$46/mo** | **~$135/mo** |

> [!NOTE]
> Zero traffic still costs $41/mo because Render worker services are always-on.

### Option B — Reduced Workers (In-Process Scheduler)

| Service | Zero Traffic | Low Pilot | Moderate |
|---------|-------------|-----------|----------|
| Render web (API, 1 worker) | $7/mo | $7/mo | $25/mo |
| Supabase PostgreSQL | $0 | $0 | $25/mo |
| Upstash Redis (rate limiting only) | $0 | $0 | ~$5/mo |
| Vercel (Frontend) | $20/mo | $20/mo | $20/mo |
| Brevo SMTP | $0 | $0 | $0 |
| **Total (Option B)** | **$27/mo** | **~$27/mo** | **~$75/mo** |

> [!NOTE]
> Minimum paid cost is ~$27/mo because Vercel commercial use requires Pro ($20/mo). Render free tier has cold-start issues (15 min idle = 30-60s cold start).

### Option C — Serverless

**Not viable** — see Section 5. Estimated rewrite cost exceeds any hosting savings.

### Zero-Cost Configuration (Theoretical Only)

Using Render free (cold starts) + Supabase free + Upstash free + no Vercel (self-host frontend on Render static site):

| Component | Free Option | Limitation |
|-----------|-----------|-----------|
| API (1 service) | Render free | 15-min idle spin-down, no workers |
| Frontend | Render static or Cloudflare Pages | No commercial restriction on Cloudflare Pages free |
| Database | Supabase free | Pauses after 1-week inactivity, no PITR backup |
| Redis | Upstash free | 10K cmd/day — exhausted under normal Celery use |
| Workers | ❌ None | No free worker services on Render |
| Email | Brevo free | 300 emails/day |
| AI | Gemini free | Rate-limited |

**Theoretical minimum (zero-cost, no workers):** $0/mo  
**What stops working at $0:** All Celery tasks (follow-ups, reminders, SLA monitoring, pipeline analysis, memory decay, CRM intelligence, predictive analytics, autonomous loop, revenue autopilot, knowledge pipeline, workflow timers). This is ~70% of the system's automated value.

---

## 7. Non-Negotiable Invariants Assessment

### 7.1 Organization-Based Tenant Isolation ✅ Preserved

`get_current_tenant()` in `dependencies.py` resolves org membership from the authenticated JWT, validates the `X-WefyLabs-Organization-Id` header against DB-verified memberships, and never trusts caller-supplied org IDs without verification. This is correctly implemented and works without Redis or workers.

**Risk:** The legacy `apps/api/app/routers/leads.py` does **not** enforce tenant isolation — it uses `get_or_create_default_broker()` (hardcoded). This router is mounted at `/api/v1/leads` in `main.py` alongside the secure module router. See Section 9.

### 7.2 No Caller-Controlled Tenant Authority ✅ Preserved

Header `X-WefyLabs-Organization-Id` is validated against DB memberships before any scoped query. The `TenantContext` is server-constructed and immutable (frozen dataclass). Worker contexts use `TenantContext.for_background_task()` which requires an explicit `organization_id`.

### 7.3 Durable Transactions and Idempotent Jobs ✅ Preserved (with workers)

Celery tasks use `AsyncSessionLocal()` per task, with explicit commits. Idempotency keys are present on billing webhooks (`X-Razorpay-Event-Id`) and autonomous loop events (`idempotency_key`). Without workers, queued events may be lost on restart.

**Risk at zero-cost:** Without Redis persistence (free Upstash has no AOF on free tier), Celery task payloads may be lost on Redis restart. This violates durability for queued jobs.

### 7.4 Reliable Retries and Recovery ✅ Preserved (with workers)

`max_retries=3, default_retry_delay=30` on critical tasks. DLQ (`dead_letter_queue`, `knowledge-dead-letter`) configured. Without a running worker, retries never execute.

### 7.5 No False-Success Responses ✅ Preserved

Health readiness endpoint returns 503 when DB or Redis is unavailable. Config validator (`validate_production_security`) raises `ValueError` at startup if production secrets are placeholders. No mock bypass in JWT validation.

### 7.6 Secure Credential Storage ✅ Preserved

`SECRET_KEY` enforced ≥32 chars in production. `SUPABASE_JWT_SECRET` placeholder rejected. Razorpay webhook verified with HMAC-SHA256. OAuth session uses HttpOnly server-side cookie binding. All secrets are env-var injected.

### 7.7 No Synthetic Evidence ✅ Enforced

`PILOT_MODE=RECOMMEND_ONLY` (default). Autonomous loop comment: _"NEVER generates synthetic evidence; all metrics sourced from PostgreSQL."_ The `generate_daily_pilot_snapshots` task is hash-locked and idempotent.

### 7.8 Stage-1 Shadow Mode Autonomy 0 ✅ Preserved

`PILOT_MODE` validated against `{RECOMMEND_ONLY, APPROVED_AUTOMATION, FULL_GOVERNED_EXECUTION, DISABLED}`. Workers check `EmergencyAutomationPauseService.is_global_paused()` and `is_tenant_paused()` before processing events. Stage-2 promotion gates not modified.

### 7.9 No Unauthorized Provider Side Effects ✅ Preserved

`WHATSAPP_ENABLED=false` hard-coded as default. `FOLLOWUP_HUB_DISPATCH_ENABLED=false` by default (follow-up emails are inert until explicitly enabled). `PAYMENTS_EMERGENCY_PAUSE=false` default. Kill switches are runtime-configurable.

### 7.10 Existing Data Must Not Be Destroyed ✅ Audit requirement

No data migration is proposed in this audit. Any migration plan must be staged and reversible with explicit approval.

---

## 8. Recommended Architecture

### Recommendation: **Option B (Modified) — Reduced Worker Profile**

**Target:** ~$27/mo minimum viable pilot deployment

### 8.1 Topology

```
┌─────────────────────────────────────────────────────┐
│  Vercel (Pro, $20/mo)                               │
│  Next.js 15 frontend                                │
│  Proxy: /api/v1/* → Render API                      │
└─────────────────────┬───────────────────────────────┘
                      │ HTTPS
┌─────────────────────▼───────────────────────────────┐
│  Render Starter ($7/mo) — Single Service             │
│  FastAPI + Uvicorn (1 worker, not 4)                │
│  + APScheduler (in-process, guarded by DB lock)     │
│  entrypoint.sh → Alembic → uvicorn --workers 1      │
└──────────┬──────────────────────┬───────────────────┘
           │                      │
┌──────────▼──────┐    ┌──────────▼──────────────────┐
│  Supabase Free  │    │  Upstash Redis Free          │
│  PostgreSQL 500MB│   │  Rate limiting only          │
│  pgvector        │   │  (in-memory fallback active) │
└─────────────────┘    └────────────────────────────┘
```

### 8.2 What Works in This Topology

| Feature | Status |
|---------|--------|
| Authentication (JWT + Google OAuth) | ✅ Full |
| Tenant isolation + RBAC | ✅ Full |
| Lead CRUD + pipeline | ✅ Full |
| Properties + inventory | ✅ Full |
| Tasks + notes + tags | ✅ Full |
| Billing (Razorpay orders + verify) | ✅ Full |
| AI Copilot (on-demand Gemini) | ✅ Full (rate-limited) |
| Onboarding flow | ✅ Full |
| Basic calendar (create/read meetings) | ✅ Read/write |
| Revenue intelligence (read-only) | ✅ Stale reads |
| Health checks (liveness/readiness) | ✅ Full |
| Audit logs | ✅ Full |
| Analytics (aggregate queries) | ✅ Full |

### 8.3 What is Degraded (Requires Disclosure)

| Feature | Degradation | Impact |
|---------|------------|--------|
| Follow-up automation | No automated dispatch | Manual follow-ups only |
| Calendar reminders | No automated dispatch | No T-24h/2h/30m alerts |
| Booking hold cleanup | Holds may linger | Manual re-release |
| CRM intelligence (SLA monitoring) | No background scan | No automated alerts |
| Predictive analytics | No scheduled refresh | Stale or empty predictions |
| Knowledge ingestion pipeline | Must be triggered synchronously | No background OCR pipeline |
| Autonomous sales loop | Beat tasks don't fire | Stage-1 shadow not collecting data |
| Memory decay | Memories not decayed | DB accumulation |
| Workflow timers | Waits don't advance | Workflows stall |
| Revenue autopilot | No opportunity scanning | No automated detection |

### 8.4 In-Process Scheduler (APScheduler) Guard Design

To safely run scheduled tasks inside the single API process:

```python
# In lifespan (pseudo-code — implementation requires separate PR + tests)
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore

scheduler = AsyncIOScheduler(
    jobstores={"default": SQLAlchemyJobStore(url=settings.DATABASE_URL_SYNC)},
    timezone="UTC"
)
# Guard: only the designated leader process runs scheduling
# Leader election via DB row lock (no Redis required)
```

**Important constraints:**
- Must use `--workers 1` with Uvicorn (APScheduler is not fork-safe with multiple processes)
- SQLAlchemy jobstore requires a **synchronous** connection string (not `asyncpg`) for APScheduler's internal use — a second connection string env var is required
- Tasks that use `asyncio.new_event_loop()` (e.g., `calendar_tasks.py`) must be rewritten to use `async def` with `asyncio.create_task()` within the running event loop

---

## 9. Minimum Changes Required

> [!WARNING]
> These changes must NOT be applied to production without: (a) passing all existing tests, (b) explicit written approval, (c) equivalent test coverage for every replacement.

### 9.1 P0 — Immediate Security Fix (Before Any Deployment)

**File:** `apps/api/app/main.py`  
**Problem:** Legacy `app/routers/leads.py` is mounted at `/api/v1/leads` without tenant isolation  
**Change:** Remove or guard the legacy router mount

```python
# Line 230 in main.py — REMOVE this line:
# app.include_router(leads_router, prefix=settings.API_V1_STR)
# The secure module router (hex_leads_v1_router) at line 232 is the correct one.
```

**Test before removal:** Verify `GET /api/v1/leads` still works via the secure module router. Check for any frontend calls that depend on the legacy response shape.

### 9.2 Option B Changes — In-Process Scheduler

**Files to change:**
1. `apps/api/requirements.txt` — add `apscheduler>=3.10.0`
2. `apps/api/app/main.py` — add APScheduler lifespan setup (guarded by single-worker constraint)
3. `apps/api/entrypoint.sh` — change `--workers "${WORKERS:-4}"` to `--workers 1`
4. `apps/api/render.yaml` — remove `wefylabs-celery-worker` and `wefylabs-celery-beat` service blocks

**Migration strategy:**
- Implement APScheduler with DB jobstore in a feature branch
- Run both Celery (on local docker-compose) and APScheduler in parallel during testing
- Verify each cron schedule fires correctly with a test task
- Deploy to a staging Render service before changing production

**Rollback strategy:**
- Keep `render.yaml` with all three services in a separate branch
- A `git revert` + redeploy restores Celery services in minutes

### 9.3 Redis — Reduce Dependency to Optional

**Current:** Rate limiter fails open (in-memory fallback) when Redis is unavailable — already safe.  
**Action needed:** Confirm `REDIS_URL` default in `config.py` does not fail startup if Upstash 10K limit is exhausted.  
**Change:** The `check_rate_limit` function already falls back to in-memory. No code change needed. Document this behavior.

### 9.4 Storage — Allow Local in Production (Pilot Only)

**Current validator:** `STORAGE_BACKEND=local` raises `ValueError` in production unless `ALLOW_LOCAL_STORAGE_IN_PROD=true`.  
**Action:** Set `ALLOW_LOCAL_STORAGE_IN_PROD=true` in Render env vars for pilot phase.  
**Risk:** Files on Render ephemeral disk will be lost on service redeploy. Acceptable for pilot if no customer documents are uploaded yet.  
**Long-term:** Must switch to S3/R2 before accepting real customer documents.

### 9.5 Frontend — Vercel Commercial License

**Action:** Upgrade Vercel to Pro ($20/mo) for commercial use, OR deploy frontend to Cloudflare Pages (free for commercial use, Next.js support via `@cloudflare/next-on-pages`).  
**Cloudflare Pages limitation:** Edge runtime, not Node.js. Next.js API routes with Node.js-specific APIs may fail. The current frontend does not have API routes (all calls proxy to FastAPI). This should be compatible.

### 9.6 Supabase — Prevent Inactivity Pause

**Action:** Configure Supabase project settings to prevent idle pause, or set up a keep-alive ping from the API health check.  
**Implementation:** Add a background health ping to `entrypoint.sh` or the lifespan startup:
```bash
# In entrypoint.sh — periodic DB ping via cron (or use UptimeRobot free tier)
```

---

## 10. Phased Implementation Plan

### Phase 0 — Immediate Safety Fixes (0 cost, 1–2 days)

- [ ] Remove legacy `leads_router` mount (Section 9.1)
- [ ] Set `ALLOW_LOCAL_STORAGE_IN_PROD=true` in Render env for pilot
- [ ] Document which features are degraded without workers
- [ ] Verify health endpoints return correct status without workers
- [ ] Confirm `PILOT_MODE=RECOMMEND_ONLY` is set in production env

### Phase 1 — Minimal Viable Pilot ($27/mo, 1 week)

- [ ] Upgrade Vercel to Pro OR migrate frontend to Cloudflare Pages (test thoroughly)
- [ ] Set Render web service to `--workers 1`
- [ ] Remove Celery worker and beat from `render.yaml` (comment out, do not delete)
- [ ] Verify core flows: login → create lead → assign → view pipeline → billing test order
- [ ] Test that rate limiter falls back to in-memory correctly
- [ ] Test AI Copilot with valid Gemini key
- [ ] Confirm health `/readiness` endpoint passes (DB ok + Redis ok or degraded-graceful)
- [ ] Set `FOLLOWUP_HUB_DISPATCH_ENABLED=false` (already default)
- [ ] Set `WHATSAPP_ENABLED=false` (already default)

### Phase 2 — Add In-Process Scheduling (Optional, +$0, 1–2 weeks)

- [ ] Add APScheduler to `requirements.txt`
- [ ] Implement DB-backed leader election guard (prevents duplicate scheduling across restarts)
- [ ] Port 6 critical schedules (follow-up eval, booking cleanup, reminders, workflow timers, memory decay, daily snapshots) to async APScheduler jobs
- [ ] Write integration tests for each ported schedule
- [ ] Deploy with `--workers 1` constraint enforced
- [ ] Verify Stage-1 daily pilot snapshot fires and generates real data

### Phase 3 — Add Workers When Revenue Justifies Cost (+$14/mo, when ready)

- [ ] Re-enable `wefylabs-celery-worker` on Render Starter
- [ ] Re-enable `wefylabs-celery-beat` on Render Starter
- [ ] Upgrade Upstash Redis to Pay-as-you-go
- [ ] Restore `--workers 4` on Uvicorn
- [ ] Verify all 25 beat schedules fire correctly
- [ ] Enable `FOLLOWUP_HUB_DISPATCH_ENABLED=true` only after email SMTP testing passes
- [ ] Full regression test suite

### Phase 4 — Production Hardening (Before Commercial Launch)

- [ ] Migrate `STORAGE_BACKEND=s3` (AWS S3 or Cloudflare R2, free 10 GB)
- [ ] Configure Supabase Pro (PITR backups, connection pooler)
- [ ] Upgrade Redis to persistent plan
- [ ] Load test at target concurrency
- [ ] Enable Razorpay live keys (after Razorpay compliance review)
- [ ] Verify `SUPER_ADMIN_EMAILS` is populated
- [ ] Security audit of all 100+ endpoints

---

## 11. Known Limitations & Unsupported Features at Zero/Minimum Cost

| Feature | Status at $27/mo |
|---------|-----------------|
| Automated follow-up dispatch | ❌ Disabled (no beat) |
| Calendar reminders (T-24h/2h) | ❌ Disabled |
| Booking hold auto-release | ❌ Disabled |
| SLA breach monitoring | ❌ Disabled |
| Lead health & decay scoring | ❌ Disabled |
| Predictive revenue forecasts | ❌ Stale/disabled |
| Knowledge pipeline (OCR → embedding → index) | ❌ Disabled |
| Autonomous sales loop (Stage-1 shadow) | ❌ No data collection |
| Memory decay | ❌ Accumulates |
| Workflow timer resumption | ❌ Stalls |
| Revenue opportunity scanning | ❌ Disabled |
| WhatsApp | ❌ Hard-disabled |
| Multi-worker Uvicorn (performance) | ⚠️ 1 worker only |
| Upstash 10K cmd/day exhaustion | ⚠️ Falls back to in-memory (per-process, not distributed) |
| Supabase idle pause | ⚠️ Must keep active |
| File persistence across redeploys | ⚠️ Local only — ephemeral |

---

## 12. Acceptance Criteria Mapping

| Criterion | Met at $27/mo? | Notes |
|-----------|---------------|-------|
| Successful login and tenant isolation | ✅ Yes | JWT + DB-verified org membership |
| End-to-end lead creation and durable storage | ✅ Yes | PostgreSQL write, not ephemeral |
| Correct CRM lifecycle operations | ✅ Yes | Pipeline, stages, tasks, notes |
| Working scheduled tasks and background jobs | ⚠️ Partial | Only with APScheduler (Phase 2) or Celery (Phase 3) |
| Recoverable failures without duplicate effects | ⚠️ Partial | Billing idempotency intact; Celery retry semantics absent |
| Genuine AI execution or honest failure reporting | ✅ Yes | Gemini key required; health endpoint reports if missing |
| Correct booking and revenue records | ✅ Yes | DB-persisted, Razorpay HMAC-verified |
| Intact audit evidence | ✅ Yes | Audit table writes on every CRUD operation |
| No unauthorized external actions | ✅ Yes | WHATSAPP_ENABLED=false, FOLLOWUP_HUB_DISPATCH_ENABLED=false |
| Reproducible deployment from GitHub | ✅ Yes | Render Git integration + Vercel Git integration |
| No mandatory monthly fee under zero-cost constraint | ❌ No | Minimum $27/mo for commercial-grade hosting |

---

## 13. Honest Conclusion

### Zero mandatory monthly cost is NOT achievable for this system at commercial-grade operation.

**The irreducible minimum is $27/mo** (Render Starter $7 + Vercel Pro $20), and this only covers the CRM read/write core, authentication, on-demand AI, billing, and basic calendar. It does not include the automated intelligence layer that constitutes the product's primary value proposition.

**The fundamental constraints are:**

1. **Celery worker processes cannot run on any free tier** — Render, Railway, and Fly.io all require paid plans for always-on background workers. Without workers: no automated follow-ups, no AI sales loop, no CRM intelligence, no predictive analytics, no knowledge pipeline.

2. **Upstash free Redis (10K commands/day) is insufficient** — A single Celery beat schedule firing every minute generates >1,400 commands/day from beat alone. A single day of real usage exhausts the limit.

3. **Vercel commercial use is not permitted on the free Hobby plan** — The product is a commercial SaaS. Vercel Pro ($20/mo) is the correct tier, or migrate to Cloudflare Pages (free for commercial use, lower risk).

4. **Supabase free tier inactivity pause** — A production system cannot allow database pauses. This must be managed (keep-alive pings or Supabase Pro at $25/mo).

### Recommended Honest Pilot Position

> **"WefyLabs CRM launches as a functional, secure, multi-tenant CRM at ~$27/mo. Automated AI intelligence features (follow-ups, reminders, predictive analytics, autonomous loop) are in the roadmap and activate when the business can justify the additional ~$28/mo for worker infrastructure. All data is durable. All security invariants are preserved."**

This is an honest, non-deceptive launch position that does not claim production readiness for features that require infrastructure that does not yet exist.

### Do Not Claim Full Production Readiness Until:

- [ ] Celery worker and beat are running and verified
- [ ] Redis has a persistent, paid plan
- [ ] Supabase Pro is active (for PITR backup)
- [ ] File storage is on S3/R2 (not ephemeral local)
- [ ] Load testing passes at target concurrency
- [ ] All 25 beat schedules verified in staging
- [ ] Razorpay live keys validated with Razorpay compliance

---

*End of Audit. No production changes were made. Proceed to implementation only with explicit approval.*
