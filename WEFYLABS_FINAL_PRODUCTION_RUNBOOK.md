# WEFYLABS FINAL PRODUCTION RUNBOOK
# Authoritative operational guide for first deployment

## 1. Prerequisites

| Requirement | Verification |
|---|---|
| Render.com account with deployment access | Required |
| PostgreSQL 16 database with pgvector extension | Required — create via Render or external provider |
| Redis 7+ instance | Required — Render Redis or external |
| Google Gemini API key (AIzaSy...) | Required — console.cloud.google.com |
| Brevo SMTP account (or compatible SMTP) | Required for email delivery |
| Domain configured (app.wefylabs.com) | Required for OAuth redirect URIs |

---

## 2. Deployment Steps

### Step 1 — Deploy from render.yaml
```bash
# Push to main branch — Render auto-deploys via autoDeploy: true
git push origin main
```

### Step 2 — Configure Environment Variables in Render Dashboard
Set the following variables for all 3 services (wefylabs-api, wefylabs-celery-worker, wefylabs-celery-beat):

| Variable | Example |
|---|---|
| DATABASE_URL | postgresql+asyncpg://user:pass@host:5432/wefylabs |
| REDIS_URL | redis://host:6379/0 |
| GEMINI_API_KEY | AIzaSy... |
| SUPABASE_JWT_SECRET | (32+ char random string) |
| SMTP_HOST | smtp-relay.brevo.com |
| SMTP_PORT | 587 |
| SMTP_USER | (Brevo username) |
| SMTP_PASSWORD | (Brevo SMTP key) |
| CORS_ORIGINS | https://app.wefylabs.com,https://wefylabs.com |
| GOOGLE_CLIENT_ID | ...apps.googleusercontent.com |
| GOOGLE_CLIENT_SECRET | GOCSPX-... |
| GOOGLE_OAUTH_REDIRECT_URI | https://app.wefylabs.com/auth/callback |

### Step 3 — Run Database Migrations
```bash
# SSH into Render shell or run via one-off job
alembic upgrade head
# Verify:
alembic current
# Expected: 0027_customer_identity_canonical (head)
```

### Step 4 — Post-Deploy Smoke Tests
```bash
# Health check
curl https://api.wefylabs.com/health

# OpenAPI spec
curl https://api.wefylabs.com/api/v1/openapi.json | python -m json.tool | grep '"paths"'

# Auth endpoint
curl -X POST https://api.wefylabs.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"wrong"}' 
# Expected: 401 Unauthorized
```

---

## 3. Health Check Paths

| Path | Purpose |
|---|---|
| `/health` | Application-level health |
| `/health/readiness` | Render health check target |
| `/metrics` | Prometheus metrics |
| `/api/v1/docs` | OpenAPI Swagger UI |

---

## 4. Celery Worker Verification
```bash
# Check Celery worker is running
# In Render dashboard: wefylabs-celery-worker service logs should show:
# [celery@...] mingle: searching for neighbors
# [celery@...] mingle: all alone
# [celery@...] celery@... ready.

# Check Celery beat is running  
# In Render dashboard: wefylabs-celery-beat service logs should show:
# beat: Starting...
# Scheduler: Sending due task ...
```

---

## 5. Incident Response

| Incident | Action |
|---|---|
| API returns 500 | Check Render logs → app/main.py startup errors |
| Database connection refused | Verify DATABASE_URL + PostgreSQL service running |
| Redis connection refused | Verify REDIS_URL + Redis service running |
| Celery tasks not running | Check wefylabs-celery-beat service is up |
| AI responses failing | Verify GEMINI_API_KEY; check /api/v1/ai-agent/v1/monitoring/stats |
| Auth failing | Verify SECRET_KEY + SUPABASE_JWT_SECRET are set |

---

## 6. Known Limitations at Launch

1. **Media uploads** store to mock CDN URLs — disable media upload features until S3/R2 configured
2. **WhatsApp channel** not active — webchat and email are primary channels at launch
3. **Google Calendar** requires broker OAuth login — prompt brokers to connect calendar on first login
4. **Knowledge RAG** requires pgvector extension on PostgreSQL — verify extension installed
5. **Voice calls** not supported — no telephony provider configured
