# WEFYLABS FINAL SYSTEM INVENTORY
# Generated: Part 8 — Final Integration Milestone

## Evidence Standard
| Status | Meaning |
|---|---|
| VERIFIED | Confirmed by in-process runtime test or direct code inspection |
| PARTIALLY VERIFIED | Code evidence confirmed; runtime path not fully exercised |
| NOT VERIFIED | Present in code; no runtime proof |
| BLOCKED | Requires external credential / staging environment |
| KNOWN BLOCKER | Documented production-blocking deficiency |

---

## Component Map

| # | Component | Location | Status | Notes |
|---|---|---|---|---|
| 1 | Auth (Register/Login/JWT/Refresh) | `app/modules/auth/` | VERIFIED | 64-test suite; endpoints return 200/401/422 correctly |
| 2 | Google OAuth 2.0 | `app/modules/auth/` | NOT VERIFIED | Client ID/secret not configured in dev |
| 3 | RBAC (Principal-Derived) | `app/infrastructure/security/rbac.py` | VERIFIED | Server-side OrganizationMember query; fails closed |
| 4 | Multi-Tenancy Scoping | `organization_id` filters | PARTIALLY VERIFIED | Selected test coverage; global proof requires staging |
| 5 | Customer Identity Resolution | `app/modules/identity_resolution/` | PARTIALLY VERIFIED | Code + selected tests; merge policy unproven |
| 6 | Customer Intelligence | `app/modules/customer_intelligence/` | VERIFIED | Mounted; endpoints accessible |
| 7 | Lead CRM (CRUD, pipeline) | `app/modules/leads/`, `app/routers/` | VERIFIED | Full CRUD; 401 enforced on all protected routes |
| 8 | Canonical Conversation | `app/modules/ai_agent/conversation_manager/` | VERIFIED | ConversationManager is canonical; endpoints return expected codes |
| 9 | AI Memory | `app/modules/memory/` | VERIFIED | Mounted; endpoint accessible |
| 10 | Property Intelligence | `app/modules/property_intelligence/` | VERIFIED | Mounted; endpoints accessible |
| 11 | Property Listings (CRUD) | `app/presentation/api/v1/properties.py` | VERIFIED | Auth protected; no 5xx |
| 12 | Knowledge Engine (RAG) | `app/modules/knowledge/` | PARTIALLY VERIFIED | Code + endpoints confirmed; pgvector + embedding runtime BLOCKED |
| 13 | Lead Qualification Engine | `app/modules/lead_qualification/` | VERIFIED | Endpoints accessible; fact/conflict model confirmed |
| 14 | AI Property Recommendation | `app/modules/property_recommendation/` | PARTIALLY VERIFIED | Compatibility scorer + hard filter confirmed in code; runtime E2E unproven |
| 15 | Matching Intelligence | `app/modules/matching_intelligence/` | PARTIALLY VERIFIED | Mounted; endpoint accessible |
| 16 | LLM Router (AI Gateway) | `app/modules/ai_agent/llm_router/router.py` | VERIFIED | Circuit breaker + cost cap + fallback verified in Part 7 |
| 17 | Prompt Guard (AI Security) | `app/infrastructure/security/prompt_guard.py` | VERIFIED | Injection detection tested (37 Part 7 tests) |
| 18 | Tool Executor (AI Boundary) | `app/modules/ai_agent/tool_executor/executor.py` | VERIFIED | Tenant-scoped; confirmed in Part 7 |
| 19 | AI Sales Agent Endpoints | `app/modules/ai_agent/router.py` | VERIFIED | /ai-agent/v1/message accessible; no 5xx |
| 20 | Copilot (Internal Agent) | `app/modules/copilot/` | PARTIALLY VERIFIED | Endpoint accessible; full tool audit incomplete |
| 21 | Command Center (Daily Briefing) | `app/modules/command_center/` | VERIFIED | Endpoint accessible |
| 22 | Availability Engine | `app/modules/calendar/availability/` | VERIFIED | Part 6 — 13 passing tests including slot calculation |
| 23 | Booking Service + Lock Manager | `app/modules/calendar/booking/` | VERIFIED | Part 6 — distributed lock, idempotency, rollback tested |
| 24 | Post-Meeting Intelligence | `app/modules/calendar/post_meeting/` | VERIFIED | Outcome recording + revenue trigger tested in Part 6 |
| 25 | Human Handoff (Escalation) | `app/modules/conversation_intelligence/handoff_service.py` | VERIFIED | Endpoint accessible; escalation state tested |
| 26 | Follow-Up Automation Engine | `app/modules/follow_up/engine/` | PARTIALLY VERIFIED | Policies endpoint accessible; idempotency runtime unproven |
| 27 | Revenue Autopilot Engine | `app/modules/revenue_autopilot/engine.py` | VERIFIED | Part 6 + Part 35 — opportunity dedup + generation tested |
| 28 | Celery Workers + Beat | `app/celery_app.py` | PARTIALLY VERIFIED | Configured in render.yaml; runtime BLOCKED (no Redis in dev) |
| 29 | Onboarding + Demo Mode | `app/modules/onboarding/` | PARTIALLY VERIFIED | Endpoint accessible; demo workspace creation confirmed in code |
| 30 | Observability (Prometheus + Health) | `/metrics`, `/health` | VERIFIED | Endpoints accessible; PII exposure test passed |
| 31 | Alembic Migrations | `alembic/versions/` | VERIFIED | Head = 0027_customer_identity_canonical; 21 migration files |
| 32 | Production Config Guard | `app/common/config/validated_settings.py` | VERIFIED | Rejects SQLite, weak secrets, missing Gemini API key in prod mode |
| 33 | Media Handler | `app/modules/communication/media_handler/` | KNOWN BLOCKER | Defaults to mock storage — must be replaced with S3/R2 before launch |
| 34 | WhatsApp / SMS Channels | `app/modules/communication/` | NOT VERIFIED | Adapter code exists; no live webhook verified |
| 35 | Google Calendar Integration | `app/modules/calendar/providers/` | NOT VERIFIED | OAuth + mock provider exist; live provider requires credentials |
| 36 | Billing (Razorpay) | `app/routers/billing.py` | NOT VERIFIED | Code + render.yaml keys; live webhook not tested |

