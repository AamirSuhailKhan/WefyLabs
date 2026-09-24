# WEFYLABS PRODUCTION DEPENDENCY MATRIX
# External Integrations, Configuration & Operational Readiness

---

| Dependency Name | Purpose | Environment Variables | Required / Optional | Failure Impact | Timeout | Retry Policy | Fallback Behavior | Local / Test Status | Production Status |
|---|---|---|---|---|---|---|---|---|---|
| **PostgreSQL + pgvector** | Primary operational & vector store | `DATABASE_URL` | **REQUIRED** | System-wide read/write failure | 20s (asyncpg) | Pool pre-ping, session rollback | None (Fails closed) | **VERIFIED LOCALLY** | **CONFIG_READY** |
| **Upstash Redis** | Cache, distributed locks, rate limiting | `REDIS_URL` | **REQUIRED** | Delayed background tasks | 500ms (connect) | Fast-fail with in-memory fallback | In-memory sliding window & locks | **VERIFIED LOCALLY** | **CONFIG_READY** |
| **Google Gemini API** | LLM inference, embedding, AI agents | `GEMINI_API_KEY`, `GEMINI_MODEL` | **REQUIRED** | AI chat & recommendations fail | 15s | 3 attempts with circuit breaker | Deterministic heuristic fallback | **VERIFIED LOCALLY** | **CONFIG_READY** |
| **Brevo / SMTP** | Outbound email delivery | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` | OPTIONAL | Delayed customer emails | 10s | Celery retry with backoff | Logs failure in Outbox / Communication | **VERIFIED LOCALLY** | **CONFIG_READY** |
| **WhatsApp Direct** | Omnichannel WhatsApp messaging | `WHATSAPP_ACCESS_TOKEN`, `PHONE_NUMBER_ID`, `WABA_ID` | OPTIONAL | WhatsApp messages blocked | 5s | Non-retryable if disabled | Falls back to Email/SMS | **VERIFIED (DISABLED)** | **KILL-SWITCH ACTIVE** |
| **Meta Lead Ads Webhooks** | Inbound social lead acquisition | `WHATSAPP_VERIFY_TOKEN`, `META_APP_SECRET` | OPTIONAL | Social ads leads delayed | 5s | Meta provider automatic retry | Idempotent Outbox ingestion | **VERIFIED LOCALLY** | **CONFIG_READY** |
| **Google Lead Forms** | Inbound search lead acquisition | `GOOGLE_LEAD_FORM_KEY` | OPTIONAL | Google ads leads delayed | 5s | Google provider automatic retry | Idempotent Outbox ingestion | **VERIFIED LOCALLY** | **CONFIG_READY** |
| **Google Calendar OAuth** | Viewing & appointment scheduling | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` | OPTIONAL | Google calendar sync fails | 10s | Bounded retry | Native WefyLabs CRM internal calendar | **VERIFIED LOCALLY** | **CONFIG_READY** |
| **Razorpay Payments** | Subscription billing & invoices | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | OPTIONAL | Subscription activation blocked | 8s | Webhook idempotent retry | Safe pause (`PAYMENTS_EMERGENCY_PAUSE`) | **VERIFIED LOCALLY** | **KILL-SWITCH ACTIVE** |
| **Supabase Auth** | JWT signature verification | `SUPABASE_JWT_SECRET`, `SUPABASE_URL` | **REQUIRED** | User authentication fails | In-process | None (stateless JWT decoding) | 401 Unauthorized | **VERIFIED LOCALLY** | **CONFIG_READY** |

---

## Operational Definitions
- **VERIFIED LOCALLY**: Automated test suites executed and passed against real or simulated interfaces in local repository.
- **CONFIG_READY**: Code and configuration schemas verified; awaiting live production credentials and domain DNS mapping.
- **KILL-SWITCH ACTIVE**: Hard-disabled in codebase and configuration to prevent accidental or unapproved external dispatch.
- **PUBLICLY VERIFIED**: Requires live production domain verification (Owner Action Item).

---
_Status: AUDITED & CERTIFIED._
