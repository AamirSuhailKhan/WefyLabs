# WEFYLABS — FOUNDATION CURRENT-STATE AUDIT

**Generated**: 2026-09-25T11:49:00Z  
**Branch**: `update-os`  
**Commit SHA**: `d20862e9dcdc191c0978e700f2d4b72baeff67fc`  
**Authoritative Environment**: Windows x64, Python 3.14.6, Node v24.14.1, npm 11.11.0  

---

## 1. REPOSITORY IDENTITY

| Attribute | Detected Value / Specification | Evidence / Source |
|---|---|---|
| **Branch** | `update-os` | `git branch --show-current` |
| **Commit SHA** | `d20862e9dcdc191c0978e700f2d4b72baeff67fc` | `git rev-parse HEAD` |
| **Repository Structure** | Monorepo: `apps/api` (FastAPI), `apps/web` (Next.js), `k8s/`, `terraform/`, `scripts/` | Root directory inspection |
| **Frontend Framework** | Next.js `15.5.24`, React `19.0.0`, TypeScript `5.6.3`, Tailwind CSS `3.4.15` | `apps/web/package.json` |
| **Backend Framework** | FastAPI `0.139.2`, Starlette `1.3.1`, Pydantic `2.13.4`, Pydantic-Settings `2.14.2` | `pip list`, `apps/api/pyproject.toml` |
| **ORM / Migrations** | SQLAlchemy `2.0.51`, Alembic `1.18.5` (Current Head: `0034_customer_portal_os`) | `apps/api/alembic/versions` |
| **Python Version** | Python `3.14.6` | `python --version` |
| **Node Version** | Node `v24.14.1`, npm `11.11.0` | `node --version`, `npm --version` |
| **Database** | PostgreSQL with `asyncpg` `0.31.0` (Supabase AWS ap-south-1 pooler), `aiosqlite` for test mode | `apps/api/.env`, `apps/api/app/database.py` |
| **Redis / Cache** | Upstash Redis `rediss://` TLS cluster, Redis Python client `8.0.1` | `apps/api/.env`, `apps/api/app/common/redis` |
| **Queue / Workers** | Celery `5.6.3` with Kombu `5.6.2`, 40+ configured queues, Celery Beat periodic scheduler | `apps/api/app/celery_app.py` |
| **AI Provider** | Primary: Google Gemini (`google-genai` `2.24.0`). Legacy `google-generativeai` `0.8.6` still imported in rogue modules | `pip list`, `apps/api/app/modules/ai_agent` |
| **Deployment Targets** | Render (`render.yaml`), Docker Compose (`docker-compose.yml`), Kubernetes (`k8s/`), Vercel (`apps/web/vercel.json`) | Root configuration files |
| **Storage Provider** | Configured as `local` (`./storage/knowledge`); S3 provider code present in knowledge module | `apps/api/app/modules/knowledge/ingestion/storage_service.py` |
| **Email Provider** | Brevo SMTP Relay (`smtp-relay.brevo.com:587`, STARTTLS) | `apps/api/.env`, `apps/api/app/common/config` |
| **Calendar Provider** | Google Calendar API via OAuth2 (`apps/api/app/modules/calendar`) | `apps/api/app/modules/calendar` |
| **Payment Provider** | Razorpay SDK `2.0.1` (`apps/api/app/modules/billing`) | `apps/api/app/modules/billing` |

---

## 2. ACTUAL ARCHITECTURAL MAP

