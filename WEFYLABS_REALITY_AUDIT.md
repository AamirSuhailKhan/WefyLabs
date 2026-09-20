# WEFYLABS PHASE 0 — REALITY AUDIT

## Executive Summary

**What WefyLabs actually is today:** a large FastAPI/Next.js real-estate CRM and automation monolith with lead/property CRUD, acquisition, matching, qualification, follow-up, calendar, communication, Copilot, billing, analytics, and revenue-autopilot code paths. It has a broad test suite and local development runtime evidence.

**What it is not yet:** runtime-verified production revenue operating system, fully proven tenant-safe platform, or proven customer-facing autonomous sales agent. External channels, live calendars, live LLM use, live PostgreSQL, Redis, and deployed services were not available for this audit.

**Strong:** substantive domain models, migrations through `0026_revenue_autopilot`, 1,463 collected tests, focused passing tests, provider abstractions, Celery/Redis deployment definitions, and a deployed-service definition in `render.yaml`.

**Risky:** authorization dependency defaults to `ADMIN`; models, routes, and background workers have grown faster than authoritative migration/runtime proof; a mock media backend loads at runtime; Calendar is mounted twice; the local SQLite file has zero schema entries; several direct LLM paths bypass the nominal router; and production configuration remains unverified.

**Evidence method:** source locations below are static-code evidence. Test evidence is explicitly labelled. Runtime evidence is an in-process FastAPI `TestClient`, not a deployed-environment verification.

## Evidence Snapshot

| Check | Result | Classification |
|---|---|---|
| Backend test collection | 1,463 tests collected | VERIFIED THROUGH TEST (collection only) |
| Targeted tests | 30 passed: tenant isolation, matching, Revenue Autopilot API | VERIFIED THROUGH TEST |
| Migration graph | `0026_revenue_autopilot (head)` | VERIFIED IN CODE |
| App health | `GET /health` returned 200 | VERIFIED AT RUNTIME (local/in-process) |
| API surface | OpenAPI generated; 551 paths | VERIFIED AT RUNTIME (local/in-process) |
| Production DB / Redis / providers | No connection or deployment inspection | UNKNOWN |

## Repository Architecture

| Area | Actual location | Status |
|---|---|---|
| Web | `apps/web`, Next 15.5.24 / React 19 / TypeScript | VERIFIED IN CODE |
| API | `apps/api/app`, FastAPI / Python 3.11 target / SQLAlchemy async | VERIFIED IN CODE |
| Data | SQLAlchemy models and Alembic migrations | PARTIALLY IMPLEMENTED |
| Workers | `app/celery_app.py`, `app/tasks`, module workers | VERIFIED IN CODE |
| Deployment | `docker-compose.yml`, `render.yaml`, `terraform`, `k8s` | VERIFIED IN CODE; deployment UNKNOWN |
| Tests | `apps/api/tests` | VERIFIED IN CODE / selected tests VERIFIED THROUGH TEST |
| CI/CD | `.github` exists; no pipeline execution inspected | UNKNOWN |

## Technology Reality

| Technology | Usage evidence | Status / confidence |
|---|---|---|
| Next.js 15.5.24 | `apps/web/package.json` | VERIFIED IN CODE / high |
| FastAPI 0.115+ | `apps/api/pyproject.toml`, `app/main.py` | VERIFIED IN CODE / high |
| Python 3.11 target | `pyproject.toml` | DECLARED; local runner was Python 3.14 / medium |
| PostgreSQL 16 | root `docker-compose.yml` | CONFIGURED; runtime UNKNOWN |
| SQLite | local `leadscore_dev.db` files and test configuration | VERIFIED IN CODE; inspected API-local file is empty |
| SQLAlchemy 2 / Alembic | `database.py`, `alembic/` | VERIFIED IN CODE |
| Redis / Celery | compose and `celery_app.py` | CONFIGURED / runtime UNKNOWN |
| Gemini | settings, `ai_service.py`, Copilot, command center | PARTIALLY IMPLEMENTED |
| OpenAI / Anthropic / Azure adapters | `modules/ai_agent/llm_router/adapters` | STUBBED/OPTIONAL: packages not declared |
| Razorpay / Google Calendar / SMTP | service modules + Render vars | CONFIGURED / runtime UNKNOWN |
| Object storage | `media_service.py` defaults to `mock` | MOCKED |

## Frontend Reality

