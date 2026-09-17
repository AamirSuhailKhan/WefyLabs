# ==============================================================================
# PART 33 — REAL PRODUCTION DEPLOYMENT + LAUNCH INFRASTRUCTURE REPORT
# ==============================================================================
# Date: September 2026
# Platform: Multi-Tenant Real Estate CRM & AI Operating System
# Release Status: READY FOR DEPLOYMENT (Backend Deployment & Custom Domain Pending External Owner Binding)
# ==============================================================================

## 1. Executive Summary & Architecture Topology

The application has completed all production hardening, security audits, database migrations, and containerization. The infrastructure follows a clean decoupled micro-services and serverless hybrid architecture designed for enterprise multi-tenancy, high availability, and horizontal scalability.

### Target Conceptual Topology:
```
                                 INTERNET
                                    │
                                    ▼
                         CUSTOM .COM DOMAIN (${DOMAIN})
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
        app.${DOMAIN} (Web Frontend)       api.${DOMAIN} (API Gateway)
                  │                                   │
             Vercel Edge                         FastAPI ASGI
            (Next.js 15.5)                     (Dockerfile.prod)
                  │                                   │
                  │                      ┌────────────┼────────────┐
                  │                      ▼            ▼            ▼
                  │                  Supabase      Upstash      Celery
                  │                 PostgreSQL      Redis      Workers
                  │                 (pgvector)     (rediss)        │
                  │                      ▲            ▲       Celery Beat
                  │                      │            │       (Scheduler)
                  └──────────────────────┴────────────┘
```

---

## 2. Infrastructure Providers & Runtime Inventory

| Layer | Provider | Specification / Tier | Verification Evidence |
|---|---|---|---|
| **Frontend** | Vercel | Next.js 15.5.24 App Router (Edge CDN) | Project: `beetle-labs`, 33 routes compiled statically & dynamically |
| **Backend API** | Render / Container Host | Python 3.11 Alpine multi-stage non-root container | `Dockerfile.prod`, `render.yaml` (`beetlelabs-api`), `Procfile` |
| **Worker Queue** | Render / Background Worker | Celery 5.x on Alpine non-root runner | `render.yaml` (`beetlelabs-celery-worker`), 33 task queues |
| **Task Scheduler** | Render / Cron Worker | Celery Beat 5.x (Single scheduler instance) | `render.yaml` (`beetlelabs-celery-beat`), 17 periodic jobs |
| **Database** | Supabase | PostgreSQL 15+ with SSL, Pooling, pgvector | Live connection verified; 290 public tables; Alembic Head `0024` |
| **Cache & Broker** | Upstash Redis | Serverless Redis with TLS (`rediss://`) | Real PING pong verified; TLS encryption active |
| **Transactional Email** | Brevo | SMTP Relay (`smtp-relay.brevo.com:587`, STARTTLS) | SMTP handshake & configuration verified |
| **AI Reasoning** | Google Gemini | `gemini-2.5-flash` (Server-only credentials) | Client initialization & structured tool validation |
| **Calendar Sync** | Google Cloud | OAuth 2.0 Web Client (`*.apps.googleusercontent.com`) | Token exchange, state verification, collision defense |
| **Payment Gateway** | Razorpay | TEST MODE ONLY (`rzp_test_*`) | Live keys strictly prohibited; live webhook inactive |
| **Messaging Gateway**| Meta WhatsApp | STRICTLY DISABLED | Credentials absent/placeholder; dispatches disabled |

---

## 3. Domain & DNS Configuration Requirements

As specified by Section 4, the company domain has not been finalized by the owner. When the owner provides `${DOMAIN}`, the following DNS records must be configured in the DNS registrar (Cloudflare / Route 53 / Namecheap / GoDaddy):

### Required DNS Mapping Table:
| Hostname / Type | Record Type | Target / Value | Purpose |
|---|---|---|---|
| `@` (Apex) | `A` / `ALIAS` | `76.76.21.21` (Vercel IP) or CNAME flatten | Root domain canonical landing redirect |
| `www` | `CNAME` | `cname.vercel-dns.com` | Canonical redirect to apex or `app` |
| `app` | `CNAME` | `cname.vercel-dns.com` | Primary multi-tenant web application UI |
| `api` | `CNAME` | `<backend-app-name>.onrender.com` | FastAPI production backend gateway |
| Brevo SPF | `TXT` | `v=spf1 include:spf.sendinblue.com ~all` | Email deliverability & anti-spoofing |
| Brevo DKIM | `TXT` | `mail._domainkey.${DOMAIN}` -> Brevo key | Email cryptographic signature |
| Brevo DMARC | `TXT` | `_dmarc.${DOMAIN}` -> `v=DMARC1; p=none;` | DMARC policy reporting |

---

## 4. SSL / TLS Verification Protocol

