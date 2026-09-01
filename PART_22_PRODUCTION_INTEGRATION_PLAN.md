# BEETLELABS — PART 22
# PRODUCTION INTEGRATION, REAL PROVIDER CONFIGURATION & LIVE-TRAFFIC READINESS PLAN

**Date:** August 25, 2026  
**Scope:** Real Provider Configuration, Health State Truthfulness, Global Emergency Safety, E2E Smoke & Live Readiness  
**Author:** Principal Architect & Security Lead  

---

## 1. Executive Summary

BeetleLabs Parts 21.1 through 21.9 implemented the deterministic Autonomous Sales Loop, AI prospect intelligence, property recommendation, lead qualification, communication adapters, and safety guard chains.

**Part 22 moves the system from "verified software" to "live operational readiness"** by auditing external environment dependencies, establishing truthful integration states, implementing global emergency automation controls, hardening health diagnostics against fabricated status, and constructing a comprehensive Part 22 production integration test suite.

---

## 2. Environment & Variable Inventory Audit

### 2.1 Backend (`apps/api/.env` vs `validated_settings.py`)

| Environment Variable | Required in Prod | Current Type / Value Type | Production Safe? | Status |
|---|---|---|---|---|
| `ENV` | Yes | `development` / `production` | Yes | CONFIGURED |
| `API_URL` | Yes | URL (`http://localhost:8000`) | Dev Only | CONFIGURATION_REQUIRED |
| `FRONTEND_URL` | Yes | URL (`http://localhost:3000`) | Dev Only | CONFIGURATION_REQUIRED |
| `DATABASE_URL` | Yes | PostgreSQL asyncpg URL | Localhost | CONFIGURATION_REQUIRED |
| `REDIS_URL` | Yes | Redis connection URL | Localhost | CONFIGURATION_REQUIRED |
| `SECRET_KEY` | Yes | JWT HMAC Secret (min 32b) | Dev Secret | CONFIGURATION_REQUIRED |
| `SUPABASE_URL` | Yes | Supabase Project URL | Placeholder | CONFIGURATION_REQUIRED |
| `SUPABASE_JWT_SECRET` | Yes | Supabase JWT Secret | Placeholder | CONFIGURATION_REQUIRED |
| `GEMINI_API_KEY` | Yes | Google AI Studio Key | Real Key | CONFIGURED (Rate Limit Verified) |
| `GEMINI_MODEL` | Yes | Model identifier | `gemini-3.5-flash` | CONFIGURED |
| `WHATSAPP_ACCESS_TOKEN`| Yes | Meta Cloud Access Token | Placeholder | CONFIGURATION_REQUIRED |
| `PHONE_NUMBER_ID` | Yes | Meta Phone Number ID | Placeholder | CONFIGURATION_REQUIRED |
| `WHATSAPP_VERIFY_TOKEN`| Yes | Webhook Verification Token | Static Dev | CONFIGURATION_REQUIRED |
| `WHATSAPP_APP_SECRET` | Yes (Prod) | Meta App Secret for HMAC | Missing in `.env` | CONFIGURATION_REQUIRED |
| `RAZORPAY_KEY_ID` | Yes | Razorpay Key (`rzp_live_*`) | Placeholder (`rzp_test_*`) | CONFIGURATION_REQUIRED |
| `RAZORPAY_KEY_SECRET` | Yes | Razorpay Secret | Placeholder | CONFIGURATION_REQUIRED |
| `RAZORPAY_WEBHOOK_SECRET`| Yes | Razorpay Webhook Secret | Placeholder | CONFIGURATION_REQUIRED |
| `GOOGLE_CLIENT_ID` | Yes | OAuth Client ID | Placeholder | CONFIGURATION_REQUIRED |
| `GOOGLE_CLIENT_SECRET` | Yes | OAuth Client Secret | Placeholder | CONFIGURATION_REQUIRED |
| `GOOGLE_OAUTH_REDIRECT_URI`| Yes | OAuth Callback URL | Localhost | CONFIGURATION_REQUIRED |
| `SMTP_HOST` | Optional/Yes | SMTP Server Host | Missing in `.env` | CONFIGURATION_REQUIRED |
| `SMTP_PORT` | Optional/Yes | SMTP Server Port | Default (587) | CONFIGURED |
| `SMTP_USER` | Optional/Yes | SMTP Username | Missing in `.env` | CONFIGURATION_REQUIRED |
| `SMTP_PASSWORD` | Optional/Yes | SMTP Password | Missing in `.env` | CONFIGURATION_REQUIRED |

