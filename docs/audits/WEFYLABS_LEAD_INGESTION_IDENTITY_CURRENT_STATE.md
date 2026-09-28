# WefyLabs Lead Ingestion & Identity Resolution — Current State Audit

**Generated**: September 25, 2026  
**Commit Reference**: `d20862e9dcdc191c0978e700f2d4b72baeff67fc` (branch `update-os`)  
**Scope**: Master Build 02 — Universal Lead Ingestion, Real-Time Identity Resolution & Lead Intelligence Foundation  
**Auditor**: Principal Engineer & Distributed Systems Architect  

---

## 1. Repository & Commit Context

- **Current Git Branch**: `update-os`
- **Head Commit**: `d20862e9dcdc191c0978e700f2d4b72baeff67fc` ("Update OS")
- **Foundation State**: Master Build 01 established canonical `organization_id` foreign keys on core models, fail-closed tenant scoping, unified `AIGateway`, hardened `ObjectStorageService`, and 18/18 passed tenant isolation security proofs.

---

## 2. Ingestion & Identity Subsystem Inventory

### 2.1 Lead Models & Storage
| Model | Location | Primary Tenant Key | Purpose |
| :--- | :--- | :--- | :--- |
| `Lead` | `apps/api/app/models/lead.py` | `organization_id` (UUID) | Canonical CRM lead entity holding contact, budget, score, stage, and location preferences |
| `Identity` | `apps/api/app/models/identity_models.py` | `organization_id` (String(36)) | Permanent identity node representing a unique real-world person across all sources |
| `IdentityLink` | `apps/api/app/models/identity_models.py` | `organization_id` (String(36)) | Many-to-one junction associating incoming `Lead` records to an `Identity` node |
| `IdentityAlias` | `apps/api/app/models/identity_models.py` | `organization_id` (String(36)) | Historical contact data (former phone numbers, alternate emails) |
| `OriginalPayload` | `apps/api/app/models/ingestion_models.py` | `organization_id` (String(36)) | Immutable archive of raw incoming webhook payloads |
| `IngestionLog` | `apps/api/app/models/ingestion_models.py` | `organization_id` (String(36)) | Ingestion attempt audit log tracking latency, status, idempotency keys |
| `LeadAcquisitionEvent` | `apps/api/app/models/acquisition_models.py` | `organization_id` (String(36)) | Event log of lead capture attempts per source/channel |
| `SourceAttribution` | `apps/api/app/models/acquisition_models.py` | `organization_id` (String(36)) | First-touch and last-touch marketing attribution (UTMs, campaigns, ad sets) |
| `OutboxEvent` | `apps/api/app/models/outbox_models.py` | `tenant_id` (String(64)) | Transactional Outbox for at-least-once domain event dispatch |

### 2.2 Ingestion Pipelines & Services (Competing Implementations Found)
1. **`UniversalIntakeService`** (`apps/api/app/modules/lead_acquisition/services/universal_intake_service.py`):
   - Handles `CanonicalLeadIntakeDTO`.
   - Normalizes contact data, checks idempotency via `AcquisitionEventService`.
   - Creates `SourceAttribution`, `Task` (SLA), `Notification`, `Activity`.
   - **Gaps Identified**:
     - Line 415-435: Did NOT populate `organization_id` when creating new `Lead` instances (only set `broker_id`).
     - Line 692-710: Queried `Lead.broker_id.in_(broker_ids)` instead of `Lead.organization_id == org_uuid`.
     - Did NOT persist raw payloads into `OriginalPayload`.
     - Published domain events via in-memory `event_bus.publish` rather than the transactional `OutboxEvent` table (risk of dual-write failure).
2. **`LeadIngestionPipeline`** (`apps/api/app/modules/ingestion/pipeline/ingestion_pipeline.py`):
   - Legacy ingestion engine handling `CanonicalLeadDTO`.
   - Populated `OriginalPayload` and `IngestionLog`.
   - **Gaps Identified**:
     - Also omitted `organization_id` on new `Lead` creation.
     - Lacked multi-source attribution tracking and advanced identity resolution.

---

## 3. Webhook & Connector Status

### 3.1 Meta Lead Ads (`MetaLeadAdsConnector`)
- **Location**: `apps/api/app/modules/lead_acquisition/connectors/meta_connector.py`
- **Features**: HMAC-SHA256 signature verification (`X-Hub-Signature-256`), challenge verification, Graph API retrieval, BHK/budget field mapping.
- **Status**: Production-ready connector logic; verified by tests in `test_part13_universal_lead_acquisition.py`.

### 3.2 Google Ads Lead Forms (`GoogleLeadFormConnector`)
- **Location**: `apps/api/app/modules/lead_acquisition/connectors/google_connector.py`
- **Features**: Webhook key validation (`google_key`), GCLID extraction, column parsing.
- **Status**: Production-ready connector logic; verified by tests.

