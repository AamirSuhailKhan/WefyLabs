# PRODUCTION OPERATIONS RUNBOOK
# BeetleLabs Enterprise Real Estate CRM/SaaS

**Version**: 1.0 (Part 32)  
**Last Updated**: 2026-09-12

---

## Architecture Overview

```
[Browser/Mobile]
      |
  [Vercel/CDN] ── Next.js 15.5.24 frontend
      |
  [Render.com]
  ┌─────────────────────────────────────────┐
  │  beetlelabs-api (FastAPI + Uvicorn 4W)  │
  │  beetlelabs-celery-worker (Celery)      │
  │  beetlelabs-celery-beat (Celery Beat)   │
  └─────────────────────────────────────────┘
      |                    |
[Supabase Postgres]   [Upstash Redis]
(PgBouncer Pooler)    (TLS, rediss://)
```

---

## Daily Operations

### Health Dashboard
```
GET /health          → Full dependency status
GET /health/liveness → Pod alive check
GET /health/readiness → DB + Redis probe
GET /metrics         → Prometheus metrics
```

### Log Monitoring
Structured JSON logs are emitted to Render's log stream.

Key log patterns to monitor:
- `"level": "ERROR"` — Application errors
- `"level": "CRITICAL"` — Config failures, fatal errors
- `[Readiness] DB probe failed` — Database connectivity issues
- `[Readiness] Redis probe failed` — Redis connectivity issues
- `[Alembic]` — Migration events on startup
- `[SMTP]` — Email delivery issues

### Celery Task Monitoring
```bash
# Check active tasks (requires Redis CLI access)
redis-cli -u $REDIS_URL keys "celery*" | wc -l

# Check failed tasks in dead letter queue
redis-cli -u $REDIS_URL llen dead_letter_queue
```

---

## Deployment Procedures

### Standard Deployment (Render autoDeploy)
1. Merge PR to `main` branch
2. Render automatically: builds → runs Alembic migrations → deploys
3. Health check at `/health/readiness` must return 200 for deployment to succeed
4. Monitor Render dashboard for any deploy failures

### Emergency Hotfix Deployment
1. Create hotfix branch from `main`
2. Make change, run tests: `pytest tests/ -v --tb=short`
3. Push directly to `main` (emergency only)
4. Monitor deploy log in Render

### Rollback
```
Render Dashboard → beetlelabs-api → Deploys → Select previous deploy → Rollback
```

---

## Database Operations

### Schema Migrations
```bash
# Create new migration (never use stamp)
python -m alembic revision --autogenerate -m "description_of_change"

# Apply migration
python -m alembic upgrade head

# Check current state
python -m alembic current

# Check heads (should always be exactly 1)
python -m alembic heads

# Rollback one step (emergency only)
python -m alembic downgrade -1
```

### Connection Pool Status
```sql
-- Current active connections
SELECT count(*), state FROM pg_stat_activity 
WHERE datname = 'postgres' GROUP BY state;

-- Long-running queries (>30s)
SELECT pid, query_start, state, query 
FROM pg_stat_activity 
WHERE (now() - query_start) > interval '30 seconds'
  AND datname = 'postgres';

-- Kill slow query
SELECT pg_terminate_backend(<pid>);
```

---

## Celery Operations

### Check Celery Status
```bash
# Inspect active workers
celery -A app.celery_app.celery_app inspect active

# Inspect scheduled tasks
celery -A app.celery_app.celery_app inspect scheduled

# Check beat schedule
celery -A app.celery_app.celery_app inspect registered
```

### Dead Letter Queue Recovery
```bash
# List DLQ messages (use redis-cli)
redis-cli -u $REDIS_URL lrange dead_letter_queue 0 -1

# Retry failed tasks (move back to default queue)
redis-cli -u $REDIS_URL lmove dead_letter_queue lead_queue RIGHT LEFT
```

---

## Environment Variable Reference

| Variable | Required | Description |
|----------|---------|-------------|
| `ENV` | ✅ | `production` / `staging` / `development` / `testing` |
| `DATABASE_URL` | ✅ | Supabase PostgreSQL connection URL (asyncpg) |
| `REDIS_URL` | ✅ | Upstash Redis URL (rediss://) |
| `SECRET_KEY` | ✅ | JWT signing key (min 32 chars) |
| `SUPABASE_JWT_SECRET` | ✅ | Supabase project JWT secret |
| `GEMINI_API_KEY` | ✅ | Google Gemini API key |
| `SMTP_HOST` | ✅ | Brevo SMTP host |
| `SMTP_USER` | ✅ | Brevo SMTP username |
| `SMTP_PASSWORD` | ✅ | Brevo SMTP API key |
| `CORS_ORIGINS` | ✅ | Comma-separated allowed origins |
| `TRUSTED_PROXY_IPS` | ✅ | Render proxy IP ranges |
| `RAZORPAY_KEY_ID` | ✅ | Razorpay key (rzp_test_* for test mode) |
| `RAZORPAY_ENVIRONMENT` | ✅ | `test` (DO NOT set to `live` until authorized) |
| `GOOGLE_CLIENT_ID` | ✅ | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | ✅ | Google OAuth client secret |
| `ALERT_SLACK_WEBHOOK_URL` | ⚠️ | Slack webhook for alerts (optional but recommended) |
| `WORKERS` | optional | Uvicorn worker count (default: 4) |

---

## Incident Command

In any production incident:
1. **Declare incident** — notify team via Slack
2. **Assign Incident Commander** — one person owns coordination
3. **Open incident channel** — `#incident-YYYY-MM-DD`
4. **Follow SECURITY_INCIDENT_RESPONSE.md** for specific procedures
5. **Document timeline** in real-time during incident
6. **Post-mortem within 48 hours**

---

## Monitoring & Alerting

### Prometheus Metrics (GET /metrics)
Key metrics to monitor:
- `http_requests_total` — Request count by endpoint/status
- `http_request_duration_seconds` — Latency histogram
- Custom BeetleLabs metrics from `metrics_registry`

### Alert Channels
Configure via environment variables:
- `ALERT_SLACK_WEBHOOK_URL` — Slack channel webhook
- `ALERT_PAGERDUTY_ROUTING_KEY` — PagerDuty on-call routing
- `ALERT_WEBHOOK_URL` — Generic webhook (for custom alerting)
