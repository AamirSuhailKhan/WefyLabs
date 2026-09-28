# WefyLabs Canonical Architecture

**Architecture Specification Version**: 1.0  
**Status**: APPROVED & CANONICAL  
**System Target**: Real Estate AI Revenue Operating System  

---

## 1. Core Architectural Principle

> **ONE SOURCE OF TRUTH PER DOMAIN**

The system does not permit duplicate or competing implementations of the same business domain. Every entity is classified strictly as a canonical source of truth or an explicit projection, adapter, or view.

```text
TRAFFIC
  ↓
LEAD CAPTURE
  ↓
LEAD INGESTION
  ↓
NORMALIZATION
  ↓
IDENTITY RESOLUTION
  ↓
DEDUPLICATION
  ↓
ENRICHMENT
  ↓
LEAD INTELLIGENCE
  ↓
AI QUALIFICATION
  ↓
PROPERTY DISCOVERY
  ↓
PROPERTY MATCHING
  ↓
CONVERSATION
  ↓
FOLLOW-UP
  ↓
APPOINTMENT
  ↓
SITE VISIT
  ↓
SALES HANDOFF
  ↓
OPPORTUNITY
  ↓
NEGOTIATION
  ↓
BOOKING
  ↓
REVENUE
  ↓
LEARNING
```

---

## 2. Multi-Tenant Identity Model

### 2.1 The Cardinal Rule
```text
ORGANIZATION = CUSTOMER TENANT
USER / BROKER = PERSON OPERATING INSIDE TENANT
```
Under no circumstances is `organization_id == broker_id` treated as a valid architectural assumption.

### 2.2 Canonical Tenant Entity Mapping
All tenant-owned database entities must include `organization_id` (UUID foreign key referencing `organizations.id` with `ON DELETE CASCADE`):

```text
Organization (organizations)
  ├── OrganizationMember (organization_members) ── User/Broker (brokers)
  ├── Workspace (workspaces)
  ├── Lead (leads) [organization_id]
  ├── PropertyListing (property_listings) [organization_id]
  ├── Conversation (conversations) [organization_id]
  ├── Meeting / Site Visit (meetings) [organization_id]
  ├── Task (tasks) [organization_id]
  ├── OutboxEvent (outbox_events) [tenant_id]
  ├── AIRequestRecord (ai_request_records) [organization_id]
  └── AIActionAuthorization (ai_action_authorizations) [organization_id]
```

### 2.3 Actor / Ownership Fields
Tenant isolation is strictly maintained by `organization_id`. Actor accountability is recorded via dedicated fields:
- `owner_user_id` / `broker_id`
- `assigned_agent_id`
- `created_by_user_id`
- `updated_by_user_id`

---

## 3. High-Level Architectural Flow

```text
Frontend (Next.js 15)
       │ HTTP / JSON (Bearer JWT + X-WefyLabs-Organization-Id)
       ▼
Edge & API Routing (FastAPI)
       │
       ├─► Health Probes (/health/live, /health/ready, /health/deep)
       │
       ▼
Authentication & Tenant Context Resolver (app.infrastructure.tenancy.scope)
       │ Resolves & Validates OrganizationContext (Fails closed: 403 on boundary violation)
       ▼
Domain Services Plane
       ├── PropertyService (app.modules.properties.service)
       ├── LeadService / Ingestion (app.modules.leads.service)
       ├── RegionalPipelineService (app.modules.pipeline.service)
       └── CommunicationService (app.services.whatsapp_service, email, sms)
       │
       ├─────────────────────────────────┬────────────────────────────────┐
       ▼                                 ▼                                ▼
AI Gateway & Router              Transactional Outbox            Object Storage Service
(AIGateway / ModelRouter)        (OutboxEvent / Celery)        (ObjectStorageService)
       │                                 │                                │
       ▼                                 ▼                                ▼
Google GenAI SDK               Broker Message Queues            Tenant-Scoped Disk/S3
(Gemini 2.5 Flash / Pro)         (Redis / Celery)               (organizations/{org_id}/...)
```

---

## 4. AI Gateway & Action Security Architecture

### 4.1 Canonical AI Gateway Flow
No domain service or controller may instantiate direct external AI provider clients. All generative model invocations flow through `AIGateway`:

```text
AI Request
    ↓
AI Gateway (app.infrastructure.ai_gateway.gateway)
    ↓
Tenant Context Validation
    ↓
Task Policy & Token Budget Check
    ↓
Context Builder (Prompt Assembly)
    ↓
Model Router (Gemini 2.5 Flash for latency, 2.5 Pro for complex reasoning)
    ↓
Structured JSON Output Validation
    ↓
Observability Record (ai_request_records)
    ↓
Tool / Action Proposal
```

### 4.2 Action Authorization Model (Prompt §24 & §25)
AI systems are strictly forbidden from self-authorizing state mutations. Mutating operations (booking visits, changing statuses, reserving inventory) follow the Action Authorization Plane:

1. **AI Proposes**: LLM produces structured action proposal with parameters.
2. **Parameters Hashed**: A deterministic SHA-256 hash of parameters is generated.
3. **Human Confirmation**: The operator/broker reviews proposed action in the UI.
4. **Server Authorization**: `AIActionAuthorization` record is created with status `authorized`, expiry time (e.g. 2 hours), and idempotency key.
5. **Tool Execution**: The tool retrieves the authorization record, verifies that `parameters_hash` matches, executes the domain side effect, and marks status as `executed`.

```text
Safety Levels:
- READ:      Search properties, read leads, query inventory (Auto-executable)
- SUGGEST:   Draft outreach, recommend properties (No side effect)
- CONFIRM:   Book appointments, assign leads, change statuses (Requires Authorization)
- EXECUTE:   Financial transactions, contract generation (Requires Strict RBAC + Authorization)
```

---

## 5. Storage Architecture

All media and documents adhere to the `ObjectStorageService` standard:
- **Tenant Scoping**: All keys must begin with `organizations/{organization_id}/`. Cross-tenant retrieval raises `PermissionError`.
- **Pre-Storage Gate**: `FileSecurityScanner` inspects file magic bytes (preventing spoofed `.exe` disguised as `.png`), checks whitelisted extensions, and validates file size limits (15MB).
- **Time-Limited Signed URLs**: Temporary HMAC-SHA256 tokens are generated for media delivery, preventing persistent public exposure of private contracts and KYC records.

---

## 6. Zero Fake Success Contract

The system upholds a strict truthfulness policy across all execution boundaries:
- Operational exceptions must never be caught and transformed into synthetic success.
- External provider downtime (e.g., WhatsApp API key unconfigured) returns explicit error indicators (`status="FAILED"`, `False`, or HTTP 503) rather than simulated completions.
- Demo seed records (`PROP-DEMO1`, `demo-lead-1`) are quarantined from production routes.

---

## 7. Database Migration & Schema Evolution

- **Source of Truth**: Alembic migrations under `apps/api/alembic/versions/`.
- **Safe Rollout Strategy**:
  1. `ADD`: Add nullable column / new tables (`0035_canonical_tenant_foundation.py`).
  2. `BACKFILL`: Map legacy data (`broker_id` -> `organization_id`) using `organization_members`.
  3. `DUAL-READ / DUAL-WRITE`: Services read `organization_id` falling back to `broker_id` if unmigrated; writes populate both.
  4. `VALIDATE`: Run test matrix proving 0 cross-tenant leakage.
  5. `SWITCH`: Enforce `NOT NULL` on `organization_id`.
  6. `REMOVE LEGACY`: Retire deprecated columns.
