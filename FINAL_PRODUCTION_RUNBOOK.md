# ==============================================================================
# FINAL PRODUCTION RUNBOOK
# ==============================================================================
# Platform: BeetleLabs Multi-Tenant Real Estate CRM & AI Operating System
# Classification: Confidential Production Runbook
# Revision: 2.0 (Part 34 Go-Live Release)
# ==============================================================================

## 1. System Topology Overview

```
                                  [USER TRAFFIC]
                                        │
                                        ▼
                             [EDGE CDN / ROUTING]
                         https://app.${DOMAIN} (Web)
                         https://api.${DOMAIN} (API)
                                        │
                   ┌────────────────────┴────────────────────┐
                   ▼                                         ▼
         [Vercel Edge Platform]                   [Render / Container Host]
         Next.js 15.5.24 (App Router)             FastAPI (Python 3.11/3.14)
         Node.js 24 runtime                       Non-root user: appuser
                   │                                         │
                   │                              ┌──────────┼──────────┐
                   │                              ▼          ▼          ▼
                   │                           Supabase   Upstash    Celery
                   │                          PostgreSQL   Redis    Workers
                   │                          (pgvector)  (rediss)  (50 queues)
                   │                              ▲          ▲          │
                   │                              │          │     Celery Beat
                   │                              │          │     (21 jobs)
                   └──────────────────────────────┴──────────┴──────────┘
```

---

## 2. Pre-Deployment Verification Protocol

Before cutting over production traffic, verify all services using automated tools:

### Step 1: Database & Migrations
```bash
cd apps/api
# Check Alembic single head
python -m alembic current
# Expected: 0025_property_total_floors (head)

python -m alembic heads
# Expected: 0025_property_total_floors (head)
```

### Step 2: Infrastructure Diagnostics
```bash
cd apps/api
python scripts/verify_production_infra.py
```
Expected output:
- `[DATABASE] PASS — Connected to Supabase PostgreSQL | Tables: 290 | Alembic Head: 0025_property_total_floors`
- `[REDIS] PASS — Upstash Redis PING OK | TLS: True`
- `[BREVO SMTP] PASS — Host: smtp-relay.brevo.com:587`
- `[RAZORPAY] TEST_MODE_ACTIVE | LIVE DISABLED: True`
- `[GOOGLE OAUTH] Configured: True`

### Step 3: Celery Worker & Upstash Broker Drill
```bash
cd apps/api
python test_worker_task_execution.py
```
Expected output:
- `CELERY WORKER DRILL: ALL CHECKS PASSED (EVIDENCE RECORDED)`

### Step 4: Frontend Type Check & Production Build
```bash
cd apps/web
npx tsc --noEmit
npm run build
```
Expected output:
- `0 TypeScript errors`
- `33/33 static/dynamic routes compiled successfully`

---

## 3. Public Health Endpoints & SLA

| Endpoint | Method | Expected HTTP | Content Guarantee | Purpose |
|---|---|---|---|---|
| `/health/liveness` | GET | 200 OK | `{"status": "alive", "version": "1.0.0"}` | Container alive probe. Never checks DB/Redis. |
| `/health/readiness`| GET | 200 OK (or 503) | `{"status": "ready", "database": "ok", "cache": "ok"}` | Validates active DB pool & Upstash Redis ping. |
| `/health` | GET | 200 OK | Detailed dependency report with zero credential leak | Human diagnostics and monitoring scrapers. |

---

## 4. Launch Day Cutover Steps (Owner Actions)

When the company `.com` domain `${DOMAIN}` is finalized:

1. **DNS Cutover (Registrar)**:
   - Point `@` (Apex) to Vercel IP: `76.76.21.21`
   - Point `app` CNAME to `cname.vercel-dns.com`
   - Point `api` CNAME to `<render-service-name>.onrender.com`
   - Add Brevo SPF: `v=spf1 include:spf.sendinblue.com ~all`
   - Add Brevo DKIM: `mail._domainkey.${DOMAIN}`

2. **Vercel Project Setup**:
   - Add domain `app.${DOMAIN}` to Vercel Project Settings.
   - Set environment variables:
     - `NEXT_PUBLIC_API_URL=https://api.${DOMAIN}/api/v1`
     - `NEXT_PUBLIC_FRONTEND_URL=https://app.${DOMAIN}`

3. **Backend Host Environment Setup**:
   - In Render/Hosting Dashboard, bind environment variables:
     - `ENV=production`
     - `API_URL=https://api.${DOMAIN}`
     - `FRONTEND_URL=https://app.${DOMAIN}`
     - `CORS_ORIGINS=https://app.${DOMAIN},https://${DOMAIN}`
     - `GOOGLE_OAUTH_REDIRECT_URI=https://app.${DOMAIN}/auth/callback`

4. **Google Cloud Console Update**:
   - Navigate to Google Cloud Console > APIs & Services > Credentials.
   - Under OAuth 2.0 Web Client ID, add Authorized Redirect URI:
     - `https://app.${DOMAIN}/auth/callback`

---

## 5. Rollback Procedures

| Component | Trigger | Rollback Action | RTO |
|---|---|---|---|
| **Frontend** | UI crash, broken assets, client-side JS exception | Vercel Dashboard > Deployments > Select previous healthy build > **Promote to Production** | < 2 minutes |
| **Backend API** | 5xx spike, container crash loop | Revert Git commit or trigger Instant Rollback to previous Docker digest in Render dashboard | < 5 minutes |
| **Celery Worker** | Task failure spike, queue starvation | Restart worker container; unroutable tasks automatically re-routed to `dead_letter_queue` | < 3 minutes |
| **Database Migration** | Incompatible schema change | Use Supabase Point-in-Time Recovery (PITR) to restore state prior to migration timestamp | 15–30 minutes |

---

## 6. Safety & Guardrail Policies

1. **Razorpay Payments**:
   - **STRICTLY TEST MODE ONLY**.
   - Live keys (`rzp_live_*`) are rejected at application startup and blocked by automated tests.
   - Real financial charges are strictly disabled.

2. **Meta WhatsApp**:
   - **STRICTLY DISABLED**.
   - Outbound dispatch returns early with disabled status.
   - Webhooks return structured acknowledgment without executing background tasks.

3. **Multi-Tenant Isolation**:
   - Every SQL query requires explicit `organization_id` or `broker_id` scoping.
   - Direct database access across organization boundaries returns HTTP 404 or 403.