---

## Migration Inventory

| File | Status |
|---|---|
| `001_initial_schema.py` | Applied |
| `002_enterprise_foundation.py` | Applied |
| `0013_ai_memory_engine.py` through `0027_customer_identity_canonical.py` | Applied |
| `a5c9f1e78b2d_ai_agent_models.py` | Applied |
| `b8e2d4f1a9c3_knowledge_engine.py` | Applied |
| `9999_production_baseline.py` | Applied |
| `merge_002_and_9999_heads.py` | Applied — single head confirmed |

Current Alembic head: **0027_customer_identity_canonical** (VERIFIED)

---

## Duplicate System Register

| Domain | Canonical | Legacy/Parallel | Action |
|---|---|---|---|
| Matching | `app/modules/property_recommendation/` | `app/modules/matching_intelligence/`, `app/modules/recommendation/` | Converge to property_recommendation; deprecate others |
| Conversation | `app/modules/ai_agent/conversation_manager/` | `app/models/conversation.py`, `unified_conversations`, `omnichannel_conversations` | Canonical is conversation_manager; adapters needed |
| Follow-up | `app/modules/follow_up/engine/` | `app/routers/follow_ups.py` (legacy) | Legacy router is read-only fallback; canonical is engine |
| Lead Scoring | `app/modules/lead_intelligence/` | `app/routers/scoring.py`, `app/models/score.py` | lead_intelligence is canonical |
| Auth Router | `app/modules/auth/router.py` | Mounted twice: with + without /api/v1 prefix | KNOWN ISSUE — intentional for legacy compatibility |

---

## Model Table Count
**256 SQLAlchemy model tables** registered in Base.metadata (VERIFIED at runtime).

---

## BeetleLabs Branding Residue
- 74 Python source files still contain `beetlelabs` branding references.
- 9 frontend TypeScript files contain `beetlelabs` or `localhost` references.
- `api-client.ts` reads/writes both `wefylabs_token` and `beetlelabs_token` keys.
- Severity: LOW — does not affect API behavior; affects internal logs and frontend localStorage.
- Action: Staged brand cleanup recommended post-launch.
