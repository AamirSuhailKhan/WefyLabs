# BEETLELABS — PART 22
# PRODUCTION DEPLOYMENT & LIVE-TRAFFIC READINESS CHECKLIST

**Target Environment:** Staging / Production  
**Architecture:** Next.js 15 Web Frontend + FastAPI Async Backend + PostgreSQL/pgvector + Redis/Celery + Google Gemini AI  
**Safety Contract:** Fail-Closed Safety Guards, Strict Tenant Isolation, Emergency Kill-Switch Enabled  

---

## 1. DATABASE & PERSISTENCE
- [ ] **Production DATABASE_URL Configured:** Set `DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<dbname>` in environment.
- [ ] **Alembic Single Head Verified:** Confirm `alembic heads` outputs exactly one head (`0015_sales_loop_orchestration`).
- [ ] **Migrations Executed:** Run `python -m alembic upgrade head` on live PostgreSQL/Supabase database.
- [ ] **pgvector Extension Active:** Verify `CREATE EXTENSION IF NOT EXISTS vector;` is executed on the database.
- [ ] **Indexes Verified:** Ensure composite indexes on `(tenant_id, lead_id, event_type)` and `(idempotency_key)` are present.
- [ ] **Automated Backup Policy:** Configure daily WAL archiving and point-in-time recovery (PITR).

---

## 2. REDIS & TASK QUEUE WORKERS
- [ ] **Managed Redis Cluster Configured:** Set `REDIS_URL=rediss://<user>:<password>@<host>:6379/0` (TLS enabled).
- [ ] **Celery Worker Processes Active:** Launch workers with `celery -A app.celery_app.celery_app worker -l info -Q sales-loop-orchestration,sales-loop-retry,lead_queue,email_queue,whatsapp_queue`.
- [ ] **Celery Beat Scheduler Active:** Launch scheduler for crontabs (decay, SLAs, daily briefs).
- [ ] **Dead-Letter Queue Monitored:** Verify `dead_letter_queue` is actively monitored with Prometheus alerts.
- [ ] **Task Serialization Verified:** Ensure JSON-only task payload serialization is enforced.

---

## 3. AI REASONING ENGINE (GOOGLE GEMINI)
- [ ] **Production API Key Configured:** Set `GEMINI_API_KEY` with live Google AI Studio / Vertex AI credentials.
- [ ] **Model Identifier Confirmed:** Set `GEMINI_MODEL=gemini-3.5-flash` (or `gemini-3.7-flash`).
- [ ] **Rate Limits & Quota Upgraded:** Ensure production project has tier-1 or pay-as-you-go quota.
- [ ] **Failure Fallback Verified:** Verify `LLMResponse` correctly reports errors without fabricating business decisions.

---

## 4. GOOGLE OAUTH & CALENDAR
- [ ] **Google Cloud Console Project Configured:** OAuth 2.0 Client ID created with type *Web application*.
- [ ] **Authorized Redirect URIs Set:** Add `https://<api_domain>/api/v1/calendar/auth/callback` and `https://<app_domain>/auth/callback`.
- [ ] **Environment Variables Populated:** Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
- [ ] **Token Encryption Secret:** Confirm `SECRET_KEY` is minimum 32 random characters for token AES encryption.
- [ ] **Live Interactive Authorization Smoke Test:** Complete one interactive broker OAuth flow and verify FreeBusy query.

---

## 5. WHATSAPP / META CLOUD API
- [ ] **Meta Developer App Configured:** WhatsApp Cloud API product added to Meta Business Manager account.
- [ ] **Permanent System User Access Token Generated:** Set `WHATSAPP_ACCESS_TOKEN` in `.env`.
- [ ] **Phone Number ID & WABA ID Set:** Populate `PHONE_NUMBER_ID` and `WABA_ID`.
- [ ] **Webhook Webhook Verification Token Set:** Set `WHATSAPP_VERIFY_TOKEN` (min 32 chars).
- [ ] **Meta App Secret Configured:** Set `WHATSAPP_APP_SECRET` for HMAC-SHA256 signature verification.
- [ ] **Controlled Smoke Test Executed:** Send one test template/text message to a verified test phone number.

---

