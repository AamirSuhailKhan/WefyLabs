# WEFYLABS AUTONOMOUS REVENUE OS — PHASE 5 RELEASE CANDIDATE BASELINE

**Audit Date**: 2026-10-28T13:45:00+05:30  
**Repository**: WefyLabs / BeetleLabs AI Real Estate CRM  
**Target Branch**: `level-3`  
**Current HEAD Commit**: `0383020a865fe315adfda4549f536a594fb10454`  
**Migration Revision**: `0048_schema_reconciliation_parity`  
**Auditor**: Principal Release Engineer & Application Security Lead  
**Evaluation Standard**: Phase A — Release Candidate State & Empirical Baseline

---

## 1. Executive Summary

This baseline report captures the operational, cryptographic, and source-control state of the WefyLabs release candidate prior to conducting the Phase 5 pilot dry run. Every system dependency, container process, health probe, and configuration boundary was independently verified.

All core infrastructure services are healthy, ports are bound strictly to localhost (`127.0.0.1`), outbound communication dispatch is confirmed **disabled** across both the API and worker runtimes, and the host-side database backup is verified intact and excluded from Git tracking.

---

## 2. Source Control & Working Tree State

| Property | Target / Baseline | Current Verified State | Status |
|---|---|---|---|
| **Branch** | `level-3` | `level-3` (via `git branch --show-current`) | **VERIFIED** |
| **Commit HEAD** | `0383020a865fe315adfda4549f536a594fb10454` | `0383020a865fe315adfda4549f536a594fb10454` | **VERIFIED** |
| **Working Tree Status** | Preserved uncommitted files | Working tree contains uncommitted remediation files per safety rules | **VERIFIED** |
| **Diff Hygiene** | Clean formatting | `git diff --check` exited code 0 (zero whitespace/EOF errors) | **VERIFIED** |
| **Prior Reports** | Phase 4 Deliverables (1–8) | All 8 Phase 4 documents present in `docs/audits/` and `docs/runbooks/` | **VERIFIED** |

---

## 3. Container Topology & Process Health

```powershell
docker compose ps -a
```

| Service | Container Name | Image ID | Status | Port Bindings |
|---|---|---|---|---|
| **API** | `leadscore_api` | `sha256:aee327ea299f...` | Up > 23 hours (healthy) | `127.0.0.1:8000->8000/tcp` |
| **Worker** | `leadscore_celery_worker` | `sha256:187442fb1546...` | Up > 23 hours | Local network only |
| **Beat** | `leadscore_celery_beat` | `sha256:187442fb1546...` | Up > 23 hours | Local network only |
| **Postgres** | `leadscore_postgres` | `pgvector/pgvector:pg16` | Up > 24 hours (healthy) | `127.0.0.1:5432->5432/tcp` |
| **Redis** | `leadscore_redis` | `redis:7-alpine` | Up > 24 hours (healthy) | `127.0.0.1:6379->6379/tcp` |

### Network Ingress Security
- PostgreSQL (`5432`), Redis (`6379`), and API (`8000`) are bound exclusively to the loopback interface (`127.0.0.1`).
- No service ports are bound to public network interfaces (`0.0.0.0`), preventing unintended internet accessibility.

---

## 4. Application Health & Security Telemetry

Probing the application health probe via loopback:
```bash
curl.exe -s http://127.0.0.1:8000/health
```
```json
{
  "status": "healthy",
  "service": "WefyLabs API",
  "version": "1.0.0",
  "environment": "development",
  "dependencies": {
    "database": {
      "status": "ok",
      "latency_ms": 1.75,
      "migration_head": "0048_schema_reconciliation_parity"
    },
    "redis": {
      "status": "ok",
      "latency_ms": 2.39
    },
    "gemini": {
      "status": "configured",
      "provider": "google-gemini",
      "model": "gemini-3.6-flash"
    },
    "smtp": {
      "status": "not_configured"
    }
  },
  "outbox_queue": {
    "pending": 0,
    "failed": 0,
    "dead_letter": 0
  },
  "security_metrics": {
    "AUTH_FAILURE": 0,
    "AUTHZ_FAILURE": 0,
    "RATE_LIMIT": 0,
    "INVALID_WEBHOOK": 0,
    "SUSPICIOUS_INPUT": 0,
    "TENANT_BOUNDARY_VIOLATION": 0,
    "AI_POLICY_REJECTION": 0,
    "SYSTEM_SECURITY_ERROR": 0
  }
}
```
- **Database Latency**: 1.75 ms
- **Redis Latency**: 2.39 ms
- **Migration Head**: `0048_schema_reconciliation_parity`
- **Security Boundary Violations**: 0

---

## 5. Effective Outbound Messaging Configuration

The runtime circuit breaker was verified directly inside the running container processes:
- `leadscore_api`: `FOLLOWUP_HUB_DISPATCH_ENABLED = False`
- `leadscore_celery_worker`: `FOLLOWUP_HUB_DISPATCH_ENABLED = False`
- Worker Runtime Log:
  ```
  [FollowUpDispatch] FOLLOWUP_HUB_DISPATCH_ENABLED is false — no follow-up executions were dispatched.
  ```
No external WhatsApp messages or emails can be emitted by the current runtime.

---

## 6. Backup Storage & Git Ignore Status

- **Host Backup File**: `./backups/leadscore_backup_20261028.dump`
- **File Existence**: Confirmed (`Test-Path` returned `True`).
- **File Size**: `1,492,352 bytes` (~1.49 MB)
- **SHA-256 Checksum**: `C28955F440B176285B96556009FD3E201A9B1B1F98CA26996673582FE4A1D9C6`
- **Git Exclusion**: `.gitignore` contains `backups/` and `*.dump`. `git status --short ./backups/` returns empty, confirming complete exclusion from git staging.

---

## 7. Baseline Certification

The release candidate baseline is confirmed stable, healthy, and securely bounded for Phase 5 dry-run execution.