```text
[ Browser / Customer Portal / Mobile ]
               │
               ▼  (HTTP / JSON, Authorization Bearer JWT, X-WefyLabs-Organization-Id)
[ API Edge: FastAPI (apps/api/app/main.py) ]
   ├── Enterprise Observability Middleware (Correlation, Tracing, Metrics)
   ├── Security Headers Middleware (CSP, HSTS, X-Frame-Options)
   ├── Idempotency Middleware (Distributed Redis Lock & Cache)
   └── Distributed Rate Limiting (Redis-backed sliding window)
               │
               ▼
[ Auth & Identity Layer (apps/api/app/dependencies.py) ]
   ├── get_current_broker: Supabase JWT validation (sub, email, expiration)
   └── get_current_tenant:
         ├── Query OrganizationMember (broker_id -> organization_id list)
         ├── Enforce organization selection (Header: X-WefyLabs-Organization-Id)
         ├── Block cross-tenant access with HTTP 403 (ORGANIZATION_ACCESS_DENIED)
         └── Fail closed if multiple memberships without header: HTTP 409 (ORGANIZATION_CONTEXT_REQUIRED)
               │
               ▼
[ Tenant Execution Plane (apps/api/app/infrastructure/tenancy/scope.py) ]
   ├── Canonical foreign key: organization_id (UUID)
   ├── require_organization_id(): fail-closed validator
   └── Dual-read compatibility filter: tenant_lead_filter(org_id, broker_id)
               │
               ▼
[ Domain Services & Modules (apps/api/app/modules/) ]
   ├── Leads & Ingestion: IngestionController, Universal Lead Hub
   ├── Real Estate Supply OS: Projects, Phases, Buildings, Floors, Units (Part 19)
   ├── Real Estate Deal OS: Opportunity -> Negotiation -> Booking -> Closing (Part 18)
   ├── Omnichannel Communication: RealDeliveryEngine, Channels (WhatsApp, Email, SMS, Webchat)
   ├── Calendar Intelligence: BookingService, GoogleCalendarProvider, MeetingHold
   ├── Knowledge Intelligence Platform: DocumentParsing, OCR (Tesseract), Vector Store (pgvector)
   └── Revenue Autopilot & CRM Intelligence: DailyBriefs, SLA Breaches, Opportunity Scanning
               │
         ┌─────┴───────────────────────────────────────────────────────┐
         ▼                                                             ▼
[ AI Gateway (apps/api/app/infrastructure/ai_gateway/) ]    [ Background Queues: Celery ]
   ├── AI Request Pipeline (Task routing, Latency, Cost)      ├── 40+ dedicated queues
   ├── ModelRouter (Gemini 2.5 Flash / Pro)                   ├── Celery Beat scheduler
   ├── Structured Output Enforcement (Pydantic / Strict JSON) ├── Distributed bounded jobs
   ├── Action Authorizer (READ/SUGGEST/CONFIRM/EXECUTE)       └── Dead-Letter Queue (DLQ)
   ├── Persistent Telemetry (AIRequestRecord table)                    │
   └── Tool Execution & Verification                                   ▼
         │                                            [ Asynchronous Worker Nodes ]
         ▼                                                             │
[ External Providers ]                                                 │
   ├── Google Gemini API (google-genai modern SDK)                     │
   ├── Meta Cloud API Direct / 360dialog (WhatsApp)                    │
   ├── Brevo SMTP (Email)                                              │
   ├── Google Calendar API (Calendar Sync)                             │
   └── Razorpay API (Payments & Subscriptions)                         │
         │                                                             │
         └─────────────────────────────┬───────────────────────────────┘
                                       ▼
                       [ Database & Persistence Engine ]
                          ├── PostgreSQL 16 (Supabase)
                          ├── Alembic Migrations (Authoritative)
                          ├── Outbox Pattern (Transactional Event Bus)
                          └── Upstash Redis (Distributed Locks & Cache)
```

---

## 3. DUPLICATE-SYSTEM INVENTORY

