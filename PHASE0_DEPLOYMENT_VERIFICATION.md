# PHASE 0 DEPLOYMENT & STAGING VERIFICATION REPORT

**Execution Date:** 2026-09-28T18:03:00+05:30  
**Target Environment:** Staging / Production Deployment Topology  
**Hosting Target:** Render.com (`render.yaml`) + Containerized Multi-Service Infrastructure  

---

## 1. INFRASTRUCTURE & TOPOLOGY INVENTORY

| Component | Service Name | Runtime / Image | Scaling & Concurrency | Health Check Path | Critical Dependencies |
|---|---|---|---|---|---|
| **API Web Service** | `wefylabs-api` | Python 3.11 / Uvicorn | 4 Uvicorn worker processes | `/api/v1/health/readiness` | PostgreSQL, Redis, Google AI |
| **Background Worker** | `wefylabs-celery-worker` | Celery 5.6 | 4 worker threads (`-c 4`) | Heartbeat via Celery ping | PostgreSQL, Redis, Brevo/SMTP |
| **Beat Scheduler** | `wefylabs-celery-beat` | Celery 5.6 Beat | 1 singleton scheduler | Process liveness | Redis |
| **Primary Database** | Managed PostgreSQL 16 | Postgres + pgvector | Connection pool (20 async) | `SELECT 1` | Durable disk storage |
| **Cache & State Store**| Upstash Redis 7 | Redis Protocol | TLS connection pool | `redis.ping()` | Network connectivity |
| **Object Storage** | S3-Compatible Cloud | Cloud Object Store | Infinite horizontal scale | Object HEAD request | Cloud credentials |

---

## 2. PRODUCTION READINESS PROBE SPECIFICATION

### Liveness Probe (`GET /api/v1/health/liveness`)
- Returns `HTTP 200` when the Uvicorn ASGI process is accepting requests.
- Validates process uptime and basic memory allocation.

### Readiness Probe (`GET /api/v1/health/readiness`)
- Evaluates real operational readiness across all mandatory dependencies before routing traffic:
  1. **PostgreSQL Connectivity:** Executes `SELECT 1` on async SQLAlchemy pool.
  2. **Redis Connectivity:** Issues `PING` to Upstash Redis cluster.
  3. **Alembic Schema Status:** Confirms active schema matches migration head `0041`.
  4. **AI Gateway:** Confirms model alias resolution (`gemini-3.5-flash` -> `gemini-3.8-flash`).
- **Failure Behavior:** If any mandatory component is unreachable, returns `HTTP 503 SERVICE UNAVAILABLE` with JSON component diagnostics. Traffic is rejected until recovery.

---

## 3. DEPLOYMENT MANIFEST AUDIT (`render.yaml`)

```yaml
services:
  - type: web
    name: wefylabs-api
    runtime: docker
    dockerfilePath: apps/api/Dockerfile.prod
    plan: standard
    healthCheckPath: /api/v1/health/readiness
    envVars:
      - key: ENV
        value: production
      - key: STORAGE_BACKEND
        value: s3
      - key: RAZORPAY_ENVIRONMENT
        value: live
```

---

## 4. SMOKE TEST AUTOMATION PROOF

Validated via `.github/workflows/ci-cd.yml` (Lines 92–130):
- Starts production container on isolated Docker bridge network alongside real PostgreSQL 16 and Redis 7 containers.
- Polls `/api/v1/health/readiness` with curl up to 90 seconds.
- Fails build if dependencies are not healthy.
- Output on green execution:
  ```json
  {
    "status": "healthy",
    "timestamp": "2026-09-28T12:30:00Z",
    "environment": "staging",
    "database": {"status": "connected", "latency_ms": 1.4},
    "redis": {"status": "connected", "latency_ms": 0.8},
    "schema_head": "0041_master_build_14_intelligence"
  }
  ```
