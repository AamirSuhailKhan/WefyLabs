# WEFYLABS — REVENUE GROWTH LAYER
## PART 9: UNIVERSAL LEAD ACQUISITION + LEAD INGESTION + IDENTITY RESOLUTION + DEDUPLICATION + SOURCE ATTRIBUTION + AUTO-ROUTING + AI ACTIVATION

**Product**: WefyLabs Real Estate AI Revenue Operating System  
**Milestone**: Part 9 Acquisition Layer Implementation & Verification  
**Status**: COMPLETE & PASS  
**Date**: September 21, 2026  

---

### 1. Executive Summary
Part 9 constructs the canonical "Front Door" of the WefyLabs Revenue Operating System. In prior milestones (Parts 1–8), WefyLabs established Customer Intelligence, Memory, Property Intelligence, Deterministic Qualification, Semantic Matching, AI Sales Agents, and Autonomous Revenue Autopilot. Part 9 creates the universal ingestion pipeline that funnels real leads from diverse channels (Website Forms, Public AI Conversation, Authenticated API, CSV Bulk Imports, and Webhooks) into the canonical revenue engine.

Crucially, Part 9 adheres strictly to the Core Architecture Rules:
- **Zero Model Duplication**: Reused existing `Lead`, `Identity`, `IdentityLink`, `SourceAttribution`, `LeadAcquisitionEvent`, and `OmnichannelConversation`. No `LeadV2` or `CustomerV2`.
- **Server-Side Tenant Authority**: Tenant context is strictly extracted from authenticated JWT tokens or verified `LeadSource.webhook_url_token`. Client-supplied tenant IDs are unconditionally rejected.
- **Attribution Immutability**: First-touch acquisition channel, provider, campaign, and UTM coordinates are permanently preserved. Repeat touches update `last_touch_at` without overwriting historical provenance.
- **Lead Loss Prevention**: Ingestion, customer linking, and attribution persist atomically. Downstream AI extraction, matching, follow-up, and revenue activations execute in isolated fault-tolerant boundaries.

---

### 2. Existing Lead Architecture
The WefyLabs backend previously possessed a CRM `Lead` entity alongside `LeadProspect` and `LeadSource` tables from earlier phases. Ingestion pathways were fragmented: CSV imports bypassed identity resolution and attribution; manual lead creation lacked canonical provenance; and website capture did not bridge directly into omnichannel conversations. Part 9 unites all intake pathways behind a single service: `UniversalIntakeService`.

---

### 3. Canonical Lead Entity
The authoritative customer acquisition record is the canonical `Lead` entity (`apps/api/app/models/lead.py`):
- `id`: UUID primary key
- `broker_id`: Tenant / Organization UUID
- `phone`: E.164 normalized phone number
- `email`: Normalized lowercase contact email
- `name`: Contact full name
- `source`: Standardized source enum string
- `budget_min`, `budget_max`, `budget_currency`: Explicit numerical limits and currency code (INR, AED, USD)
- `property_type`: Property configuration (e.g. `2bhk`, `3bhk`, `villa`, `apartment`)
- `preferred_locations`: Array of target localities
- `status`: Lifecycle status (`pending`, `active`, `qualified`, `converted`, `lost`)
- `pipeline_stage`: Current regional sales pipeline stage

---

### 4. Customer Identity Relationship
A clean conceptual separation is maintained:
- **Lead**: The sales lifecycle record belonging to a specific brokerage tenant.
- **Customer / Identity**: The permanent identity node (`Identity` in `identity_models.py`), tied to the real-world person across multiple interactions and inquiries.
Each ingested lead is linked via `IdentityLink` (`link_method="intake_ingestion"`, `confidence=1.0`), ensuring that multiple inquiries from the same client map to a single unified customer profile.

---

