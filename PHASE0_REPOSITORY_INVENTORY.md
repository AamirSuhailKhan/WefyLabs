# PHASE 0 REPOSITORY INVENTORY — COMPLETE CODEBASE MAPPING

**Date Established:** 2026-09-28T17:50:00+05:30  
**Repository Identity:** WefyLabs RC-1  
**Scope:** Architecture, Modules, Routers, Tenancy, Storage, Security, Infrastructure  

---

## 1. BACKEND INVENTORY (`apps/api`)

### 1.1 Architecture & Stack
- **Framework:** FastAPI `0.139.2` with Starlette ASGI runtime
- **Async ORM:** SQLAlchemy `2.0.51` with `asyncpg` `0.31.0` and `aiosqlite` `0.22.1`
- **Migrations:** Alembic `1.18.5` (Head: `0041_master_build_14_intelligence`)
- **Worker / Background Queues:** Celery `5.6.3` with Redis backend (`redis` `8.0.1`)
- **Validation:** Pydantic `2.13.4`, Pydantic Settings `2.14.2`
- **Security & Crypto:** PyJWT `2.13.0`, cryptography `50.0.0`, hashlib/hmac
- **AI Integrations:** `google-genai` `2.24.0`, `google-generativeai` `0.8.6` (deprecated), `openai` `2.48.0`
- **Payments:** `razorpay` `2.0.1`

### 1.2 Module Inventory (72 Directories in `apps/api/app/modules/`)
1. `acquisition` & `lead_acquisition` — Inbound forms, tracking, and webhooks
2. `ai_agent` — Autonomous sales loop, tools, workforce controller
3. `api_keys` — Tenant API key generation, revocation, scoping
4. `alerts` & `incident` — SRE alerting and incident tracking
5. `audit` — System-wide immutable append-only audit trail
6. `auth` — Authentication, JWT, Google OAuth 2.0, invitations, passwords
7. `autonomous_loop` — Lead re-engagement state machine
8. `billing` — Subscription engine, catalog service, Razorpay, reconciliation
9. `calendar` — Calendar sync, appointment holds, scheduling, meetings
10. `command_center` — Broker daily briefing, action items, high-priority tasks
11. `communication` — Multi-channel router (email, SMS, WhatsApp, telegram, webchat)
12. `conversation_intelligence` — Conversation summaries, sentiment, intent
13. `copilot` — Broker AI assistant and deal copilots
14. `crm` & `crm_intelligence` — Unified contact 360, pipeline, stages, tasks
15. `customer_intelligence` — Behavioral analytics, churn risk
16. `customer_success` — Health scores, onboarding support
17. `deals` — 13-stage transaction lifecycle, milestones, commissions
18. `developer` — Webhook management, developer logs, API explorer
19. `diagnostics` & `system_health` — Health probes, database/cache checkers
20. `discovery` — AI buyer discovery, lead matching
21. `enrichment` — Data enrichment via public/social sources
22. `event_history` — Outbox event stream and event replay
23. `feature_flags` — Dynamic feature flags and kill switches
24. `follow_up` — Scheduled lead follow-ups and AI touchpoints
25. `global_` — Multi-currency, localization, phone validation
26. `health` — Production readiness, liveness, and component health
27. `identity_resolution` — Cross-channel lead identity deduplication
28. `ingestion` — Multi-source lead parser (portal email, CSV, webhook)
29. `integrations` — Third-party connectors (CRM, marketing, webhooks)
30. `intelligence` — Benchmarking, market intelligence graph
31. `inventory` — Buildings, floors, units, channel partner allocations
32. `knowledge` — Document ingestion, vector embedding, citation engine
33. `lead_intelligence` — Buying intent scoring, urgency analysis
34. `leads` — Core lead entity management and CRUD
35. `marketing` — Campaigns, landing pages, tracking links, listing distribution
36. `marketplace` — Extensions, plugin marketplace
37. `memory` — Semantic memory and long-term conversation recall
38. `metrics` — Prometheus metrics exporter and latency collectors
39. `notifications` — In-app, push, and email alert dispatch
40. `observability` — OpenTelemetry tracing and structured logging
41. `onboarding` — Organization activation wizard, demo mode, CSV seeds
42. `performance` — Team KPIs, leaderboard, broker conversion rates
43. `plugins` — Sandboxed custom extensions
44. `portal` — Customer-facing digital deal room
45. `predictive` — Lead conversion probability, price prediction
46. `properties` & `property_recommendation` — Real estate listings, semantic property match
47. `property_intelligence` — AVM automated valuation, pricing sanity
48. `prospect_intelligence` — Prospect scoring and preference graphs
49. `qualification` — BANT-style qualification and requirements extraction
50. `recommendation` — Property matching and ranking engine
51. `revenue_autopilot` — Deal acceleration and auto-offer generation
52. `revenue_intelligence` — Pipeline velocity, leakage detection, commissions
53. `sales_action` — Next best action recommendations
54. `sales_pipeline` — Visual kanban pipeline, stage gates
55. `saved_searches` & `search` & `search_history` — Multi-tenant search platform
56. `security` — DevSecOps scanner, IP allowlisting, audit log exports
57. `settings` — Organization preferences, channel credentials
58. `telemetry` — Performance telemetry and client error capture
59. `timeline` — Unified activity stream across leads, deals, properties
60. `webhooks` — HMAC-signed incoming webhook engine
61. `workflow` — Trigger/condition/action automation engine

