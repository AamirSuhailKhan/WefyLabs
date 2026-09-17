# PRODUCTION DISASTER RECOVERY RUNBOOK
# BeetleLabs Enterprise Real Estate CRM/SaaS

**Version**: 1.0 (Part 32)  
**Last Updated**: 2026-09-12  
**RTO Target**: 30 minutes  
**RPO Target**: 5 minutes (last Supabase backup checkpoint)

---

## Failure Scenarios & Recovery Procedures

---

### Scenario 1: Complete API Service Outage

**Symptoms**: GET /health/liveness returns non-200 or times out

**Immediate Actions (< 5 min)**:
1. Check Render.com dashboard → Services → eetlelabs-api
2. Check recent deploy logs for startup errors
3. If crash-looping: roll back to last known good deploy
   `
   render deploy --service beetlelabs-api --image <previous-sha>
   `
4. If Alembic migration failure: check logs for [ERROR] Alembic migration failed
   - **DO NOT** run lembic stamp head — diagnose the actual migration failure first

**Recovery Verification**:
- GET /health/readiness returns {"status": "ready"}
- GET /api/v1/auth/login responds within 2 seconds

---

### Scenario 2: Database Connection Exhaustion

**Symptoms**: GET /health/readiness returns {"status": "not_ready", "issues": ["database_unavailable"]}; API logs show syncpg.TooManyConnectionsError or pool timeout

**Diagnosis**:
`sql
-- Run in Supabase SQL Editor
SELECT count(*), state FROM pg_stat_activity GROUP BY state;
SELECT pid, now() - pg_stat_activity.query_start AS duration, query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';
`

**Immediate Actions**:
1. Identify and terminate long-running queries:
   `sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity
   WHERE duration > interval '5 minutes' AND state = 'active';
   `
2. Restart eetlelabs-api service on Render (triggers connection pool refresh)
3. If pool_size is too low for current traffic, scale Render service tier

**Prevention**: Pool configured in Part 32 — pool_size=10, max_overflow=20, command_timeout=20s

---

### Scenario 3: Redis / Upstash Outage

**Symptoms**: GET /health/readiness returns {"issues": ["redis_unavailable"]}; Rate limiting and caching disabled; Celery tasks not dispatching

**Immediate Actions**:
1. Check Upstash dashboard for incidents: https://status.upstash.com
2. API degrades gracefully — core CRUD operations still work (Redis is for rate limiting + Celery broker)
3. If Upstash is down, Celery workers will fail to connect — tasks will queue up and retry when Redis recovers

**Recovery Verification**:
- GET /health → "redis": {"status": "ok"}

---

### Scenario 4: Alembic Migration Failure on Deploy

**Symptoms**: [ERROR] Alembic migration failed. Aborting startup. in deploy logs; Service fails to start

**CRITICAL**: Do NOT stamp Alembic. Do NOT delete migrations. Do NOT run create_all().

**Diagnosis**:
`ash
# Check what migration failed
python -m alembic history --verbose | head -10
python -m alembic current
python -m alembic heads
`

**Recovery**:
1. If multiple heads detected: python -m alembic merge heads -m "merge_heads"
2. If migration has SQL error: Fix the migration script, create new revision
3. If emergency rollback needed: python -m alembic downgrade -1
4. NEVER use lembic stamp head to bypass — it leaves schema/code out of sync

---

### Scenario 5: Celery Worker Outage (Tasks Not Processing)

**Symptoms**: Follow-ups not sending; Daily briefings not generated; SLA monitors silent

**Diagnosis**:
1. Check Render eetlelabs-celery-worker service status
2. Check Render eetlelabs-celery-beat service status ← **Must be running**

**Immediate Actions**:
1. Restart eetlelabs-celery-worker on Render
2. If Beat is down: restart eetlelabs-celery-beat
3. Check Redis connectivity from worker: Celery worker logs should show Connected to redis://...

**Recovery Verification**:
- Celery worker logs show: [celery.worker.consumer] Connected to redis://...
- Beat logs show: eat: Starting...
- Within 5 minutes, scheduled tasks should fire

---

### Scenario 6: Gemini AI Service Degradation

**Symptoms**: AI features (copilot, scoring, qualification) returning errors or falling back to defaults

**Platform Response** (already implemented):
- Gemini service failures trigger graceful fallback to rule-based scoring
- CRM core functionality (leads, contacts, deals) continues to work
- AI features display "AI temporarily unavailable" messages

**Monitoring**:
- Check Gemini API status: https://status.cloud.google.com
- Check API logs for [Gemini] or [AI] error patterns

**Actions**:
- No immediate action required if fallback is active
- Alert via ALERT_SLACK_WEBHOOK_URL if configured
- AI features auto-recover when Gemini service restores

---

### Scenario 7: Brevo SMTP Email Failure

**Symptoms**: Onboarding emails not sending; Password reset emails not delivered

**Diagnosis**:
- Check Brevo dashboard: https://app.brevo.com/email/dashboard
- Check API logs for [SMTP] error patterns

**Immediate Actions**:
1. Verify SMTP credentials: SMTP_USER and SMTP_PASSWORD still valid
2. Check Brevo sending limits (free tier: 300 emails/day)
3. If credentials expired: rotate in Render environment variables

---

## Data Backup & Restoration

### Supabase Automated Backups
- **Free tier**: Daily backups, 7-day retention
- **Pro tier**: Point-in-time recovery, 30-day retention
- Backup access: Supabase Dashboard → Settings → Backups

### Manual Database Backup
`ash
pg_dump "postgresql://postgres.iymirycycichjbllucsr:[PASSWORD]@aws-0-ap-south-1.pooler.supabase.com:5432/postgres" \
  --no-owner --no-acl -F c \
  -f backup_.dump
`

### Database Restoration
`ash
pg_restore -d "postgresql://..." --clean --no-owner backup_YYYYMMDD_HHMMSS.dump
# After restoration, verify Alembic is at correct head:
python -m alembic current
`

---

## Contact & Escalation

| Level | Contact | When |
|-------|---------|------|
| L1 | On-call engineer | Any outage > 5 min |
| L2 | Lead engineer | Database corruption, security incident |
| L3 | Platform: Render Support | Platform-level failures |
| L3 | Supabase Support | Database unavailability |
| L3 | Upstash Support | Redis unavailability |