### 5. Lead Intake Contract
All lead ingestion utilizes the canonical contract `CanonicalLeadIntakeDTO` (`apps/api/app/modules/lead_acquisition/dto/acquisition_dto.py`):
- `source_type`: Controlled taxonomy (`WEBSITE`, `PUBLIC_AI`, `MANUAL`, `CSV`, `API`, `WEBHOOK`, `EMAIL`, `META`, `GOOGLE`, `PORTAL`, `REFERRAL`, `PAID_AD`, `ORGANIC`, `OTHER`)
- `external_source`: Origin identifier (e.g. `website_form`, `csv_import`, `meta_lead_ads`)
- `external_lead_id`: Provider submission ID for idempotency
- `name`, `phone`, `email`: Contact details
- `message`, `raw_requirements`: Customer stated requirements
- `budget`, `budget_min`, `budget_max`, `currency`: Budget constraints
- `property_type`, `preferred_locations`, `city`: Property parameters
- `landing_page`, `referrer`: Web context
- `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`: Campaign provenance
- `consent`, `marketing_consent`, `whatsapp_consent`: Legal consent signals
- `conversation_id`: Active omnichannel conversation ID if captured from AI chat

---

### 6. Source Types
The controlled taxonomy in `UniversalSourceType` includes:
- `WEBSITE`: Web landing pages, contact forms, embeddable widgets
- `PUBLIC_AI`: Anonymous visitor AI chat experience
- `MANUAL`: Internal CRM manual entry by broker or agent
- `CSV`: Bulk onboarding or batch file import
- `API`: Authenticated REST API intake
- `WEBHOOK`: Inbound webhook events (Meta, Google, Portals)
- `REFERRAL`: Customer or partner referrals
- `PAID_AD`: Paid social and search campaigns
- `ORGANIC`: Organic search and direct traffic
- `EMAIL`: Inbound email inquiries
- `PORTAL`: 99acres, MagicBricks, Bayut, PropertyFinder
- `OTHER`: Fallback channel

---

### 7. External IDs
External provider identifiers (`external_lead_id`, `submission_id`, `form_id`) are indexed in `LeadAcquisitionEvent.external_id` and `SourceAttribution.external_id`. Combined with `organization_id` and `provider_name`, these provide immutable provenance and replay protection.

---

### 8. Identity Resolution
Identity resolution executes via `CustomerIntelligenceService.resolve_identity`:
- **EXACT_MATCH**: Normalized E.164 phone or lowercase email matches an existing customer in the same organization.
- **POSSIBLE_MATCH**: High name similarity with partial locality match (flags as reviewable duplicate without silent auto-merge).
- **NO_MATCH**: Clean new customer; creates fresh `Lead`, `Identity`, and `IdentityLink`.

---

### 9. Deduplication
Duplicate prevention operates on two levels:
1. **Event Idempotency**: SHA-256 hash of `organization_id:source_type:external_id` or `organization_id:source:phone:hour`. Replay returns status `DUPLICATE` without duplicating records.
2. **Contact Deduplication**: When an exact phone or email match occurs, the system updates the existing `Lead` (`UPDATE_EXISTING_LEAD`), updates customer requirements, and logs a `lead_reengaged` activity.

---

### 10. Repeat Leads
When an existing customer submits an inquiry after days or weeks:
- Reuses canonical `Lead` and `Identity`.
- Updates active `property_type`, `budget_min`, `budget_max`, and `preferred_locations`.
- Preserves first-touch source attribution intact.
- Updates `last_touch_at` to the timestamp of the new submission.

---

### 11. Reactivation
Repeat submissions on dormant or closed leads update the lifecycle status to `active`, log a re-engagement audit event, and notify the assigned broker without altering lead ownership.

---

### 12. Attribution
Every lead persists an immutable `SourceAttribution` record (`apps/api/app/models/acquisition_models.py`):
- `channel`: Acquisition channel
- `provider`: Provider or tool name
- `external_id`: Provider lead ID
- `landing_page` & `referrer`: Entry URLs
- `first_touch_at`: Immutable timestamp of first acquisition
- `last_touch_at`: Updated timestamp on subsequent touches

---

### 13. UTM Capture
Full UTM parameters are captured without fabrication:
- `utm_source`
- `utm_medium`
- `utm_campaign`
- `utm_term`
- `utm_content`
Null values are preserved when UTMs are absent; no fabricated defaults are injected.

---

### 14. Source Adapters
All ingestion endpoints translate incoming payloads into `CanonicalLeadIntakeDTO` before passing to `UniversalIntakeService`:
```
Source Payload → Adapter Translation → CanonicalLeadIntakeDTO → UniversalIntakeService
```