### 2.2 Frontend (`apps/web/.env*`)

| Variable | Target | Current Value | Production Safe? | Status |
|---|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | Client API endpoint | `http://localhost:8000/api/v1` | Dev Only | CONFIGURATION_REQUIRED |
| `NEXT_PUBLIC_FRONTEND_URL` | Client URL | `http://localhost:3000` | Dev Only | CONFIGURATION_REQUIRED |

---

## 3. Subsystem Readiness Matrix & Gap Analysis

| Subsystem | Target Provider | Current Environment State | Truthful Operational Status | Live Verification Blocker |
|---|---|---|---|---|
| **1. Database Engine** | PostgreSQL + pgvector | In-Memory (Tests) / Localhost (Dev) | `CONFIGURATION_REQUIRED` | Live Supabase/PostgreSQL instance required for production traffic |
| **2. Task Queue / Broker** | Redis + Celery | Localhost / In-Memory fallback | `CONFIGURATION_REQUIRED` | Production Redis cluster required |
| **3. AI Reasoning Engine** | Google Gemini | Real API Key Active | `LIVE_VERIFIED` (Quota Active) | Free tier rate-limit active; quota upgrade required for high traffic |
| **4. Calendar & Scheduling** | Google Calendar API | OAuth Service Implemented | `CONFIGURATION_REQUIRED` | Real Google Cloud OAuth Client ID/Secret + interactive consent |
| **5. WhatsApp Communication** | Meta Cloud API / 360Dialog | Direct Graph API Adapter | `CONFIGURATION_REQUIRED` | Real Meta Business WABA ID + Phone Number ID |
| **6. Email Communication** | SMTP Provider | Pure TLS/SSL SMTP Adapter | `CONFIGURATION_REQUIRED` | Real SMTP credentials (SES/Sendgrid/Postmark) |
| **7. Payment & Billing** | Razorpay Gateway | Real HMAC Webhook Adapter | `CONFIGURATION_REQUIRED` | Live Razorpay Key (`rzp_live_*`) & Webhook Secret |
| **8. Webhook Security** | Generic Webhook Engine | HMAC SHA-256 + Replay Defense | `CONFIGURED` / `VERIFIED` | Production webhook secrets required |
| **9. Autonomous Loop Safety** | Safety Guard Chain | Fail-Closed Guards Active | `CONFIGURED` / `VERIFIED` | Need Global Tenant Emergency Pause Switch |
| **10. Health & Observability** | DeepHealthService | Prometheus + Diagnostics | `VERIFICATION_REQUIRED` | Hardened health check required to eliminate dummy status |

---

## 4. Part 22 Implementation Action Plan

1. **Safety & Health Hardening:**
   - Harden `DeepHealthService` to accurately report `LIVE`, `DEGRADED`, `CONFIGURATION_REQUIRED`, or `UNAVAILABLE` without fabricated provider names or dummy latency.
   - Implement `EmergencyAutomationPauseService` and tenant-level emergency automation pause endpoints in `app/modules/autonomous_loop/`.
2. **Environment & Provider Verification Suite:**
   - Implement `tests/test_part22_production_integration.py` covering environment fail-closed validation, health diagnostic truthfulness, Celery task structure, Google OAuth encryption & CSRF security, WhatsApp and SMTP truthful error classification, Razorpay signature security, webhook replay defenses, and global emergency automation pause.
3. **Full Regression Execution:**
   - Execute all 15 test suites (Parts 21.1–21.9 + Part 22) to maintain 100% test coverage.
4. **Frontend Production Build Verification:**
   - Verify `apps/web` builds with 0 errors and audit production URL configurations.
5. **Deployment Artifacts:**
   - Generate `PART_22_PRODUCTION_DEPLOYMENT_CHECKLIST.md`.
   - Generate `PART_22_PRODUCTION_INTEGRATION_REPORT.md`.