### 3.3 IndiaMART & 99acres (Gaps Identified)
- **Current State**: Registered in `lead_source_registry.py` as taxonomy enums, but **NO dedicated parser or connector exists** in `apps/api/app/modules/lead_acquisition/connectors/`.
- **Requirement**: Implement canonical connectors for IndiaMART (`IndiaMartConnector`) and 99acres (`NinetyNineAcresConnector`) with deterministic payload normalization, phone cleaning, and custom question extraction.

---

## 4. Normalization & Identity Resolution Analysis

### 4.1 Phone Normalization (`normalization_service.py`)
- **Current Logic**: Checks E.164 regex, falls back to `phonenumbers` with default country "AE", strips whitespace.
- **Gap**: Lacks explicit Indian phone normalization (e.g. 10 digits starting with 6/7/8/9, `0` prefix, `91` without `+`), and does not return structured phone metadata (`phone_country`, `normalization_status`).

### 4.2 Email Normalization (`normalization_service.py`)
- **Current Logic**: Strips whitespace, lowercase, validates `@` and domain `.`.
- **Status**: Clean and production-safe.

### 4.3 Identity Resolution Engine (`app/modules/identity_resolution`)
- **Components**: `CandidateFinder`, `SimilarityEngine` (exact, phonetic, token, fuzzy), `RuleEngine`, `ConfidenceEngine`, `DecisionEngine`, `MergeExecutor`.
- **Thresholds**:
  - Confidence $\ge 0.95$: Auto-merge into existing identity node.
  - Confidence $0.85 - 0.95$: Queue for manual review.
  - Confidence $< 0.85$: Create new identity node.
- **Status**: Robust matching algorithms verified in `test_part3_identity_resolution.py`. Must be tightly integrated into the universal intake pipeline.

---

## 5. Architectural Convergence Plan for Master Build 02

```text
[Webhook / API / CSV] (Meta, Google, IndiaMART, 99acres, Website)
         │
         ▼
[Webhook Endpoint] (acquisition_controller.py)
         │ 1. Fail-closed Tenant Token Resolution (LeadSource.organization_id)
         │ 2. Signature / Key Verification
         │ 3. Raw Payload Preservation (OriginalPayload table)
         ▼
[Universal Ingestion Contract] (LeadIngestionEvent / CanonicalLeadIntakeDTO)
         │ 4. Deterministic Idempotency Key (provider + event_id / payload_hash)
         │ 5. Contact Normalization (E.164 phone with Indian format support, clean email)
         ▼
[UniversalIntakeService]
         │ 6. Identity Resolution (Phone/Email exact match -> Identity graph)
         │ 7. Lead Upsert (Existing lead updated with provenance; New lead created with organization_id)
         │ 8. First-Touch Attribution Immutability (SourceAttribution)
         │ 9. Fair Routing & Owner Preservation
         │ 10. Conversation & Activity Linking
         │ 11. Transactional Outbox (OutboxEvent persisted atomically with domain mutation)
         ▼
[Downstream Activations] (Async Celery Workers)
         ├── Lead Qualified Event
         ├── SLA First-Contact Task & Notification
         └── AI Customer Intelligence
```

---

## 6. Action Items Checklist

1. [ ] **Universal Ingestion Contract**: Enrich `CanonicalLeadIntakeDTO` to serve as the unified `LeadIngestionEvent` contract across all sources.
2. [ ] **Raw Event Preservation**: Ensure `OriginalPayload` is archived in `UniversalIntakeService` before destructive normalization.
3. [ ] **Strict Phone Normalization**: Enhance `normalize_phone` to handle Indian mobile numbers (`+91`, `0`, 10 digits starting with 6-9), return `(normalized_phone, confidence, country, status)`.
4. [ ] **IndiaMART Connector**: Implement `IndiaMartConnector` handling JSON/XML push payloads and query parameters.
5. [ ] **99acres Connector**: Implement `NinetyNineAcresConnector` handling real-estate portal enquiry formats.
6. [ ] **Tenant Scoping & Lead Creation Repair**:
   - Ensure `organization_id=org_uuid` is explicitly saved on `Lead`.
   - Update `_find_lead_by_phone` and `_find_lead_by_email` to filter on `Lead.organization_id == org_uuid`.
7. [ ] **Transactional Outbox Integration**: Replace direct in-memory event publishing with atomic `OutboxEvent` creation.
8. [ ] **Automated Ingestion Test Suite**: Create `tests/test_master_build_02_ingestion_identity.py` validating:
   - Meta Ads ingestion & idempotency.
   - Google Ads ingestion & idempotency.
   - IndiaMART ingestion & normalization.
   - 99acres ingestion & normalization.
   - Cross-channel deduplication to single Identity node.
   - First-touch attribution preservation.
   - Transactional outbox event creation.