| Domain Concept | Current Implementations & Locations | Used By | Production Status | Duplicate Of | Recommended Canonical Implementation | Recommended Action |
|---|---|---|---|---|---|---|
| **Tenant Context** | 1. `apps/api/app/dependencies.py` (`get_current_tenant`)<br>2. `apps/api/app/infrastructure/tenancy/scope.py`<br>3. `apps/api/app/models/lead.py` (`@property def organization_id -> str(self.broker_id)`)<br>4. `apps/api/app/models/property_models.py` (`@property def organization_id -> str(self.broker_id)`) | 1 & 2: routers, dependencies<br>3 & 4: legacy property accessors | 1 & 2: Active<br>3 & 4: Production Risk | Each other | `apps/api/app/infrastructure/tenancy/scope.py` + `apps/api/app/dependencies.py` with real `organization_id` foreign keys on `Lead` and `PropertyListing` | **MERGE & MIGRATE**: Add real `organization_id` column to `leads` and `property_listings`; retire legacy `@property` hacks. |
| **Lead API Routers** | 1. `apps/api/app/modules/leads/router.py` (`/leads`)<br>2. `apps/api/app/presentation/api/v1/leads.py` (`/leads`)<br>3. `apps/api/app/modules/leads/controller/lead_controller.py` (`/v1/leads`) | `main.py` mounts all 3 under `/api/v1` | Confusing collisions | Each other | `apps/api/app/modules/leads/router.py` | **CONVERGE**: Retire redundant router endpoints; ensure single canonical lead entrypoint under `/api/v1/leads`. |
| **Communication / WhatsApp** | 1. `apps/api/app/services/whatsapp_service.py`<br>2. `apps/api/app/modules/communication/delivery_engine/real_delivery_engine.py`<br>3. `apps/api/app/modules/communication/provider_adapters/whatsapp_provider.py`<br>4. `apps/api/app/routers/whatsapp.py` | 1: `conversation_service.py`<br>2: `action_executor.py`<br>3: `ChannelManager`<br>4: `main.py` | 1: Production Risk (fake success!)<br>2 & 3: Production Ready | 2 & 3 | `apps/api/app/modules/communication/delivery_engine/real_delivery_engine.py` via `ChannelManager` | **CONVERGE & ELIMINATE**: Route `conversation_service` through `real_delivery_engine`/`ChannelManager`; delete fake success in `whatsapp_service.py`. |
| **AI Gateway & Gemini Invocations** | 1. `apps/api/app/infrastructure/ai_gateway/gateway.py`<br>2. `apps/api/app/services/ai_service.py` (direct `httpx` to Google)<br>3. `apps/api/app/modules/revenue_autopilot/outreach_generator.py` (direct `google.generativeai`)<br>4. `apps/api/app/modules/properties/service.py` (direct `google.generativeai`)<br>5. `apps/api/app/modules/follow_up/ai_reengagement/reengagement_service.py` (direct `google.generativeai`) | 1: Gateway foundation<br>2: Webhook conversation<br>3: Outreach generation<br>4: Property descriptions<br>5: Reengagement | 1: Canonical<br>2, 3, 4, 5: Fragmented / Outdated SDK | 1 | `AIGateway` (`apps/api/app/infrastructure/ai_gateway/gateway.py`) | **REPLACE & CONVERGE**: Migrate all rogue callers (2, 3, 4, 5) to `AIGateway`; remove direct `google.generativeai` imports. |
| **Health Endpoints** | 1. `apps/api/app/presentation/api/health.py` (`/health/live`, `/health/ready`, `/health/deep`)<br>2. `apps/api/app/modules/system_health/controller/health_controller.py` (`/api/v1/v1/health`)<br>3. `apps/api/app/modules/health/controller/health_controller.py` (`/api/v1/v1/health-diag`) | 1: Root & Kubernetes<br>2: System health module<br>3: Health diagnostics | 1: Canonical<br>2 & 3: Nested path clutter | 1 | `apps/api/app/presentation/api/health.py` mounted at `/health` | **CONVERGE**: Standardize on `/health/live`, `/health/ready`, `/health/deep`. Retire nested duplicate `/api/v1/v1/health*` routes. |
| **Object Storage** | 1. `apps/api/app/modules/knowledge/ingestion/storage_service.py` (StorageProvider, Local, S3, Mock)<br>2. Ad-hoc in-memory/direct writes in properties/portal | 1: Knowledge documents only<br>2: Untracked | Incomplete across CRM | None | Universal `ObjectStorageService` supporting tenant-scoped keys `organizations/{org_id}/...` | **UNIFY**: Promote `storage_service` to `app/infrastructure/storage/object_storage.py` and enforce signed URLs, MIME verification, and tenant scoping across all modules. |

---

## 4. FAKE / STUB / DEMO / MOCK INVENTORY