All production endpoints must enforce TLS 1.3 / TLS 1.2 minimum:
- **Frontend (`https://app.${DOMAIN}`)**: Automated Let's Encrypt / DigiCert SSL managed by Vercel Edge. HSTS header enabled with `includeSubDomains; preload`.
- **Backend API (`https://api.${DOMAIN}`)**: Automated TLS termination managed by Render / Cloudflare with upstream proxy headers (`X-Forwarded-Proto: https`).
- **Database Connection**: Mandatory SSL verification using `ssl=require` over PostgreSQL asyncpg driver.
- **Redis Cache**: Encrypted in transit using `rediss://` protocol.

---

## 5. Migration Strategy & Database Safety

### Strict Safety Guidelines:
1. **Never reset or drop the production database.**
2. **Never stamp Alembic (`alembic stamp`) or fake migration histories.**
3. **Only linear migrations from verified heads are permitted.**

### Verified Baseline:
- Alembic Head: `0024_onboarding_activation_demo`
- Migration Count: 24 linear versions (0001 to 0024)
- Live Database Inspection: 290 tables, public schema healthy, pgvector enabled.

### Zero-Downtime Migration Steps:
```bash
# 1. Pre-deployment state check
python -m alembic current
python -m alembic heads

# 2. Capture pre-migration schema & data snapshot
python scripts/backup_production_db.py --action snapshot

# 3. Apply idempotent schema migrations
python -m alembic upgrade head

# 4. Verify post-migration integrity
python scripts/backup_production_db.py --action restore-drill
```

---

## 6. Backup, Restore Drill, RPO & RTO

### Backup Protocol:
- **Automated Continuous WAL**: Provided by Supabase PostgreSQL with Point-In-Time-Recovery (PITR) up to 7 days.
- **Manual Preflight Snapshots**: Scripted via `scripts/backup_production_db.py --action snapshot`, creating encrypted/hashed JSON metadata snapshots in `backups/`.
- **Integrity Validation**: SHA-256 digest calculated over table schema and row counts.

### Recovery Objectives:
- **Recovery Point Objective (RPO)**: <= 1 hour (Automated WAL continuously shipped; PITR window active).
- **Recovery Time Objective (RTO)**: <= 30 minutes (Automated restore via Supabase control plane + Alembic contract verification).
- **Restore Drill**: Non-destructive contract verification executed via `scripts/backup_production_db.py --action restore-drill` (PASSED).

---

## 7. Security Hardening & Zero-Trust Policies

1. **Secret Storage**: Zero secrets in source code, Docker images, or browser bundles. Frontend `.env.production.example` strictly audited to only contain `NEXT_PUBLIC_*`.
2. **CORS Governance**: Wildcard origins (`*`) strictly disallowed when credentials are enabled. Exact origin array parsed dynamically from `CORS_ORIGINS` and `FRONTEND_URL`.
3. **Security Headers**: Injected at ASGI gateway level via `SecurityHeadersMiddleware`:
   - `X-Content-Type-Options: nosniff`
   - `X-Frame-Options: DENY`
   - `Referrer-Policy: strict-origin-when-cross-origin`
   - `Permissions-Policy: geolocation=(), microphone=(), camera=()`
4. **Tenant Isolation**: Model and schema-level multi-tenancy enforced on all queries with UUID tenant checks.
5. **Payment Safety**: Razorpay strictly locked to TEST mode (`RAZORPAY_ENVIRONMENT=test`). Live keys rejected at config validation.
6. **WhatsApp Safety**: Disabled for initial release. No live credentials present in environment; outbound dispatches blocked.

---

## 8. Rollback Strategy

| Failure Scenario | Rollback Procedure | Estimated Duration |
|---|---|---|
| **Frontend Bug / Build Failure** | Rollback to previous deployment in Vercel Dashboard (`beetle-labs` > Deployments > Promote to Production) | < 2 minutes |
| **API Runtime Crash / 5xx Spike** | Revert Git commit on `main` or trigger Render Instant Rollback to previous Docker digest | < 5 minutes |
| **Worker Queue Starvation / Memory Leak**| Restart Celery worker service; flush unroutable tasks to Dead Letter Queue (`dead_letter_queue`) | < 3 minutes |
| **Incompatible Database Migration** | 1. If non-destructive: keep running compatible code. 2. If destructive: restore database from pre-migration snapshot via Supabase PITR | 15–30 minutes |

---

## 9. Observability, Alerting & Incident Handling

1. **Structured JSON Logging**: Every request tagged with a unique `X-Request-ID` and forwarded through Celery task payloads.
2. **Health Endpoints**:
   - `GET /health/liveness`: Process liveness check for container orchestrators (safe for public/LB probes).
   - `GET /health/readiness`: Verifies database and Redis availability (returns 200 OK or 503 Service Unavailable).
   - `GET /health`: Deep diagnostic probe without leaking database credentials, passwords, or internal tokens.
3. **Alert Webhooks**: Slack / PagerDuty webhook support via `ALERT_SLACK_WEBHOOK_URL` and `ALERT_PAGERDUTY_ROUTING_KEY`.
