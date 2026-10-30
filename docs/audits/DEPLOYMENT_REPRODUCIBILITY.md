# WEFYLABS AUTONOMOUS REVENUE OS — DEPLOYMENT & DOCKER REPRODUCIBILITY AUDIT

**Audit Date**: 2026-10-27T15:59:00Z  
**Target Infrastructure**: Docker Compose / Linux Debian Containers  
**Auditor**: Infrastructure & DevOps Release Engineer  
**Status**: `VERIFIED REPRODUCIBLE`

---

## 1. Container & Image Architecture

All application services share a unified, reproducible Python 3.11 container environment:
- **`leadscore_api`**: FastAPI HTTP application served via Uvicorn on port 8000.
- **`leadscore_celery_worker`**: Celery worker consuming 26 domain queues across 8 child processes.
- **`leadscore_celery_beat`**: Persistent task scheduler.
- **`leadscore_postgres`**: PostgreSQL 16 with pgvector extension.
- **`leadscore_redis`**: Redis 7 Alpine cache and task broker.

---

## 2. Image Build & Provenance

- **Base Image**: Linux Debian Bookworm (`python:3.11.17`).
- **Dependency Management**: Locked via `poetry.lock` (278 KB) to guarantee immutable dependency hashes.
- **Build Reproducibility**:
  - `docker compose build api celery_worker celery_beat` executes with clean layer provenance.
  - Source directories `app`, `alembic`, and `alembic.ini` are copied at build time.
  - Runtime code modifications require image rebuilds rather than ad-hoc `docker cp` injection.

---

## 3. Network Isolation & Port Security

- **Internal Bridge Network**: All inter-service communication (`api -> postgres`, `worker -> redis`, etc.) occurs on private bridge network `crmrealstate_default`.
- **Host Port Binding**: Only the API port (`127.0.0.1:8000`) is bound to the loopback interface on the host. PostgreSQL (5432) and Redis (6379) are not exposed to public interfaces.
- **Production Proxy Requirement**: In internet-facing production, traffic to port 8000 must terminate at an upstream TLS reverse proxy (Nginx / Cloudflare) with HTTPS enforcement.

---

## 4. Health Checks & High Availability

- **API Health Check**: Evaluates `/health` via curl every 30s (`interval: 30s, timeout: 10s, retries: 3`).
- **Postgres Health Check**: `pg_isready -U postgres -d leadscore` verifying database socket readiness.
- **Redis Health Check**: `redis-cli ping` verifying broker responsiveness.
- **Restart Policy**: `unless-stopped` applied to all containers to ensure automatic recovery after host reboot.