### 1.3 Routing & Endpoints
- **Total Registered OpenAPI Endpoints:** 819 unique paths `[VERIFIED]`
- **Total Operations (Path + HTTP Method):** 913 operations `[VERIFIED]`
- **Duplicate Registrations in `main.py`:**
  - `health_router` mounted twice (`/` and `/api/v1`)
  - `auth_router` mounted twice (`/` and `/api/v1`)
  - `invitations_router` mounted twice (`/` and `/api/v1`)
  - `calendar_router` mounted at line 284 and line 304

### 1.4 Middleware Pipeline (LIFO Order)
1. `CORSMiddleware` — Configured origins, headers, credentials
2. `IdempotencyMiddleware` — Redis-backed HTTP request deduplication
3. `RequestTracingMiddleware` — Correlation ID and request tracing headers
4. `ObservabilityTracingMiddleware` — Prometheus metrics and latency metrics
5. `SecurityHeadersMiddleware` — HSTS, X-Content-Type-Options, X-Frame-Options, CSP
6. `CorrelationMiddleware` — Request-scoped UUID injection
7. `EnterpriseObservabilityMiddleware` — Structured JSON request/response logging

---

## 2. FRONTEND INVENTORY (`apps/web`)

### 2.1 Architecture & Stack
- **Framework:** Next.js `15.5.24` (App Router)
- **UI Library:** React `19.0.0`, React DOM `19.0.0`
- **Styling:** Tailwind CSS `3.4.15`, PostCSS `8.5.23`
- **Animation & Visuals:** Framer Motion `12.42.2`, GSAP `3.15.0`, Lenis `1.3.25`
- **Charts:** Recharts `2.13.3`
- **Icons:** Lucide React `0.454.0`

### 2.2 Route Inventory (57 Production Routes)
- Public / Marketing: `/` (Landing page with waitlist), `/login`, `/register`, `/auth/callback`, `/simulator`, `/portal`, `/robots.txt`, `/sitemap.xml`
- Onboarding: `/onboarding` (Multi-step activation wizard)
- Dashboard Core: `/dashboard`, `/dashboard/leads`, `/leads/[id]`, `/dashboard/properties`, `/dashboard/deals`, `/dashboard/pipeline`, `/dashboard/tasks`, `/dashboard/calendar`, `/dashboard/inbox`
- CRM 360: `/dashboard/crm`, `/dashboard/crm/leads`, `/dashboard/crm/customers`, `/dashboard/crm/customers/[id]`, `/dashboard/crm/pipeline`, `/dashboard/crm/tasks`, `/dashboard/crm/activities`
- Lead Capture: `/dashboard/lead-capture`, `/dashboard/lead-capture/sources`, `/dashboard/lead-capture/forms`, `/dashboard/lead-capture/events`, `/dashboard/lead-capture/import`
- Marketing Suite: `/dashboard/marketing`, `/dashboard/marketing/campaigns`, `/dashboard/marketing/listings`, `/dashboard/marketing/landing-pages`, `/dashboard/marketing/launches`, `/dashboard/marketing/assets`
- Intelligence & Analytics: `/dashboard/analytics`, `/dashboard/analytics/executive`, `/dashboard/analytics/predictions`, `/dashboard/intelligence`, `/dashboard/revenue-intelligence`, `/dashboard/matching`, `/dashboard/performance`, `/dashboard/autopilot`
- Settings & Admin: `/settings`, `/settings/billing`, `/settings/security`, `/dashboard/settings`, `/admin`, `/operations`, `/knowledge`, `/mobile`
- Portal (Customer Experience): `/portal/[org]/chat`, `/portal/[org]/property/[id]`

