# WEFYLABS — UNIVERSAL LEAD INGESTION ARCHITECTURE

## 1. Architectural Scope & Pipeline Overview
This document specifies the authoritative universal lead ingestion architecture for WefyLabs Real Estate AI Revenue Operating System.

All external inbound streams—Meta Lead Ads, Google Ads Lead Forms, IndiaMART CRM Push, 99acres Portal Enquiries, Website forms, WhatsApp webhooks, and REST APIs—converge into a single deterministic ingestion pipeline.

```text
SOURCE
  ↓
RAW EVENT ARCHIVE (OriginalPayload — Immutable)
  ↓
INGESTION RECEIPT & AUDIT (IngestionLog — Latency & Attempt Tracking)
  ↓
IDEMPOTENCY VERIFICATION (Tenant-Scoped SHA-256 Idempotency Key)
  ↓
CANONICAL NORMALIZATION (PhoneNormalizationResult E.164 + Canonical Email)
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
ASYNC WORKERS & OBSERVABILITY (Audit Log & Domain Event Publishing)
```

---

## 2. Ingestion Contracts & Taxonomy

### 2.1 Universal Ingestion Contract (`CanonicalLeadIntakeDTO`)
Every source translates into `CanonicalLeadIntakeDTO` before core domain processing:
- `source_type`: `UniversalSourceType` (`WEBSITE`, `META`, `GOOGLE`, `INDIAMART`, `99ACRES`, `WHATSAPP`, `API`, `CSV`, `MANUAL`)
- `external_source`: Origin identifier (e.g., `meta_lead_ads`, `google_lead_form`, `indiamart`, `99acres`)
- `external_lead_id`: Provider-assigned submission/lead ID for idempotency tracking
- `name`, `phone`, `email`, `message`
- Real-estate parameters: `property_type`, `transaction_type`, `property_id`, `budget`, `currency`, `preferred_locations`, `city`
- Marketing attribution: `utm_source`, `utm_medium`, `utm_campaign`, `source_metadata`
- Idempotency key: Explicit or deterministic hash of `provider:external_id`

### 2.2 Raw Event Preservation (`OriginalPayload`)
Before any mutation or destructive normalization:
- Archived in `original_payloads` table.
- Stores: `id`, `ingestion_id`, `organization_id`, `source`, `raw_payload_json`, `headers_json`, `ip_address`, `created_at`.
- Guaranteed auditability and zero data loss.

---

## 3. Provider Connectors

### 3.1 Meta Lead Ads (`MetaLeadAdsConnector`)
- Signature verification: HMAC-SHA256 over raw request body using `X-Hub-Signature-256`.
- Webhook verification: Responds to GET hub challenge.
- Normalized mapping: Parses `field_data` array into contact info and custom real estate questions (BHK, Budget, Timeline, Preferred Location).

### 3.2 Google Ads Lead Form (`GoogleLeadFormConnector`)
- Key verification: Constant-time comparison of `google_key` configured in Google Ads asset.
- Normalized mapping: Parses `user_column_data`, `gclid`, and real estate questions.

### 3.3 IndiaMART CRM Push (`IndiaMartConnector`)
- Key verification: Constant-time comparison against `glusr_crm_key`.
- Normalized mapping: Extracts `UNIQUEQUERYID`, `SENDER_NAME`, `SENDER_MOBILE`, `SENDER_EMAIL`, `QUERY_PRODUCT_NAME`, `QUERY_MESSAGE`, `SENDER_CITY`.
- Real-estate extraction: Automatic regex extraction for BHK configurations and Indian budget representations (e.g. `1.5 Cr`, `75 Lakhs`).

### 3.4 99acres Real Estate Portal (`NinetyNineAcresConnector`)
- Key verification: Constant-time comparison against `portal_key`.
- Normalized mapping: Extracts `enquiry_id`, `cust_name`, `contact_num`, `cust_email`, `property_id`, `property_type`, `budget`, `locality`.

---

## 4. Normalization Engine

### 4.1 Phone Normalization (`PhoneNormalizationResult`)
- Primary standard: **E.164**
- Normalizes Indian formats:
  - 10 digits (`9876543210` -> `+919876543210`)
  - 11 digits with 0 (`09876543210` -> `+919876543210`)
  - 12 digits with 91 (`919876543210` -> `+919876543210`)
- Normalizes WhatsApp identifiers (`@c.us`, `@s.whatsapp.net`, `whatsapp:`).
- Normalizes international dialing prefix (`00...` -> `+...`).
- Exposes tuple unpack compatibility: `phone, conf = normalize_phone(...)`.

### 4.2 Email Normalization
- Trims whitespace, lowercases.
- Validates syntax.
- Generates stable SHA-256 fingerprint ignoring aliases and dots for duplicate detection while preserving original email.

---

## 5. Transactional Outbox Pattern
To prevent dual-write loss between database transactions and message queues:
- An `OutboxEvent` is inserted within the same database transaction as `Lead` creation.
- Fields: `event_id`, `tenant_id`, `event_type`, `aggregate_type`, `aggregate_id`, `payload`, `status="PENDING"`.
- Asynchronous pollers/dispatchers deliver outbox records with at-least-once reliability and exponential backoff.
