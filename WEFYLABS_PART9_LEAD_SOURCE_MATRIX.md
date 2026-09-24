# WEFYLABS — PART 9 LEAD SOURCE MATRIX
## Canonical Source Taxonomy & Ingestion Adapter Capabilities

This matrix documents the verification status, security architecture, attribution tracking, and downstream AI activations across all supported lead ingestion channels in WefyLabs Part 9.

| SOURCE | ADAPTER | AUTH | TENANT | IDEMPOTENCY | ATTRIBUTION | NORMALIZATION | AI ACTIVATION | STATUS | RUNTIME VERIFIED |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Website Form** | `PublicLeadCaptureController` (`POST /api/v1/public/lead-capture/{token}`) | Token-based / Public | Verified via `LeadSource.webhook_url_token` | SHA-256 event hash | First & Last Touch, UTMs, Landing URL, Referrer | E.164 Phone, Email lowercase, Budget units | Async AI Extraction, Qualification, Matching, Follow-up | ACTIVE | VERIFIED (Tests + Browser) |
| **Public AI Chat** | `PublicLeadCaptureController` (`POST /api/v1/public/lead-capture/conversation/{token}`) | Token-based / Public | Verified via `LeadSource.webhook_url_token` | SHA-256 event hash | Channel `PUBLIC_AI`, Provider `ai_agent` | E.164 Phone, Email lowercase, Budget units | Conversation linked, Extraction, Matching | ACTIVE | VERIFIED (Tests + Browser) |
| **Internal CRM Manual** | `LegacyLeadService.create_lead` & `LeadController` | JWT Bearer Token | Authenticated `current_broker.id` | Phone duplicate check | Channel `MANUAL`, Provider `crm_manual` | E.164 Indian phone validation | SLA task creation, Activity log | ACTIVE | VERIFIED (Tests) |
| **CSV Bulk Import** | `OnboardingCsvImportService.commit_import` | JWT Bearer Token | Authenticated `broker.id` | Row-level deduplication + SHA-256 | Channel `CSV`, Provider `csv_import` | Formula injection sanitize, E.164, Budget | Batch identity linkage, Attribution | ACTIVE | VERIFIED (Tests) |
| **REST API Intake** | `AcquisitionController` (`POST /api/v1/lead-acquisition/intake`) | JWT / API Key | Authenticated `current_broker.id` | SHA-256 idempotency key | Full UTMs, provider name, external ID | Complete normalization pipeline | Full downstream activations | ACTIVE | VERIFIED (Tests) |
| **Webhooks (Meta Ads)** | `AcquisitionController` (`POST /api/v1/lead-acquisition/webhooks/{provider}`) | Signature HMAC / Secret Header | Token / Org resolution | Provider `lead_id` + Event hash | Channel `META`, Campaign ID, Form ID | E.164 Phone, Email lowercase | Full downstream activations | CONFIGURED | VERIFIED (Tests) |
| **Webhooks (Google Ads)** | `AcquisitionController` (`POST /api/v1/lead-acquisition/webhooks/{provider}`) | Key / Signature | Token / Org resolution | Google Lead ID + Event hash | Channel `GOOGLE`, Campaign, GCLID | E.164 Phone, Email lowercase | Full downstream activations | CONFIGURED | VERIFIED (Tests) |
| **Inbound Email** | `UniversalIntakeService` (`source_type=EMAIL`) | Authenticated bridge | Broker / Org mapping | Message-ID / Subject hash | Channel `EMAIL`, Sender address | E.164 Phone extraction, Email | NLP extraction, Follow-up | ACTIVE | VERIFIED (Unit) |
| **Property Portals** | `UniversalIntakeService` (`source_type=PORTAL`) | Webhook / API Token | Partner Org token | Portal submission ID | Channel `PORTAL`, Listing ID | Complete normalization pipeline | Matching, SLA Notification | READY | VERIFIED (Architecture) |
| **WhatsApp Ingestion** | N/A | DEFERRED | DEFERRED | DEFERRED | DEFERRED | DEFERRED | DEFERRED | DEFERRED | STRICTLY DEFERRED (Part 10) |
| **Voice Call Intake** | N/A | DEFERRED | DEFERRED | DEFERRED | DEFERRED | DEFERRED | DEFERRED | DEFERRED | STRICTLY DEFERRED |
| **SMS Ingestion** | N/A | DEFERRED | DEFERRED | DEFERRED | DEFERRED | DEFERRED | DEFERRED | DEFERRED | STRICTLY DEFERRED |

---

### Security & Ingestion Policy Highlights
- **Tenant Context Authority**: Client payloads are never permitted to declare `organization_id`. Tenant context is strictly resolved server-side from authenticated credentials or verified source tokens.
- **Anti-Spam Decoy**: Public form submissions that trigger honeypot traps (`website_url_hp`, `_hp_trap`) return `200 OK` decoy responses without persisting spam leads or triggering expensive AI models.
- **Fault-Tolerant Downstream Isolation**: Downstream AI, Property Matching, Follow-up, and Revenue Autopilot processes execute in isolated error-handling contexts. Core lead persistence and attribution remain intact even during third-party service degradation.
