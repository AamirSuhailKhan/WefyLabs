# WEFYLABS PART 13: UNIVERSAL LEAD ACQUISITION ARCHITECTURE

## 1. Executive Architecture Summary

WefyLabs Part 13 implements universal, production-grade lead acquisition for **Meta Lead Ads** and **Google Ads Lead Forms**, seamlessly connecting both external advertising platforms into the canonical Part 9 Universal Lead Intake pipeline.

### Core Architectural Principle
**Single Unified Acquisition Pipeline**: Under no circumstances does Part 13 introduce a second CRM, a second lead ingestion system, a second customer identity engine, a second attribution store, or a separate event bus. Every lead from Meta and Google Ads enters through the canonical `UniversalIntakeService`, normalizes into `CanonicalLeadPayload`, resolves identity via `IdentityService`, applies deduplication, registers multi-touch attribution via Part 11 Revenue Intelligence, initiates auto-routing, triggers first-contact SLA timers, activates the AI Workforce, and integrates with the Part 12 Communication Hub.

```
AD SOURCE (Meta Lead Ads / Google Ads Lead Forms)
      │
      ▼
PROVIDER WEBHOOK / RETRIEVAL
      │
      ├─► Server-side Tenant Resolution & Auth (HMAC-SHA256 / google_key)
      ├─► Fast 200 OK Provider Acknowledgment (Lead Loss Prevention)
      │
      ▼
PROVIDER CONNECTOR / ADAPTER (MetaConnector / GoogleConnector)
      │
      ▼
CANONICAL LEAD PAYLOAD (CanonicalLeadPayload)
      │
      ▼
UNIVERSAL INGESTION PIPELINE (UniversalIntakeService)
      │
      ├─► Idempotency & Raw Event Ledger (LeadAcquisitionEvent)
      ├─► Deterministic Field Normalization (E.164 Phone, Email, Budget, BHK)
      ├─► Customer Identity Resolution (IdentityService / CustomerProfile)
      ├─► Deduplication & Ingestion Strategy (CREATE vs UPDATE)
      │
      ▼
CANONICAL LEAD RECORD (Lead)
      │
      ├─► Source & Campaign Attribution (SourceAttribution / Revenue Intelligence)
      ├─► Workload-Aware Auto-Routing (LeadRoutingService)
      ├─► First-Contact SLA Activation (SLA Task Engine)
      ├─► AI Workforce Activation (AgentRouter / Lead Intelligence)
      ├─► Omnichannel Follow-Up (Part 12 Communication Hub)
      └─► Revenue Autopilot & Closed-Loop Attribution
```

---

## 2. Meta Lead Ads Integration Architecture

### 2.1 Webhook Verification & Graph API Retrieval
- **Challenge Verification**: Complies with Meta's webhook handshake protocol via `GET /api/v1/lead-acquisition/webhooks/meta`. Validates `hub.mode == "subscribe"` and matches `hub.verify_token` against the tenant's configured webhook secret. Returns the integer challenge directly to Meta.
- **HMAC-SHA256 Payload Signature Verification**: Every incoming `POST` webhook contains an `X-Hub-Signature-256` header. The server computes `hmac.new(app_secret, raw_payload, sha256)` and performs constant-time comparison (`hmac.compare_digest`). Unsigned or forged requests are rejected with `401 Unauthorized`.
- **Graph API Lead Retrieval (v19.0)**: Meta leadgen webhooks transmit lightweight change notifications (`leadgen_id`, `page_id`, `form_id`, `ad_id`, `created_time`). The connector fetches the full lead details securely via `GET https://graph.facebook.com/v19.0/{leadgen_id}` using the tenant's page or system user access token.
- **Asynchronous Decoupling**: Provider webhooks acknowledge receipt with `200 OK` within milliseconds, dispatching lead retrieval and downstream processing to background workers (`fetch_and_ingest_meta_lead`) to prevent webhook timeouts.

### 2.2 Normalization & Custom Question Extraction
Meta forms provide an array of `field_data` containing `name` and `values`. The connector deterministically maps real estate questions into canonical attributes:
- `full_name`, `first_name`, `last_name`
- `email` (lowercased, whitespace-stripped)
- `phone_number` (converted to E.164 format with default country code fallback)
- Real estate requirements: `budget` (normalized integer currency in INR), `bhk`, `preferred_location`, `timeline`, `purpose` (investment vs end-use).
- All unmapped custom form questions are preserved in `custom_fields` with provenance.

---

## 3. Google Ads Lead Form Integration Architecture

### 3.1 Webhook Authentication & Dual-Format Support
- **Key Verification**: Inbound Google Ads Lead Form webhook submissions include a user-configured `google_key`. The endpoint validates this key against the tenant's configured lead source secret.
- **Dual Schema Support**:
  1. **Webhook Payload Format**: Real-time HTTP POST format (`lead_id`, `form_id`, `campaign_id`, `gclid`, `user_column_data` array).
  2. **Google Ads API Format**: Batch retrieval format (`leadFormSubmissionData`, `columnData`, `gclid`).
- **GCLID & Ad Metadata**: Captures Google Click Identifier (`gclid`), `campaign_id`, `ad_group_id`, and `creative_id` directly into the canonical attribution model.

