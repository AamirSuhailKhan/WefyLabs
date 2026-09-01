# PART 21.6 — REAL COMMUNICATION PROVIDER INTEGRATION & PRODUCTION DELIVERY ENGINE
## Technical Implementation Plan

**BeetleLabs Enterprise Real Estate CRM**
**Auditor/Engineer:** Principal Engineer (AI)
**Target Baseline:** 39/39 Part 21.5, 273/273 Full Core Regression, merge_002_and_9999_heads (Alembic)

---

## 1. Executive Summary & Objective

Part 21.6 turns the communication execution layer from Part 21.5 into a genuine production-ready provider integration system.

### Core Principle:
`
POLICY DECIDES.
AI PHRASES.
PROVIDER DELIVERS.
PROVIDER CONFIRMS.
DATABASE RECORDS THE TRUTH.
`

The system will NEVER claim that a message was sent, delivered, or scheduled unless the real provider confirms that state.
If credentials are missing, it strictly returns CONFIGURATION_REQUIRED or PROVIDER_UNAVAILABLE.
Zero mock fallback in production paths.

---

## 2. Current Implementation Audit (From Step 0)

| Component | Current State | Part 21.6 Action Required |
|---|---|---|
| base_provider.py | Basic abstract base class with simple ProviderResponse | Enhance with strict typed statuses (QUEUED, ACCEPTED, SENT, DELIVERED, READ, FAILED, RATE_LIMITED, AUTH_FAILED, CONFIGURATION_REQUIRED, PROVIDER_UNAVAILABLE, INVALID_RECIPIENT), verify_configuration(), capabilities(), normalize_error() |
| whatsapp_provider.py | Meta Cloud API skeleton returning mock IDs | Implement real httpx Meta Graph API calls, token validation, real template/text formatting, HMAC SHA256 webhook signature verification with hmac.compare_digest, delivery status webhook ingestion, Graph API error code mapping |
| email_smtp_provider.py | SMTP adapter with commented out aiosmtplib | Implement real SMTP client dispatch with TLS/SSL, credential validation, failure classification, Message-ID generation, no fake delivery |
| sms_provider.py | Abstract SMSProvider + MockSMSProvider | Implement real SMSGatewayProvider with real HTTP dispatch where credentials exist; return CONFIGURATION_REQUIRED when not configured; remove mock in prod |
| webchat_provider.py | In-app / webchat session adapter | Validate real session/presence; return CONFIGURATION_REQUIRED or INVALID_RECIPIENT if session absent |
| action_executor.py (21.5) | Stored FollowUpExecution with placeholder provider IDs | Connect directly to Real Delivery Engine & ChannelManager with execution locks, idempotency keys, and real provider status handling |
| Execution-Time Safety Re-Checks | Not present at execution moment | Implement execution-time re-checks for Consent, Fatigue, Quiet Hours, and Human Approval |
| Idempotency & Concurrency Lock | Partial idempotency key | Implement deterministic sha256(tenant_id:lead_id:sales_action_id:channel:message_hash:version) + execution locking |
| Webhook Verification & Processing | Basic endpoint in communication router | Add signature verification, replay protection, duplicate webhook deduplication, tenant-safe status progression |
| Provider Configuration Service | Not unified | Create ProviderConfigurationService exposing safe status (READY, CONFIGURATION_REQUIRED, AUTHENTICATION_FAILED, DISABLED) without secrets |
| Celery Background Tasks | Basic stubs | Add idempotent, tenant-scoped deliver_communication task with retry management and exponential backoff |
| Metrics & Audit | Basic metrics | Add 8+ PII-safe Prometheus metrics and structured audit logging |
| Frontend | SalesActionCard.tsx basic UI | Add rich delivery states (Sent, Delivered, Read, Failed, Retrying, Configuration Required) and provider status |

---

## 3. Architecture & Data Flow

`
                 REAL LEAD
                     ↓
              PART 21.5 POLICY (SalesActionDomainService)
                     ↓
              APPROVED ACTION
                     ↓
         PART 21.6 DELIVERY ENGINE (RealDeliveryEngine)
                     ↓
          EXECUTION-TIME SAFETY RE-CHECKS
    [Consent Re-Check | Fatigue Re-Check | Quiet-Hours Re-Check | Approval Re-Check]
                     ↓
           IDEMPOTENCY & EXECUTION LEASE LOCK
                     ↓
          PROVIDER ADAPTER LAYER
       ┌─────────────┼─────────────┐
       ↓             ↓             ↓
   WhatsApp        Email          SMS
 (Graph API)      (SMTP)       (Gateway)
       ↓             ↓             ↓
       └─────────────┼─────────────┘
                     ↓
              Provider Result (Real / Truthful)
                     ↓
              Delivery State Machine
       (QUEUED -> ACCEPTED -> SENT -> DELIVERED -> READ / FAILED)
                     ↓
        Conversation / FollowUpExecution Audit
                     ↓
             Next Best Action
`

---

## 4. Detailed Component Design

### 4.1. Typed Provider Interface
Standardized DeliveryStatusEnum, ProviderStatusEnum, ProviderResponse, CommunicationCapabilities.

### 4.2. Real WhatsApp Cloud API Provider
Real Meta Graph API POST via httpx.AsyncClient. Error normalization (190 -> AUTH_FAILED, 131026 -> INVALID_RECIPIENT, 130429 -> RATE_LIMITED, etc.).

### 4.3. Real Email SMTP Provider
Real SMTP with TLS/SSL, credential validation, real Message-ID, SMTP error classification.

### 4.4. Real SMS Gateway Provider
Real SMS endpoint integration. When unconfigured, returns CONFIGURATION_REQUIRED.

### 4.5. Execution-Time Safety Re-Checks
1. Consent Re-check (reject with CONSENT_REVOKED_AT_EXECUTION if opted out).
2. Fatigue Re-check (reject with FATIGUE_EXCEEDED_AT_EXECUTION if budget exceeded).
3. Quiet-Hours Re-check (reschedule if inside quiet hours, return QUIET_HOURS_RESCHEDULED).
4. Human Approval Re-check (reject with APPROVAL_REQUIRED_AT_EXECUTION if unapproved).

### 4.6. Idempotency & Concurrency Control
Deterministic key sha256(org:lead:action:channel:msg_hash:version) + execution locking.

### 4.7. Retry Engine with Bounded Exponential Backoff
RETRYABLE vs NON_RETRYABLE classification with jitter.

### 4.8. Webhook Ingestion & State Machine
HMAC SHA-256 signature verification, replay protection, deduplication, state advancement.

### 4.9. Provider Configuration Service
Non-sensitive operational status without credential leakage.

### 4.10. Observability & Audit Trail
PII-safe Prometheus metrics with hashed tenant IDs.

---

## 5. Verification Plan

1. Dedicated Test Suite: 	ests/test_part21_6_communication_providers.py (40+ test scenarios across Sections A through M).
2. Full Regression Suite (21.1 to 21.6).
3. Frontend Next.js build (
pm run build).
4. Alembic head verification (merge_002_and_9999_heads).
5. FastAPI startup check.
