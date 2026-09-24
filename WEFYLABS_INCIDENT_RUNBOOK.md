# WEFYLABS SITE RELIABILITY & INCIDENT RUNBOOK
# Operational Playbooks for Production Incidents

---

## 1. Incident Severity Definitions

- **SEV-1 (Critical)**: Total API outage, database loss, data corruption, or cross-tenant data leak. Immediate all-hands response (<15m).
- **SEV-2 (Major)**: Partial degradation, AI provider outage, background task queue backlog exceeding 5,000 tasks, or external communication failure. Response (<1h).
- **SEV-3 (Minor)**: Non-blocking performance anomaly, isolated webhook retry failure, or single background task crash. Response (<4h).

---

## 2. Playbook A: Database Connection Pool Exhaustion

### Symptoms
- HTTP 500 errors on API routes with `asyncpg.exceptions.TooManyConnectionsError` or `TimeoutError: QueuePool limit of size 10 overflow 20 reached`.
- `/health/ready` probe returning 503.

### Diagnosis
```bash
# Check current connection count on PostgreSQL
SELECT count(*) FROM pg_stat_activity WHERE datname = 'leadscore';
# Inspect active long-running queries (>10s)
SELECT pid, now() - pg_stat_activity.query_start AS duration, query 
FROM pg_stat_activity 
WHERE (now() - pg_stat_activity.query_start) > interval '10 seconds' 
  AND state != 'idle';
```

### Remediation
1. **Terminate runaway queries**:
   ```sql
   SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE duration > interval '30 seconds';
   ```
2. **Verify connection recycling**: `apps/api/app/database.py` enforces `pool_recycle=1800` and `pool_pre_ping=True`.
3. If PgBouncer is in front of database, restart PgBouncer pooler or scale pool size to 60 connections.

---

## 3. Playbook B: Redis Outage / Interruption

### Symptoms
- Rate limiting warnings in logs: `[RateLimiter] Redis unavailable — falling back to in-memory rate limiting`.
- Celery tasks stalled or failing to dequeue.

### Built-in System Behavior
- **FastAPI HTTP Traffic**: Completely unaffected! Multi-tier rate limiting and distributed locks gracefully degrade to thread-safe in-memory implementations.
- **Worker Queues**: Background task execution pauses until Redis reconnects.

### Remediation
1. Verify Upstash/Redis connection:
   ```bash
   python -c "from app.common.redis.rate_limiter import _get_redis; print(_get_redis().ping())"
   ```
2. Check network / DNS resolution to Redis endpoint.
3. If Redis credentials were rotated, update `REDIS_URL` in `.env` and restart API and Celery workers.

---

## 4. Playbook C: Celery Queue Backlog & Worker Starvation

### Symptoms
- Follow-ups or notifications delayed by >15 minutes.
- `outbox_events` table contains accumulated rows with status `PENDING`.

### Diagnosis
```bash
# Inspect queue lengths via Celery inspect
celery -A app.celery_app inspect active
celery -A app.celery_app inspect reserved
```

### Remediation
1. Scale up Celery worker concurrency:
   ```bash
   celery -A app.celery_app worker -l INFO -c 8 --queues=lead_queue,webhook_queue,ai_queue
   ```
2. Inspect slow tasks: If heavy AI tasks are blocking worker threads, verify they are routed to the dedicated `ai_queue` as configured in `celery_app.py`.

---

## 5. Playbook D: AI Provider (Gemini) Outage or Latency Spike

### Symptoms
- Response latencies on AI endpoints exceeding 10 seconds.
- `AIGovernor` warnings in logs: `[AIGovernor] Upstream AI failure #N`.

### Built-in System Behavior
- **Circuit Breaker**: Trips automatically after 5 consecutive failures, fast-failing subsequent calls to avoid thread pool exhaustion.
- **Graceful CRM Degradation**: CRM predictive intelligence and customer 360 automatically fall back to deterministic heuristics (`degraded_surface`), ensuring customer CRM screens never hang or show blank errors!

### Remediation
1. Check Google Gemini status dashboard: `https://status.cloud.google.com/`
2. If temporary quota exhaustion, adjust token limits or verify billing account.
3. Once upstream recovers, `AIGovernor` automatically moves to `HALF_OPEN` and resets to `CLOSED` after the first successful canary call.

---
_Status: PRODUCTION OPERATIONAL RUNBOOK ACTIVE._
