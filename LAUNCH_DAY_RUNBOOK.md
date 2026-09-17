# ==============================================================================
# LAUNCH DAY OPERATIONS RUNBOOK (T-24H TO T+24H)
# ==============================================================================
# Platform: Multi-Tenant Real Estate CRM & AI Operating System
# Objective: Coordinate smooth production cutover with zero downtime and strict security.
# ==============================================================================

## Timeline & Checklist

### T - 24 Hours (Launch Eve Pre-Flight)
- [ ] **Alembic Single Head**: Confirm `0025_property_total_floors` is active on Supabase.
- [ ] **Infrastructure Probe**: Run `python apps/api/scripts/verify_production_infra.py` (DB, Redis, SMTP, Razorpay TEST mode).
- [ ] **Code Freeze**: Freeze `main` branch against non-essential feature PRs.
- [ ] **Backup Snapshot**: Run `python scripts/backup_production_db.py --action snapshot`.
- [ ] **Domain & DNS Verification**: Ensure TTL on DNS records is lowered to 300s (5 minutes) for rapid propagation.
- [ ] **SSL Certificates**: Verify TLS validity on `*.${DOMAIN}`.

### T - 1 Hour (Final System Warmup)
- [ ] **Database Connection Pool**: Check Supabase pooler connections (confirm < 20% active connection utilization).
- [ ] **Upstash Redis Health**: Confirm TLS ping latency < 50ms.
- [ ] **Email Relay Probe**: Test Brevo SMTP relay connection.
- [ ] **Google OAuth Client**: Verify production Authorized Redirect URI matches `https://app.${DOMAIN}/auth/callback`.
- [ ] **Payment Safety Check**: Verify Razorpay keys start with `rzp_test_` and `RAZORPAY_ENVIRONMENT=test`.
- [ ] **WhatsApp Safety Check**: Verify `WHATSAPP_ENABLED=false` and no live tokens are present.

### T - 15 Minutes (Deployment Readiness)
- [ ] **Container Status**: Confirm `beetlelabs-api` container built with non-root user `appuser`.
- [ ] **Worker Verification**: Confirm `beetlelabs-celery-worker` listening to 50 configured queues.
- [ ] **Beat Scheduler**: Confirm single `beetlelabs-celery-beat` scheduler active (21 periodic jobs).
- [ ] **Liveness Probe**: Call `GET https://api.${DOMAIN}/health/liveness` -> HTTP 200.
- [ ] **Readiness Probe**: Call `GET https://api.${DOMAIN}/health/readiness` -> HTTP 200.

---

## T = 0 (LAUNCH CUTOVER)
- [ ] **Switch DNS Routing**: Point `app.${DOMAIN}` and `api.${DOMAIN}` to production endpoints.
- [ ] **Vercel Production Traffic**: Route 100% traffic to production deployment bundle.
- [ ] **Broadcast Operational Readiness**: Notify internal stakeholder channel of active public availability.

---

### T + 15 Minutes (Immediate Post-Launch Verification)
- [ ] **Smoke Test 1 (User Authentication)**: Complete end-to-end signup and login with test broker.
- [ ] **Smoke Test 2 (Workspace Creation)**: Provision new organization and initialize onboarding state.
- [ ] **Smoke Test 3 (Inventory & Lead)**: Create lead and property listing; verify deterministic match generation.
- [ ] **Smoke Test 4 (Command Center)**: Open Agent Command Center; verify follow-up task rendering.
- [ ] **5xx Error Watch**: Confirm 0 unexpected server 500 errors in backend logs.

### T + 1 Hour (First Operational Checkpoint)
- [ ] **Latency Monitoring**: Verify p50 < 100ms, p95 < 250ms on API endpoints.
- [ ] **Worker Queue Depth**: Check Celery queues; confirm backlog is zero and tasks are processing smoothly.
- [ ] **Database Locks & Slow Queries**: Check Supabase metrics for slow query spikes (> 500ms).
- [ ] **Redis Memory & Quota**: Check Upstash daily commands quota and key eviction rates.
- [ ] **Transactional Email**: Confirm welcome emails dispatched via Brevo without bounce spikes.

### T + 4 Hours (Scale & Stability Verification)
- [ ] **Gemini AI Usage**: Monitor token consumption, rate limits, and fallback triggers.
- [ ] **Google Calendar Sync**: Verify token storage, refresh, and no-show prediction tasks.
- [ ] **Memory Consumption**: Confirm API containers and Celery workers are stable without memory leaks.
- [ ] **Multi-Tenant Data Isolation**: Audit query logs to ensure 0 cross-tenant data leakage.

### T + 24 Hours (Full Day Sign-off & Normalization)
- [ ] **Daily Briefing Task**: Confirm scheduled task `send-daily-followup-briefing` executed at 07:00 UTC.
- [ ] **Daily DB Snapshot**: Run `python scripts/backup_production_db.py --action snapshot`.
- [ ] **DNS TTL Normalization**: Raise DNS TTL from 300s back to standard 3600s / 86400s.
- [ ] **Customer Support Ticket Review**: Check for reported client-side bugs or authorization issues.
- [ ] **Formal Status Transition**: Transition system state from Launch Watch to Standard Operations.