### 2.3 Authentication & Session Handling
- **Token Storage:** Stored in `localStorage` (`wefylabs_token`, `wefylabs_user`) in `lib/api-client.ts`.
- **API Client:** Centralized HTTP wrapper with Bearer token injection, automatic 401 handling, and typed endpoints.

---

## 3. INFRASTRUCTURE & DEPLOYMENT INVENTORY

### 3.1 Render Configuration (`render.yaml`)
- **Service 1:** `wefylabs-api` (Web Service, Docker, Python Uvicorn with 4 workers)
  - Health check: `/api/v1/health/readiness`
  - Auto-deploy: enabled on `main`
- **Service 2:** `wefylabs-celery-worker` (Background Worker, Docker)
  - Command: `celery -A app.core.celery_app worker -l info -c 4`
- **Service 3:** `wefylabs-celery-beat` (Background Worker, Docker)
  - Command: `celery -A app.core.celery_app beat -l info`
- **Environment Flags:**
  - `RAZORPAY_ENVIRONMENT: test` `[RISK]`
  - `STORAGE_LOCAL_DIR: storage_data` `[RISK: Ephemeral]`

### 3.2 Docker Configuration
- `apps/api/Dockerfile`: Development multi-stage Python image
- `apps/api/Dockerfile.prod`: Production multi-stage image (distroless/slim pattern)
- `apps/web/Dockerfile`: Production Next.js standalone build
- `docker-compose.yml`: Root compose with PostgreSQL, Redis, API, Celery worker, Celery beat, Next.js frontend

---

## 4. DATABASE INVENTORY & SCHEMA STATE

### 4.1 Migration State
- **Alembic Version Files:** 34 files in `apps/api/alembic/versions`
- **Authoritative Head:** `0041_master_build_14_intelligence` `[VERIFIED]`
- **Branching / Merges:** Single linear head confirmed via `alembic heads` `[VERIFIED]`

### 4.2 Key Domain Models & Tenancy Status
| Model | Table Name | Tenant Scoping Column | Foreign Key | Nullable? | Status |
|---|---|---|---|---|---|
| `Organization` | `organizations` | `id` (PK) | N/A | No | Canonical Root |
| `OrganizationMember` | `organization_members` | `organization_id` | `organizations.id` | No | Strict Membership |
| `Broker` | `brokers` | `id` (User PK) | None | N/A | Actor inside Tenant |
| `Lead` | `leads` | `organization_id` | `organizations.id` | Yes (legacy rows) | Dual-read filter |
| `PropertyListing` | `property_listings` | `organization_id` | `organizations.id` | Yes (legacy rows) | Needs strict enforcement |
| `DealTransaction` | `deal_transactions` | Missing `organization_id` | Only `broker_id` | N/A | **DEFECT**: Missing org tenancy |
| `SchedulingMeeting` | `scheduling_meetings` | `organization_id` | Column exists | No | Correctly scoped |
| `Conversation` | `conversations` | `broker_id` / `lead_id` | Indirect | N/A | Scoped via Lead |
| `PaymentOrder` | `payment_orders` | `organization_id` | `organizations.id` | Yes | Needs non-null guarantee |
| `Document` | `knowledge_documents` | `organization_id` | String UUID | No | Enforced in knowledge engine |
