# WEFYLABS AUTONOMOUS REVENUE OS — PILOT OPERATIONS & RECOVERY RUNBOOK

**Target Environment**: Docker Compose / Linux Containers  
**Audience**: On-Call Engineers, Site Reliability Engineers, Pilot Operations Leads  
**Version**: 1.0.0  
**Effective Date**: 2026-10-27  

---

## 1. System Inventory & Architecture Map

| Service Name | Container Name | Port (Host:Internal) | Healthcheck | Primary Responsibility |
|---|---|---|---|---|
| `api` | `leadscore_api` | `127.0.0.1:8000:8000` | `GET /health` | FastAPI REST API, Auth, Ingestion |
| `celery_worker` | `leadscore_celery_worker` | Internal | None | Asynchronous task processor (8 forks) |
| `celery_beat` | `leadscore_celery_beat` | Internal | None | Periodic cron & interval dispatcher |
| `postgres` | `leadscore_postgres` | `127.0.0.1:5432:5432` | `pg_isready` | PostgreSQL 16 + pgvector storage |
| `redis` | `leadscore_redis` | `127.0.0.1:6379:6379` | `redis-cli ping` | Celery broker & rate limiter cache |

---

## 2. Standard Operating Procedures

### A. Health & Status Verification
Check all service health:
```bash
docker compose ps -a
```
Query comprehensive system health via API:
```bash
curl -s http://127.0.0.1:8000/health | jq .
```
Expected: `status: healthy`, `database.status: ok`, `redis.status: ok`.

### B. Live Log Inspection
Inspect recent API logs:
```bash
docker compose logs -f --tail=100 api
```
Inspect Celery worker logs:
```bash
docker compose logs -f --tail=100 celery_worker
```
Inspect Celery beat schedules:
```bash
docker compose logs -f --tail=100 celery_beat
```

### C. Graceful Restart Procedures
Restart worker and beat without restarting database:
```bash
docker compose restart celery_worker celery_beat
```
Restart API without database restart:
```bash
docker compose restart api
```

---

## 3. Disaster Recovery & Emergency Procedures

### A. Database Backup Procedure (Non-Destructive)
Take a live hot dump of the PostgreSQL database:
```bash
docker compose exec postgres pg_dump -U postgres -d leadscore -Fc -f /var/lib/postgresql/data/leadscore_hot_backup.dump
```
Verify the dump exists on the host data volume:
```bash
docker compose exec postgres ls -lh /var/lib/postgresql/data/leadscore_hot_backup.dump
```

### B. Database Restore to Staging / Recovery DB
Create disposable recovery database and restore:
```bash
docker compose exec postgres psql -U postgres -c "CREATE DATABASE leadscore_recovery;"
docker compose exec postgres pg_restore -U postgres -d leadscore_recovery /var/lib/postgresql/data/leadscore_hot_backup.dump
```

### C. Worker Lockup / Event Loop Recovery
If Celery worker exhibits any unexpected thread hangs or pool degradation:
```bash
# 1. Stop worker gracefully
docker compose stop celery_worker

# 2. Clear stale Celery keys in Redis (preserve business cache)
docker compose exec redis redis-cli -n 0 keys "celery-task-meta-*" | xargs -r docker compose exec -T redis redis-cli -n 0 del

# 3. Start worker
docker compose start celery_worker
```

### D. Emergency Pilot Abort & Dispatch Halting
If unexpected duplicate outbound messages or anomalous activity occurs during the pilot:
```bash
# Immediately halt background dispatches without killing the database or API:
docker compose stop celery_worker celery_beat

# Verify API is still answering health checks for read-only broker access:
curl -s http://127.0.0.1:8000/health
```

> [!CAUTION]
> **CRITICAL DATA PRESERVATION RULE**:
> NEVER execute `docker compose down -v` or `docker volume rm`.
> The PostgreSQL database volume `crmrealstate_postgres_data` contains persistent pilot data.