## 6. EMAIL (SMTP ADAPTER)
- [ ] **Production SMTP Server Configured:** Set `SMTP_HOST`, `SMTP_PORT` (587 or 465), `SMTP_USER`, and `SMTP_PASSWORD` (SendGrid / Postmark / AWS SES).
- [ ] **Sender Identity Verified:** Set `from_email` to a verified domain address (`notifications@yourdomain.com`).
- [ ] **DKIM & SPF Records Active:** Ensure DNS TXT records are valid on the sending domain.
- [ ] **Controlled Smoke Test Executed:** Send one test confirmation email to an approved internal test address.

---

## 7. PAYMENT & BILLING (RAZORPAY)
- [ ] **Live Mode Key Configured:** Set `RAZORPAY_KEY_ID=rzp_live_<key>` in production.
- [ ] **Live Mode Secret Configured:** Set `RAZORPAY_KEY_SECRET=<secret>`.
- [ ] **Webhook Endpoint Registered in Dashboard:** Set `https://<api_domain>/api/v1/billing/razorpay-webhook`.
- [ ] **Webhook Secret Configured:** Set `RAZORPAY_WEBHOOK_SECRET` (min 32 chars).
- [ ] **Live Signature Verification Smoke Test:** Verify HMAC signature validation with test webhook payload.

---

## 8. SECURITY, CREDENTIALS & AUDIT LOGGING
- [ ] **Cryptographic Random `SECRET_KEY`:** Generate 64-character random string for JWT signing and AES encryption.
- [ ] **Tenant Isolation Verified:** Verify `get_or_create_automation_state` blocks cross-tenant lead access with `PermissionError`.
- [ ] **Prompt Injection Defense Active:** Verify system instructions explicitly treat customer message content as untrusted data.
- [ ] **Logs Sanitized:** Ensure no passwords, raw bearer tokens, or unmasked PII are emitted to stdout or log aggregators.
- [ ] **CORS Origins Restricted:** Set `CORS_ORIGINS=["https://app.yourdomain.com", "https://yourdomain.com"]`.

---

## 9. AUTONOMOUS LOOP SAFETY & EMERGENCY CONTROLS
- [ ] **Global Emergency Pause Verified:** Test `EmergencyAutomationPauseService.set_global_pause(True)` immediately halts all loops.
- [ ] **Tenant Emergency Pause Verified:** Verify `/autonomous-loop/emergency/pause` is accessible by broker admins.
- [ ] **Broker Takeover Mechanism Verified:** Verify `/leads/{lead_id}/handoff` halts autonomous actions for the lead.
- [ ] **Quiet Hours Active:** Confirm customer timezone quiet-hours blocking is active.
- [ ] **Fatigue Guard Active:** Confirm daily and weekly message frequency limits are enforced.

---

## 10. FRONTEND WEB APPLICATION (`apps/web`)
- [ ] **Next.js Production Build Verified:** Run `npm run build` with 0 TypeScript/build errors.
- [ ] **Production API URL Set:** Configure `NEXT_PUBLIC_API_URL=https://api.yourdomain.com/api/v1`.
- [ ] **Frontend Domain URL Set:** Configure `NEXT_PUBLIC_FRONTEND_URL=https://app.yourdomain.com`.
- [ ] **No Localhost References in Client Bundle:** Audit build bundle to ensure no hardcoded `localhost:8000` strings.
- [ ] **Authentication Callback Configured:** Verify `/auth/callback` handles tokens correctly.

---

## 11. OBSERVABILITY & READINESS PROBES
- [ ] **Deep Health Endpoint Active:** `/api/v1/health-diag/deep` returns full subsystem breakdown.
- [ ] **Kubernetes Liveness Probe:** Point to `/api/v1/health-diag/liveness`.
- [ ] **Kubernetes Readiness Probe:** Point to `/api/v1/health-diag/readiness`.
- [ ] **Prometheus Metrics Scraped:** Verify `/metrics` scrapes `LOOP_EVENTS_TOTAL`, `LOOP_GUARD_BLOCKS`, `LOOP_PROCESSING_LATENCY`.

---

## 12. SIGN-OFF & GO-LIVE AUTHORIZATION
- [ ] **Lead Architect Sign-off:** ___________________________
- [ ] **Security Lead Sign-off:** ___________________________
- [ ] **Operations Lead Sign-off:** ___________________________
- [ ] **Go-Live Date:** ___________________________
