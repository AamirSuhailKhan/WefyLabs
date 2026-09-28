# WefyLabs Deprecation & Migration Map

**Document Version**: 1.0  
**Status**: ACTIVE MIGRATION TRACKER  
**Mandate**: Never leave duplicate competing implementations indefinitely. Every duplicate is classified with an explicit replacement and removal condition.

---

## 1. Domain Deprecation Ledger

| Component / Subsystem | Legacy Implementation | Canonical Replacement | Action | Migration Status | Removal Condition |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tenant Scoping** | Direct `broker_id` column used as tenant boundary on `leads`, `property_listings`, `conversations` | `organization_id` (UUID foreign key to `organizations.id`) | **MERGE / REPLACE** | Migration `0035` deployed; dual-read/write active | When all brokers belong to valid organizations and backfill validation passes |
| **AI Client SDK** | Legacy `google.generativeai` direct imports across disparate services | `app.infrastructure.ai_gateway.gateway.AIGateway` using Google GenAI SDK (`google.genai`) | **REPLACE** | 100% completed (0 legacy SDK imports in codebase) | Dependencies removed from pyproject / poetry in next cleanup |
| **Health Endpoints** | Redundant mounts: `/api/v1/v1/health`, `/api/v1/v1/health-diag` | Unified `/health/live`, `/health/ready`, `/health/deep`, `/health/capabilities` | **MERGE** | Canonical router active; backward-compatible aliases preserved | Frontend updated to canonical paths in Phase 2 |
| **Storage Engine** | `MockStorageBackend` with in-memory / temporary dict storage | `app.infrastructure.storage.object_storage.ObjectStorageService` | **REPLACE** | Canonical service active with MIME/magic-byte checks & signed URLs | Remove `MockStorageBackend` file |
| **WhatsApp Provider** | Simulated success when `d360_key_placeholder` supplied | Real HTTP provider call with truthful boolean failure and logging | **REPLACE** | Active in `WhatsAppService` | Fully verified |
| **Property Demo Seeding** | Auto-injection of `PROP-DEMO1` and `PROP-DEMO2` in `GET /api/v1/properties/` | Explicit DB querying scoped to authenticated `organization_id` | **REMOVE** | Removed from `properties.py` controller | Fully verified |
| **Frontend Gates** | `npm run lint` running `tsc --noEmit` | Clean separation: `npm run typecheck` (`tsc --noEmit`) and `npm run lint` (`next lint`) | **REPLACE** | Active in `apps/web/package.json` | Fully verified |
| **AI Action Authorization** | Implicit tool execution without server-side verification token | `AIActionAuthorization` record validation (`pending` -> `authorized` -> `executed`) | **REPLACE** | Active in `ai_foundation_models.py` and tools | All tools migrated to check authorization tokens |

---

## 2. Codebase Convergence Matrix

### 2.1 AI Services Convergence
```text
[LEGACY] apps/api/app/modules/revenue_autopilot/outreach_generator.py (google.generativeai)
  └──► CONVERGED TO: AIGateway.generate_completion(task="outreach")

[LEGACY] apps/api/app/modules/follow_up/ai_reengagement/reengagement_service.py (google.generativeai)
  └──► CONVERGED TO: AIGateway.generate_completion(task="reengagement")

[LEGACY] apps/api/app/modules/properties/service.py (generate_ai_description direct call)
  └──► CONVERGED TO: AIGateway.generate_completion(task="property_description")

[LEGACY] apps/api/app/services/ai_service.py (generate_ai_qualification_response direct call)
  └──► CONVERGED TO: AIGateway.generate_completion(task="qualification")
```

### 2.2 Storage Convergence
```text
[LEGACY] In-memory mock storage / hardcoded static URLs
  └──► CONVERGED TO: ObjectStorageService
         ├── upload(content, organization_id, resource_type, resource_id, filename)
         ├── download(organization_id, object_key)
         ├── delete(organization_id, object_key)
         └── generate_signed_url(organization_id, object_key, expires_in)
```

### 2.3 Tenant Context Convergence
```text
[LEGACY] X-Broker-Id header guessing / Single-broker tenancy
  └──► CONVERGED TO: resolve_organization_id_for_broker()
         ├── Primary: Header `X-WefyLabs-Organization-Id`
         ├── Secondary: `organization_members` junction table
         └── Fallback (Dual-read migration window only): broker.id
```