| Location | Pattern / Match | Context | Classification | Assessment & Remedy |
|---|---|---|---|---|
| `apps/api/app/services/whatsapp_service.py:79-81` | `if settings.DIALOG360_API_KEY == "d360_key_placeholder"... return True` | Standalone WhatsApp dispatch silently returns `True` and logs `[WhatsApp Simulated Send]` when key is default placeholder | **PRODUCTION BLOCKER** | **ELIMINATE IMMEDIATELY**: Violates Zero Fake Success rule. Must return `False` or truthful `OperationStatus.CONFIGURATION_REQUIRED`. |
| `apps/api/app/presentation/api/v1/properties.py:225-265` | `if result["total"] == 0 and not search: seed1 = PropertyListing(...)` | Silently inserts synthetic demo properties (`PROP-DEMO1`, `PROP-DEMO2`) into a user's database when they view an empty list | **PRODUCTION BLOCKER** | **ELIMINATE IMMEDIATELY**: Violates Demo Mode separation. Synthetic data must NEVER be silently injected into production tenant tables. |
| `apps/api/app/presentation/api/v1/properties.py:536-538` | `except Exception: pass` | Bulk property update catches all exceptions and silently ignores failures | **PRODUCTION RISK** | **REPLACE**: Must record individual item errors and return truthful `partial_success` or error summary. |
| `apps/api/app/routers/whatsapp.py:77-79` | `except Exception as e: ... return {"status": "ok", "detail": "Internal processing error"}` | Webhook listener swallows processing error and returns 200 OK with success indicator | **PRODUCTION RISK** | **AUDIT**: Webhooks require acknowledging receipt to prevent replay storms, but raw payload must be recorded in Outbox/Dead-Letter store for retry. |
| `apps/api/app/models/lead.py:148-151` | `@property def organization_id(self) -> str: return str(self.broker_id)` | Treats broker_id as tenant organization_id | **PRODUCTION BLOCKER** | **REPLACE**: Add real `organization_id` column and migration; remove fake equivalence. |
| `apps/api/app/models/property_models.py:152-155` | `@property def organization_id(self) -> str: return str(self.broker_id)` | Treats broker_id as tenant organization_id | **PRODUCTION BLOCKER** | **REPLACE**: Add real `organization_id` column and migration; remove fake equivalence. |
| `apps/api/app/models/broker.py:84-87` | `@property def organization_id(self) -> str: return str(self.id)` | Treats broker_id as tenant organization_id | **PRODUCTION BLOCKER** | **REPLACE**: Broker is an actor inside an organization, not the organization itself. |
| `apps/api/app/celery_app.py:261, 267` | `"kwargs": {"tenant_id": "__all__"}` | Background Celery task processing all tenants in an unbounded loop | **PRODUCTION RISK** | **REPLACE**: Use dispatcher pattern with bounded tenant batches. |
| `apps/api/app/modules/revenue_autopilot/outreach_generator.py:127` | `gemini_key == "mock-gemini-key"` | Checks for test mock key and falls back to deterministic rule template | **DEVELOPMENT-ONLY** | **PRODUCTION SAFE**: Falls back honestly without claiming AI generation. |
| `apps/api/app/modules/knowledge/providers/ocr_provider.py` | `MockOCRProvider` | In-memory OCR for tests | **LEGITIMATE TEST** | Valid for CI unit tests; production fail-fast check in `validated_settings.py` already prevents its use in production. |
| `apps/api/app/modules/knowledge/ingestion/storage_service.py` | `MockStorageProvider` | In-memory storage for tests | **LEGITIMATE TEST** | Valid for CI unit tests; production fail-fast prevents its use when S3/local is required. |
| `apps/web/package.json:9` | `"lint": "tsc --noEmit"` | TypeScript checking masquerading as linting script | **PRODUCTION RISK** | **FIX**: Create distinct `npm run typecheck` and `npm run lint`. |

---

## 5. SUMMARY OF FOUNDATIONAL GAPS REQUIRING IMMEDIATE CONVERGENCE

1. **Tenant Identity Coupling (P0)**:
   - `Lead` and `PropertyListing` models lack actual `organization_id` database columns, relying on a `@property` hack that equates `organization_id == broker_id`.
   - Solution: Create a safe Alembic migration to add `organization_id` with foreign key to `organizations.id`, implement dual-read/dual-write logic, and establish `TenantContext` enforcement across all query execution paths.

2. **Zero Fake Success Elimination (P0)**:
   - `whatsapp_service.send_message` returns `True` when using placeholder keys.
   - `presentation/api/v1/properties.py` silently creates synthetic records (`PROP-DEMO1`, `PROP-DEMO2`) on empty reads.
   - Solution: Remove synthetic auto-seeding in production routes; convert all fake-success returns to truthful status codes (`FAILED` / `CONFIGURATION_REQUIRED`).

3. **AI Gateway Convergence (P0)**:
   - Several services (`outreach_generator`, `properties/service`, `follow_up/reengagement`, `ai_service`) still bypass `AIGateway` to make direct `google.generativeai` SDK or `httpx` HTTP calls.
   - Solution: Route all generative calls through canonical `AIGateway` with `ModelRouter`, structured outputs, and persistent `AIRequestRecord` telemetry.

4. **Action Authorization & Safety Levels (P0)**:
   - AI actions must be classified (`READ`, `SUGGEST`, `CONFIRM`, `EXECUTE`) and require server-side `AIActionAuthorization` records before executing stateful mutations.

5. **Universal Object Storage (P1)**:
   - File storage abstraction is currently restricted to the knowledge module.
   - Solution: Promote `ObjectStorageService` to canonical infrastructure with strict tenant-prefixed keys (`organizations/{org_id}/...`), MIME verification, and presigned URLs.

6. **Health Endpoint Convergence (P1)**:
   - Redundant health routes exist across `/api/v1/v1/health` and `/api/v1/v1/health-diag`.
   - Solution: Standardize on `/health/live`, `/health/ready`, and `/health/deep`.
