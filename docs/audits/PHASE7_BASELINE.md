# WEFYLABS PHASE 7 — BASELINE ENVIRONMENT & AUDITED STATE AUDIT

**Project:** WefyLabs Autonomous Revenue OS / AI Real Estate CRM  
**Branch:** `level-3`  
**Base Commit:** `0383020a865fe315adfda4549f536a594fb10454`  
**Database Migration Head:** `0048_schema_reconciliation_parity`  
**Primary Engine:** FastAPI / SQLAlchemy Async / PostgreSQL 16 (pgvector) / Redis 7 / Celery 5.3  
**Audit Date:** 2026-10-28  

---

## 1. Executive Summary

Phase 7 establishes concrete, verifiable CI/CD safety gates, automated runtime database isolation guards, regression test coverage, and release-candidate readiness following the forensic investigation of Phase 6.

All investigative and verification operations in Phase 7 were conducted under a **strict read-only safety lock** on the live database (`leadscore`). Zero mutations, schema changes, updates, or deletions occurred against `leadscore`.

---

## 2. Source Control & Repository State

- **Active Branch:** `level-3`
- **Audited Commit:** `0383020a865fe315adfda4549f536a594fb10454`
- **Working Tree Integrity:** Preserved all pre-existing user modifications, untracked files, and local configuration branches.
- **Git Safety:** No forced resets (`git reset --hard`), file cleans (`git clean -fd`), or unauthorized remote pushes were performed.
- **Merge & Whitespace Integrity:** Verified clean with `git diff --check`.

---

## 3. Container & Infrastructure Topology

| Service Container | Image | Bind Address / Port | Health Status | Role |
| :--- | :--- | :--- | :--- | :--- |
| `leadscore_postgres` | `pgvector/pgvector:pg16` | `127.0.0.1:5432` | Healthy (pg_isready 0) | Shared live DB & isolated test DB host |
| `leadscore_redis` | `redis:7-alpine` | `127.0.0.1:6379` | Healthy (redis-cli ping PONG) | Celery message broker & idempotency store |
| `leadscore_api` | `wefylabs-api:latest` | `127.0.0.1:8000` | Configuration Verified | FastAPI REST API engine |
| `leadscore_celery_worker`| `wefylabs-api:latest` | Host Network (Internal) | Configuration Verified | Celery background task worker |
| `leadscore_celery_beat` | `wefylabs-api:latest` | Host Network (Internal) | Configuration Verified | Celery periodic scheduler |

### Public Port Exposure Audit
- **PostgreSQL 5432:** Binds exclusively to localhost loopback `127.0.0.1:5432:5432`. No public network or `0.0.0.0` binding.
- **Redis 6379:** Binds exclusively to localhost loopback `127.0.0.1:6379:6379`. Protected from external access.
- **FastAPI 8000:** Binds exclusively to `127.0.0.1:8000:8000`.

---

## 4. PostgreSQL Database Inventory & Schema Parity

The PostgreSQL container hosts three segregated database instances:

1. **`leadscore` (Live Application Database):**
   - **Status:** **STRICTLY READ-ONLY FOR PHASE 7**.
   - **Migration Revision:** `0048_schema_reconciliation_parity`
   - **Total Tables:** 411 tables (all ORM models registered).
   - **Row Counts:** Verified invariant (Leads: 4, Organizations: 7, Brokers: 8, Memberships: 7).
   - **Extensions:** `pgcrypto`, `uuid-ossp`, `vector` installed and active.

2. **`leadscore_verify_phase6` (Forensic Verification Database):**
   - **Status:** Static verification restore from `./backups/leadscore_backup_20261028.dump`.
   - **Migration Revision:** `0048_schema_reconciliation_parity`
   - **Role:** Preserved forensic baseline for backup-to-live parity verification.

3. **`leadscore_test_acceptance` (Isolated Acceptance Test Database):**
   - **Status:** Dedicated isolated test database with full 411-table schema and pgvector indexes.
   - **Migration Revision:** `0048_schema_reconciliation_parity`
   - **Role:** Destination for all synthetic acceptance runs, IDOR checks, and idempotence evaluations.

---

## 5. Security & Invariant Baseline

1. **Gemini Credential Protection:**
   - Configuration remains unchanged per user instructions.
   - Credential value was not printed, rotated, revoked, modified, or included in any report, artifact, or log.
2. **Outbound Dispatch Lock:**
   - `FOLLOWUP_HUB_DISPATCH_ENABLED = False`
   - `WHATSAPP_ENABLED = False`
   - `PILOT_MODE = RECOMMEND_ONLY`
   - External APIs (Meta WhatsApp Cloud API, SendGrid/SMTP, Razorpay Live) remain inert.