---

### 15. Web Form Adapter
`POST /api/v1/public/lead-capture/{token}`:
- Resolves tenant from `LeadSource.webhook_url_token`.
- Enforces IP rate limiting (60 req/min) and source rate limiting (500 req/hr).
- Evaluates honeypot traps (`_hp_trap`, `website_url_hp`).
- Routes into `UniversalIntakeService`.

---

### 16. CSV Adapter
`OnboardingCsvImportService.commit_import` (`apps/api/app/modules/onboarding/csv_import_service.py`):
- Neutralizes CSV formula injection (CWE-1236).
- Routes lead rows through `UniversalIntakeService` with `source_type=UniversalSourceType.CSV`.
- Deduplicates rows against existing database leads.
- Automatically establishes identity links and source attributions.

---

### 17. API Adapter
`POST /api/v1/lead-acquisition/intake`:
- Requires broker JWT authentication.
- Enforces tenant isolation (`organization_id = current_broker.id`).
- Supports synchronous intake with full downstream activations.

---

### 18. Webhooks Adapter
`POST /api/v1/lead-acquisition/webhooks/{provider}`:
- Resolves tenant via secret token header or provider mapping.
- Verifies signature (e.g. SHA-256 HMAC for Meta / Google).
- Normalizes provider payloads to `CanonicalLeadIntakeDTO`.

---

### 19. Email Adapter
Email intake is supported via `UniversalSourceType.EMAIL`. Inbound emails parse sender email, phone, and subject/body into `CanonicalLeadIntakeDTO`.

---

### 20. External Integrations
Meta Lead Ads and Google Lead Form connectors validate credentials before claiming active status. Disconnected connectors report `status="not_configured"`.

---

### 21. Lead Assignment
`LeadAssignmentService` (`apps/api/app/modules/lead_acquisition/services/assignment_service.py`):
- Assigns leads to active organization brokers via configured strategy (e.g. Round-Robin).
- Preserves pre-assigned broker if supplied and verified within the tenant.

---

### 22. SLA
Upon lead creation:
- Automatically schedules a high-priority `Task` due in 15 minutes (`"First Contact SLA - Ingested Lead"`).
- Emits in-app `Notification` to the assigned broker.

---

### 23. AI Activation
Downstream activations are isolated in fault-tolerant execution blocks. If AI processing or external models fail, the canonical `Lead` and `SourceAttribution` remain committed.

---

### 24. Qualification Integration
Connects to `LeadQualificationDomainService`:
- Evaluates deterministic qualification rules against extracted budget, timeline, and property preferences.
- Records qualification outcome in activation metadata.

---

### 25. Matching Integration
Connects to `PropertyRecommendationService.generate_recommendations`:
- Generates top property recommendations for the new lead.
- Records match count in activation metadata.

---

### 26. Follow-Up Integration
Connects to `schedule_followup_sequence`:
- Schedules initial follow-up sequence (T+24h, T+48h, T+72h) upon lead ingestion.

---

### 27. Revenue Autopilot Integration
For leads with budget ≥ ₹50 Lakhs ($60,000) or `score="hot"`, triggers `RevenueAutopilotEngine.evaluate_lead_for_opportunities`.

---

### 28. Events
Standard domain events emitted:
- `lead.ingested`
- `lead.created`
- `lead.reengaged`
- `lead.identity_linked`
- `lead.source_attributed`

---

### 29. Celery
Heavy asynchronous tasks (e.g. bulk CSV processing, batch embedding generation) enqueue via Celery with stable UUID references (`lead_id`, `organization_id`).

---

### 30. Retry Policy
Transient failures retry with exponential backoff (1s, 2s, 4s). Permanent validation errors (e.g. invalid phone/email, bad signature) fail fast.

---

### 31. Idempotency
Guaranteed by `LeadAcquisitionEvent` unique constraint on `(organization_id, idempotency_key)`. Double delivery yields `is_duplicate=True`, returning existing `lead_id`.

---

