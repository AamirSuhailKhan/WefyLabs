# WEFYLABS — MASTER BUILD 02 SPECIFICATION

## Universal Lead Ingestion, Real-Time Identity Resolution & Lead Intelligence Foundation

### 1. Executive Summary
Master Build 02 establishes the production-grade, deterministic, idempotent, and tenant-safe lead ingestion and identity convergence architecture for WefyLabs. It converges all external lead channels—including Meta Lead Ads, Google Ads Lead Forms, IndiaMART CRM Push, and 99acres Portal Enquiries—into a unified transactional pipeline with immutable raw event archiving, cross-channel identity graph deduplication, and transactional outbox guarantees.

---

### 2. Canonical Ingestion Pipeline Architecture

```text
SOURCE (Meta, Google, IndiaMART, 99acres, Website, API)
  ↓
RAW EVENT ARCHIVE (OriginalPayload — Immutable Record)
  ↓
INGESTION RECEIPT & AUDIT (IngestionLog — Latency & Attempt Tracking)
  ↓
IDEMPOTENCY VERIFICATION (SHA-256 Idempotency Key Scoped to Tenant)
  ↓
CANONICAL NORMALIZATION (E.164 Strict Phone Normalization + Email Canonicalization)
  ↓
TENANT RESOLUTION (Verified LeadSource Integration Credential — Fail-Closed)
  ↓
IDENTITY RESOLUTION & DEDUPLICATION (Identity Graph + IdentityLink Scoped to Tenant)
  ↓
LEAD UPSERT (Lead.organization_id Scoped Persistence + Owner Preservation)
  ↓
ATTRIBUTION ENGINE (SourceAttribution — First-Touch Immutable, Last-Touch Updated)
  ↓
OPERATIONAL ACTIVATION (15-Minute SLA Task + Agent Notification)
  ↓
TRANSACTIONAL OUTBOX (OutboxEvent Atomic Insertion — Dual-Write Elimination)
  ↓
ASYNC WORKERS & OBSERVABILITY (Metrics & Audit Recording)
```

---

### 3. Key Components Implemented

#### 3.1 Normalization Pipeline (`normalization_service.py`)
- **`PhoneNormalizationResult`**: Backward-compatible tuple subclass `(normalized_phone, confidence)` exposing `.normalized_phone`, `.confidence`, `.raw_phone`, `.phone_country`, and `.normalization_status`.
- **E.164 Indian Phone Formats**:
  - 10 digits (`9876543210` -> `+919876543210`, status: `formatted`, country: `IN`)
  - 11 digits trunk 0 (`09876543210` -> `+919876543210`, status: `formatted`, country: `IN`)
  - 12 digits 91 prefix (`919876543210` -> `+919876543210`, status: `formatted`, country: `IN`)
  - Valid E.164 (`+919876543210` -> `+919876543210`, status: `valid`, country: `IN`, confidence: `1.0`)
- **WhatsApp & URI Parsing**: Automatically strips `@c.us`, `@s.whatsapp.net`, `whatsapp:`, and `tel:` prefixes.
- **International Prefixes**: Normalizes `00...` international dialing prefixes (e.g. `00971501234567` -> `+971501234567`, country: `AE`).
- **Uncertainty & Rejection**: Sub-7-digit strings or non-numeric garbage are marked `invalid` with `0.0` confidence and return `None`.

#### 3.2 IndiaMART CRM Push Connector (`indiamart_connector.py`)
- **Connector**: `IndiaMartConnector`
- **Authentication**: Constant-time HMAC comparison via `hmac.compare_digest` against `glusr_crm_key`.
- **Payload Extraction**:
  - `UNIQUEQUERYID` -> `external_id` (deterministic idempotency)
  - `SENDER_NAME` -> `name`
  - `SENDER_MOBILE` -> `phone`
  - `SENDER_EMAIL` -> `email`
  - `QUERY_PRODUCT_NAME` & `QUERY_MESSAGE` -> Real-estate BHK, property type (Apartment, Villa, Plot, Commercial), budget, and location extraction.
  - Synthesizes clean customer enquiry messages and structured source metadata.

#### 3.3 99acres Real Estate Portal Connector (`ninety_nine_acres_connector.py`)
- **Connector**: `NinetyNineAcresConnector`
- **Authentication**: Constant-time key comparison against `portal_key`.
- **Payload Extraction**:
  - `enquiry_id` / `lead_id` -> `external_id`
  - `cust_name` -> `name`
  - `contact_num` / `cust_phone` -> `phone`
  - `cust_email` -> `email`
  - `property_id` -> `property_id`
  - `bhk` / `unit_type` -> `property_type`
  - `budget` -> `budget`
  - `locality` / `city` -> `preferred_locations`

#### 3.4 Raw Event Preservation (`OriginalPayload`)
- Before executing business logic or transformations, the raw incoming webhook or API payload is archived immutably in `original_payloads` table.
- Stores: `id`, `ingestion_id`, `organization_id`, `source`, `raw_payload_json`, `headers_json`, `ip_address`, and `created_at`.
- Guarantees complete auditability, re-playability, and debugging evidence.

#### 3.5 Transactional Outbox Engine (`OutboxEvent`)
- In the same database transaction as `Lead` creation, `IdentityLink` creation, and `Task` creation, an `OutboxEvent` record is persisted.
- Attributes:
  - `tenant_id`: String UUID of the organization
  - `event_type`: `lead.ingested` (or `lead.reengaged` for duplicates)
  - `aggregate_type`: `Lead`
  - `aggregate_id`: Lead UUID
  - `payload`: Structured JSON payload including lead ID, phone, email, name, source, and event ID
  - `status`: `PENDING`
  - `idempotency_key`: `outbox:<event_id>`
- Eliminates dual-write vulnerabilities between database commits and message bus / Celery dispatch.

#### 3.6 Tenant Boundary & Scoping Enforcement
- `Lead.organization_id`: Directly populated upon creation (`lead = Lead(organization_id=org_uuid, ...)`).
- `_find_lead_by_phone` & `_find_lead_by_email`: Filter directly on `Lead.organization_id == org_uuid` (with fallback to eligible broker IDs).
- Complete isolation: If Tenant A and Tenant B receive leads with the identical phone number, they resolve into separate, isolated leads within their respective tenant silos.

---

### 4. Verification Summary
- **Master Build 02 Test Suite** (`test_master_build_02_ingestion_identity.py`): **17 / 17 tests PASSED**.
- **Master Build 01 Security Matrix** (`test_tenant_matrix_security.py`): **18 / 18 tests PASSED**.
- **Universal Lead Acquisition Suites** (`test_part13...` & `test_part21...`): **92 / 92 tests PASSED**.
- **Frontend Type Safety** (`apps/web`): **0 TypeScript errors (`tsc --noEmit`)**.