Routes exist for marketing, register/login/OAuth callback, onboarding, dashboard, leads, properties, matching, tasks, pipeline/deals, inbox, follow-ups, automations/autopilot, analytics, settings, knowledge, portal, mobile, admin and simulator. API imports occur on principal dashboard pages (for example `dashboard/leads`, `properties`, `matching`, `follow-ups`, `inbox`). This establishes **frontend and intended API integration**, not successful live data behavior.

Demo is explicitly surfaced: onboarding says it creates a “Synthetic demo workspace”; the lead-capture forms page contains a demo-token fallback; navigation has a demo fallback. Mark demo paths **MOCKED/DEMO**, not production evidence. Mobile/accessibility/performance were not browser-audited: **UNKNOWN**.

## Backend Reality

`app/main.py` mounts routers for core CRM plus acquisition, identity, enrichment, communications, calendar, knowledge, matching, qualification, follow-up, CRM intelligence, autonomous loop, command center, onboarding, and revenue autopilot. It also mounts `calendar_router` twice, which produced duplicate OpenAPI operation-ID warnings at runtime: **BROKEN / PRODUCTION RISK** for API specification clients.

The codebase contains both legacy/service routes and newer module routes. Examples of duplicated business domains: `Score`/lead intelligence/predictive scoring; `Conversation`, unified communication, and omnichannel conversation models; `FollowUp` legacy and `follow_up_models`; several matching/recommendation paths. Consolidation needs a call-graph and data-ownership decision before deletion.

## Authentication and Authorization

Signup/login/OAuth, invitations, password reset, and account-deletion code exist under `modules/auth`. Backend routers use identity dependencies in many areas, but complete route-by-route enforcement was not proven.

`infrastructure/security/rbac.py` defines owner/admin/manager/agent/read-only roles and permissions, but `require_permission` receives `current_role: Role = Role.ADMIN` rather than resolving the authenticated principal. This is a **CRITICAL SECURITY RISK** until every consumer is shown to override it safely. UI controls cannot compensate for that.

## Multi-tenancy

Organizations, members, invitations, tenant mixins and many `organization_id`/broker filters exist. Targeted tenant-isolation tests passed. This is **TEST VERIFIED for selected coverage**, not global proof. Property tenancy is especially inconsistent: `PropertyListing.organization_id` is a computed alias of `broker_id`, rather than an organization foreign key. Background task, cache-key, file, AI-context, and analytics isolation are **NOT VERIFIED**.

## AI and Knowledge

Gemini is the declared primary provider. A nominal router exists in `modules/ai_agent/llm_router`, while direct Gemini HTTP/SDK calls also occur in `services/ai_service.py`, qualification extraction, follow-up re-engagement, Copilot, and command-center paths. Therefore there is **no verified centralized AI gateway**.

Knowledge models and worker routes cover documents, chunks/indexes, retrievals, citations, feedback and evaluation; pgvector setup SQL exists. Whether a real vector database is provisioned and whether retrieval is injected into customer responses is **UNKNOWN**. The deprecated `google-generativeai` package warning occurred during targeted tests: **TECHNICAL DEBT / PRODUCTION RISK**.

## Channels, Calendar, and Human Handoff

Adapters exist for WhatsApp, Telegram, SMTP email, SMS and webchat, with delivery queues and human-takeover code. Runtime loaded all adapters, but media initialized with `storage_backend=mock`; Telegram/SMS include mock paths, and external credentials/webhooks were not exercised. Thus only adapter wiring is VERIFIED IN CODE. Real two-way channel operation, WhatsApp activation, SMS, voice, and customer webchat are **NOT VERIFIED**. Voice has model support only through call-detail records; no telephony provider proof: **MISSING**.

Calendar supports OAuth, availability, holds, booking, cancellation, rescheduling, reminders, viewings and conflicts in code. Factory chooses mock in dev/test. Live provider operation is **UNKNOWN**.

## Deployment, Performance, Tests

`render.yaml` defines API, Celery worker, and beat services; Docker Compose defines Postgres/Redis/API/worker/beat. This is deployment configuration, not a deployed-system verification. `main.py` calls `Base.metadata.create_all()` outside production, while production depends on Alembic: this invites schema drift. The API-local SQLite file inspected during the audit had zero schema entries; it cannot evidence a working schema. PostgreSQL schema comparison was not possible: **OWNER ACTION REQUIRED** for a read-only staging/prod DB credential or schema dump.

## Final Recommendation

Stop breadth expansion. First enforce principal-derived authorization and tenant-scoped data access, establish a migration/runtime schema baseline, consolidate the authoritative lead/property/conversation/matching paths, and replace mocked delivery/storage before presenting autonomous revenue behavior as live.