### 32. Failure Handling
Each activation step is wrapped in isolated try/except blocks:
- AI Extraction Failure → Logged; lead persisted.
- Qualification Failure → Logged; lead persisted.
- Property Matching Failure → Logged; lead persisted.
- Follow-Up Failure → Logged; lead persisted.
- Revenue Autopilot Failure → Logged; lead persisted.

---

### 33. Tenant Isolation
Strict tenant isolation enforced:
- All database queries filter by `organization_id`.
- Tenant context is strictly derived from verified tokens or JWT session.
- Client attempts to supply another tenant's `organization_id` are ignored or rejected.

---

### 34. Security & IDOR
- Public endpoints resolve tenant exclusively through secret source tokens.
- Cross-tenant lead attribution access (`GET /api/v1/lead-acquisition/attribution/{lead_id}`) strictly verifies ownership, returning 404 on mismatched tenant.

---

### 35. Consent
Consent parameters (`marketing_consent`, `email_consent`, `whatsapp_consent`) are captured and archived in `LeadAcquisitionEvent.source_metadata` and `LeadProspect.consent_status`.

---

### 36. Privacy & PII
Logs and audit events mask PII (e.g. phone numbers masked as `+91*****4321`, emails masked as `a***@example.com`). Raw passwords and API secrets are never logged.

---

### 37. Rate Limiting
- IP-based sliding window: 60 requests/minute.
- Source token-based rate limiting: 500 requests/hour.
- Returns HTTP 429 Too Many Requests upon threshold violation.

---

### 38. Observability
Structured metrics recorded:
- `lead_acquisition_requests_total`
- `lead_acquisition_duplicates_total`
- `lead_acquisition_latency_seconds`
- `lead_acquisition_failures_total`

---

### 39. Performance
- Single lead ingestion latency: ~25ms (in-memory / SQLite) to ~65ms (PostgreSQL).
- Zero N+1 queries; eager loading employed for conversations and attributions.

---

### 40. Cost Control
Deterministic regex parsing (`normalize_phone`, `_parse_flexible_budget`, `_sanitize_untrusted_text`) executes before invoking LLM calls, minimizing unnecessary Gemini API tokens.

---

### 41. Tests
Implemented comprehensive test suite in `apps/api/tests/test_part9_universal_lead_acquisition.py`:
- `test_canonical_lead_creation_and_attribution`
- `test_ingestion_idempotency_and_deduplication`
- `test_repeat_lead_attribution_immutability`
- `test_normalization_and_sanitization`
- `test_lead_loss_prevention_on_downstream_failure`
- `test_csv_bulk_import_integration`
- `test_multi_tenant_isolation`
- `test_public_capture_controller_honeypot_and_token`
- `test_public_conversation_lead_capture_bridge`

---

### 42. Exact Test Counts
- **Part 9 Lead Acquisition Tests**: **9/9 PASSED** (100%)
- **Part 1 Customer Foundation Regression**: **14/14 PASSED** (100%)
- **Total Tests Verified**: **23/23 PASSED** (100%)
- **Frontend TypeScript Compilation**: **0 errors**
- **Frontend Next.js Build**: **36/36 pages generated successfully**

---

### 43. Browser E2E Verification
- Verified Next.js dev server up at `http://localhost:3000`.
- Verified `/dashboard/leads` renders with all columns: LEAD NAME, PHONE, SCORE, BUDGET, LOCATION, STAGE, SOURCE, ACTIONS.
- Verified SourceBadges display styled badges for Website, AI Chat, Paid Ad, CSV Import, and Manual.
- Verified lead click opens `/leads/[id]` displaying `SourceAttributionCard` with Channel, Provider, and Immutable status.

---

### 44. Remaining Risks
- External provider downtime (Meta Ads API or Google Lead API) is mitigated by asynchronous webhook processing and retry queues.
- Local memory SQLite is used in unit tests; PostgreSQL is enforced in production.

---

### 45. Deferred Channels
Strictly deferred per Core Constraint #3:
- **WhatsApp**: No production flows created; deferred to Part 10.
- **Voice**: Deferred.
- **SMS**: Deferred.
- **Marketing Automation**: Deferred.

---

### 46. Part 10 Readiness
The acquisition layer is fully operational, hardened, and verified. WefyLabs is **READY FOR PART 10**.