### 3.2 Field Normalization
- Extracts standard Google Ads column IDs: `FULL_NAME`, `FIRST_NAME`, `LAST_NAME`, `EMAIL`, `PHONE_NUMBER`, `CITY`, `POSTAL_CODE`.
- Parses custom real estate questions: Budget ranges, bedroom requirements (BHK), purchase timelines, and property types.

---

## 4. Universal Ingestion Pipeline & Tenancy

### 4.1 Strict Multi-Tenant Isolation
- Under no circumstances is `organization_id` accepted from the webhook request body or query parameters.
- Webhook routes identify the tenant solely through authenticated credentials:
  - Meta: Webhook verify token / app secret mapped in database `lead_sources`.
  - Google: `google_key` mapped to tenant `lead_sources`.
  - Header / Route ID: Specific source UUID `source_id` bound to tenant context.

### 4.2 Idempotency & Deduplication
- Every ingestion creates an immutable `LeadAcquisitionEvent` with an `idempotency_key` constructed from `f"{provider}:{organization_id}:{external_lead_id}"`.
- Subsequent deliveries of the identical provider lead ID update the event status to `DUPLICATE` without creating redundant customer or lead records.
- Cross-provider leads (e.g. same customer submitting via Meta then Google) resolve to the single unified customer identity via `IdentityService` (phone/email match) while maintaining distinct acquisition event attribution trails.

### 4.3 Workload-Aware Auto-Routing & SLA Activation
- Ingested leads invoke `LeadRoutingService.route_lead`:
  - Evaluates territory, property type, budget, and active agent workload.
  - Generates an immutable `routing_reason` audit trail.
- Automatically initializes first-contact SLA timers (e.g., 15-minute response window) and registers SLA tasks for the assigned sales representative.

### 4.4 Non-Blocking Downstream Resilience (Lead Loss Prevention)
- Failures in downstream services (e.g., AI Gateway timeout, Redis cache miss, external email provider error) are caught and logged as non-fatal.
- The canonical `Lead` record remains safely committed to the database. Downstream operations are queued for background retry.

---

## 5. Bounded Reconciliation & Backfill Engine

Both Meta and Google connectors implement bounded sync operations to identify and recover missing leads without risking provider rate limits or system saturation:

- **Reconciliation (`reconcile`)**:
  - Scans a bounded time window (e.g., last 24 hours, last 7 days).
  - Fetches external lead summaries from provider APIs.
  - Compares external IDs against persisted `LeadAcquisitionEvent` records.
  - Identifies gaps (`missing_lead_ids`) and automatically triggers safe replay for missing leads.
  - Exposes `dry_run: true` mode to allow operators to review discrepancies before execution.
- **Backfill (`backfill`)**:
  - Imports leads from a specified historical window (`start_time` to `end_time`).
  - Implements bounded batch limits (maximum 500 leads per execution).
  - Maintains idempotency: existing leads are touched or skipped without creating duplicates.

---

## 6. Provider Capability & Compliance Matrix

| Capability | Meta Lead Ads | Google Ads Lead Forms |
| :--- | :--- | :--- |
| **Transport** | Real-time Webhook + Graph API v19.0 | Webhook (`user_column_data`) & API |
| **Authentication** | HMAC-SHA256 (`X-Hub-Signature-256`) | Secret Key (`google_key`) |
| **Verification Handshake** | Hub challenge (`hub.mode`, `hub.challenge`) | Webhook validation key |
| **Campaign Attribution** | Campaign ID, Ad Set ID, Ad ID, Form ID | Campaign ID, Ad Group ID, GCLID, Form ID |
| **Real Estate Field Normalization** | Budget, BHK, Location, Timeline, Purpose | Budget, BHK, City, Postal Code, Timeline |
| **Deduplication Key** | `meta:{org_id}:{leadgen_id}` | `google:{org_id}:{lead_id}` |
| **Bounded Reconciliation** | Supported (lookback window, dry-run) | Supported (lookback window, dry-run) |
| **Bounded Backfill** | Supported (capped batch limit) | Supported (capped batch limit) |
| **Health Check** | API Token & Page verification | Key verification & Account status |
| **WhatsApp Acquisition** | **DISABLED** (Explicitly prohibited) | N/A |
| **Live Connection Status** | `CONFIGURED` / `NOT_CONFIGURED` | `CONFIGURED` / `NOT_CONFIGURED` |

---

## 7. Security & Privacy Specifications

1. **Zero Credential Exposure**: Provider access tokens, client secrets, and webhook keys are encrypted at rest using server-side configuration encryption and never returned in API responses.
2. **PII Masking**: Raw webhook payloads containing PII are stored exclusively in tenant-scoped `LeadAcquisitionEvent.raw_payload` with strict RBAC access. System logs mask phone numbers and email addresses.
3. **Fail-Closed Verification**: Any webhook request failing cryptographic signature or key verification is rejected immediately with `401 Unauthorized`.
4. **Anti-CSRF OAuth Flow**: OAuth connection flows use cryptographically random `state` tokens bound to user session and tenant context.
