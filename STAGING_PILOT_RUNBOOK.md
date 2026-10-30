# WefyLabs — Staging Deployment & Controlled Pilot Runbook

**Target Project:** WefyLabs AI-Native Real Estate Revenue Operating System  
**Release Gate Status:** **CONTROLLED-PILOT CANDIDATE**  
**Authoritative Migration Head:** `0047_webhook_event_claims`  
**API Prefix:** `/api/v1`  
**Execution Autonomy Level:** Stage 1 (Shadow Mode — Mandatory Human Confirmation)

---

## 1. Architecture & Service Topology

```
                   ┌──────────────────────────────────┐
                   │       Next.js 15 Frontend        │
                   │      (Port 3000 / Standalone)    │
                   └─────────────────┬────────────────┘
                                     │ /api/v1 (Proxied)
                                     ▼
                   ┌──────────────────────────────────┐
                   │       FastAPI Core Engine        │
                   │           (Port 8000)            │
                   └───────┬─────────┬─────────┬──────┘
                           │         │         │
          ┌────────────────┘         │         └───────────────┐
          ▼                          ▼                         ▼
┌──────────────────┐       ┌──────────────────┐      ┌──────────────────┐
│  PostgreSQL 16+  │       │     Redis 7+     │      │  Celery Workers  │
│   with pgvector  │       │  Broker & Lock   │      │   & Celery Beat  │
└──────────────────┘       └──────────────────┘      └──────────────────┘
```

---

## 2. Environment Variable Configuration Checklist

| Variable Name | Purpose | Mandatory? | Safe Default / Pattern |
| :--- | :--- | :---: | :--- |
| `ENV` | Execution environment mode | **YES** | `staging` / `production` |
| `PORT` | API listen port | **YES** | `8000` |
| `DATABASE_URL` | Async PostgreSQL connection string | **YES** | `postgresql+asyncpg://<user>:<pwd>@<host>:5432/<db>` |
| `REDIS_URL` | Redis URI for Celery & rate limits | **YES** | `redis://<host>:6379/0` (or `rediss://...`) |
| `SECRET_KEY` | HMAC token signing secret | **YES** | Minimum 64-character high-entropy hex string |
| `SUPABASE_JWT_SECRET` | Supabase auth token verification | **YES** | Provided by Supabase project dashboard |
| `GEMINI_API_KEY` | Google Gemini LLM API key | **YES** | High-quota Google AI Studio / Vertex key |
| `GEMINI_MODEL` | Canonical LLM model alias | NO | `gemini-3.5-flash` (active Google Gemini production model) |
| `WHATSAPP_ACCESS_TOKEN` | Meta WhatsApp Cloud API access token | CONDITIONAL | Required for live WhatsApp outbound messaging |
| `WHATSAPP_PHONE_NUMBER_ID`| Meta registered phone ID | CONDITIONAL | Required for live WhatsApp messaging |
| `WHATSAPP_APP_SECRET` | Meta App Secret for webhook HMAC-SHA256 | CONDITIONAL | **Fail-closed:** if unset, webhook returns 503 |
| `WHATSAPP_VERIFY_TOKEN` | Meta Webhook GET challenge token | CONDITIONAL | High-entropy shared secret |
| `RAZORPAY_KEY_ID` | Razorpay merchant key ID | CONDITIONAL | `rzp_test_...` (staging) or `rzp_live_...` |
| `RAZORPAY_KEY_SECRET` | Razorpay API key secret | CONDITIONAL | Required for signature verification |
| `RAZORPAY_WEBHOOK_SECRET`| Razorpay payment webhook secret | CONDITIONAL | Required for payment capture webhook auth |
| `SMTP_HOST` | Transactional email provider host | CONDITIONAL | e.g. `smtp-relay.brevo.com` |
| `SMTP_PORT` | Transactional email provider port | CONDITIONAL | `587` |
| `SMTP_USERNAME` | SMTP login user | CONDITIONAL | e.g. `b6a4de001@smtp-brevo.com` |
| `SMTP_PASSWORD` | SMTP password / API token | CONDITIONAL | Brevo SMTP secret key |
| `KNOWLEDGE_OCR_PROVIDER` | PDF / brochure OCR backend | NO | `tesseract` |

> [!CAUTION]
> Never set placeholder or mock strings (`sk_test_placeholder`, `wa_secret_placeholder`) in production environments. Production startup fails closed when mandatory secrets are detected as defaults.

---

## 3. Database Migration & Initialization Sequences

The WefyLabs database architecture reconciles an initial 215-table stamp-only baseline (`9999_production_baseline`) merged with enterprise foundation heads into a linear migration graph ending at authoritative head `0047_webhook_event_claims`.

### Procedure A: Empty Database Initialization (Fresh Staging / Disposable DB)

For a brand-new database instance with no pre-existing tables:

1. **Provision PostgreSQL Extensions:**
   Execute in the target PostgreSQL database before running application scripts:
   ```sql
   CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
   CREATE EXTENSION IF NOT EXISTS "pgcrypto";
   CREATE EXTENSION IF NOT EXISTS "vector";
   ```

2. **Execute Certified Async Bootstrap Script:**
   The application provides a standalone, certified initialization script (`apps/api/scripts/init_db.py`) that loads all 410 ORM models, creates tables asynchronously via valid SQLAlchemy context manager, applies pgvector HNSW index and migration-only seeds, and stamps Alembic at authoritative head `0047_webhook_event_claims`.

   **Production Immutability Policy:**
   The generic bootstrap procedure strictly refuses to mutate production databases under any circumstances:
   - Generic initialization (`Base.metadata.create_all`) is strictly blocked when `ENV` is `production` or `prod`.
   - No convenient CLI flag bypass exists. Production database changes must strictly use reviewed Alembic migrations (`python -m alembic upgrade head`).
   - Ambiguous or unrecognized environments (`ENV=""`, unknown values) or invalid schema names are rejected immediately.
   - Database URLs are sanitized in logs to ensure zero secret exposure.

   **POSIX Shell (Linux / macOS / Docker):**
   ```bash
   cd apps/api
   python scripts/init_db.py
   ```

   **Windows PowerShell:**
   ```powershell
   Set-Location apps/api
   python scripts/init_db.py
   ```

   *(Optional)* To bootstrap into an isolated staging schema:
   ```bash
   python scripts/init_db.py --schema staging_pilot
   ```
   To route the FastAPI application to this schema at runtime:
   ```bash
   export DB_SCHEMA=staging_pilot
   ```

3. **Verify Bootstrap Parity (Enforces Read-Only Safety):**
   The `--check-only` flag runs with `SET TRANSACTION READ ONLY`, guaranteeing zero database mutations during schema verification in any environment (including production):
   ```bash
   python scripts/init_db.py --check-only
   python -m alembic current
   # Expected Output: 0047_webhook_event_claims (head)
   ```

---

### Procedure B: Existing Database Incremental Migration

For existing databases that have already been stamped at an earlier Alembic revision:

1. **Pre-Migration Safety Backup:**
   Always capture a database snapshot before running schema upgrades:

   **POSIX Shell:**
   ```bash
   pg_dump -h $PGHOST -U $PGUSER -d $PGDATABASE -F c -b -v -f "pre_migration_backup_$(date +%Y%m%d_%H%M%S).dump"
   ```

   **Windows PowerShell:**
   ```powershell
   $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
   pg_dump -h $env:PGHOST -U $env:PGUSER -d $env:PGDATABASE -F c -b -v -f "pre_migration_backup_${timestamp}.dump"
   ```

2. **Run Incremental Alembic Upgrade:**
   ```bash
   cd apps/api
   python -m alembic upgrade head
   ```

3. **Verify Final Migration State:**
   ```bash
   python -m alembic current
   # Expected Output: 0047_webhook_event_claims (head)
   ```

---

### Procedure C: Recovery from a Failed Upgrade

If an upgrade fails mid-migration:

1. **Identify Failed Migration Revision:**
   ```bash
   python -m alembic current
   ```

2. **Inspect Migration Failure in Logs:**
   Examine terminal output or Postgres logs to identify the failing DDL statement. PostgreSQL transactional DDL rolls back automatically for individual migrations that fail inside `context.begin_transaction()`.

3. **Restoring to Clean Revision State:**
   If the database was partially upgraded or left in an inconsistent state:
   - Identify the last known good revision (e.g. `0046_broker_google_subject`).
   - If DDL was rolled back by Postgres:
     ```bash
     python -m alembic stamp <last_good_revision>
     ```
   - If non-transactional changes or schema corruption occurred, restore the pre-migration snapshot:

     **POSIX Shell:**
     ```bash
     pg_restore -h $PGHOST -U $PGUSER -d $PGDATABASE --clean --if-exists "pre_migration_backup_<timestamp>.dump"
     ```

     **Windows PowerShell:**
     ```powershell
     pg_restore -h $env:PGHOST -U $env:PGUSER -d $env:PGDATABASE --clean --if-exists "pre_migration_backup_<timestamp>.dump"
     ```

4. **Verify Schema Drift with Alembic Check:**
   ```bash
   python -m alembic check
   ```

---

## 4. Staging Startup & Verification Order

Execute service startup strictly in the following order:

1. **PostgreSQL 16+ (pgvector):**
   - Healthcheck: `pg_isready -U postgres -d leadscore`
2. **Redis 7+:**
   - Healthcheck: `redis-cli ping` -> `PONG`
3. **Database Migrations:**
   - Execute Step 3.2 above (or bootstrap into isolated schema via `DB_SCHEMA=staging_pilot`).
4. **Celery Worker:**
   ```bash
   celery -A app.celery_app.celery_app worker --loglevel=info -c 4 -Q default,high_priority,communications,scheduled
   ```
5. **Celery Beat (Scheduler):**
   ```bash
   celery -A app.celery_app.celery_app beat --loglevel=info
   ```
6. **FastAPI Application Server:**
   ```bash
   cd apps/api
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
   ```
7. **Next.js Web Client (Standalone Server):**
   Due to monorepo root tracing, Next.js standalone output is structured at `apps/web/.next/standalone/apps/web/server.js`:
   ```bash
   cd apps/web/.next/standalone
   PORT=3000 node apps/web/server.js
   ```

8. **Live HTTP Smoke Verification:**
   Execute the automated 12-flow TCP validation script:
   ```bash
   python scratch/validate_http_flows_p12.py
   ```

### Docker Daemon Prerequisite Notice
When deploying via `docker compose up`:
- **Requirement:** Docker Desktop must be running with the WSL2 backend enabled.
- **Limitation:** In non-interactive Windows services or headless agent environments, Docker Desktop cannot initialize its background pipe (`//./pipe/dockerDesktopLinuxEngine`).
- **Prerequisite Action:** The host operator must log in to the interactive Windows desktop session and launch `Docker Desktop.exe`.

---

## 5. Health Probes & Monitoring Endpoints

| Endpoint | Method | Expected Status | Purpose |
| :--- | :---: | :---: | :--- |
| `/health/liveness` | `GET` | `200 OK` | Container orchestrator liveness probe |
| `/health/readiness` | `GET` | `200 OK` | Verifies DB and Redis connectivity |
| `/health/startup` | `GET` | `200 OK` | Startup dependency initialization check |
| `/health/dependencies` | `GET` | `200 OK` | Status of PostgreSQL, Redis, AI, and WhatsApp |
| `/metrics` | `GET` | `200 OK` | Prometheus scrape endpoint (text/plain) |
| `/v1/metrics` | `GET` | `200 OK` (Auth) | Super-admin protected Prometheus exposition |

---

## 6. Controlled Broker Pilot Execution Protocol

During the initial 14-day broker pilot:
1. **Autonomy Stage:** Locked to **Stage 1 (Shadow Mode)**.
2. **Outbound Messaging Rule:** No automated WhatsApp message may be dispatched to a buyer without an authorized broker clicking **Approve** in the Command Center or Leads inbox.
3. **Pilot SKU Lifecycle:**
   - Catalog plan: `pilot` (₹4,999 / 14-day duration, 499,900 paise).
   - Checkout is a single upfront payment; access is managed internally for 14 calendar days.
   - On Day 12, an in-app renewal/upgrade banner prompts conversion to `starter` or `professional`.
   - On Day 14, pilot access expires if not upgraded; leads and historical conversations remain read-only.
4. **Portal Ingestion Setup:**
   - Housing.com / MagicBricks: Set partner webhook destination to:
     `https://<staging-api>/api/v1/lead-acquisition/webhooks/{housing|magicbricks}`
   - Incoming payloads are normalized through `UniversalLeadNormalizer`.
5. **PDF Brochure Ingestion:**
   - Upload brochure to `POST /api/v1/inventory/brochure/extract-candidate-inventory`.
   - Broker must review and confirm candidate units in the UI before inventory becomes active.

---

## 7. Incident Response & Rollback Procedures

### Emergency Autonomous Execution Pause
If any autonomous worker behaves unexpectedly or attempts unapproved actions:
```bash
# Emergency kill-switch: Pause all background execution queues
python -c "
from app.modules.autonomous_loop.safety import trigger_emergency_pause
trigger_emergency_pause('Operator manual intervention')
"
```

### Staging Rollback Procedure
If a breaking regression occurs upon deployment:
1. **Stop Application Containers:**
   `docker compose stop api celery_worker celery_beat`
2. **Revert Application Image / Git Revision:**
   `git checkout <last-known-good-commit>`
3. **Database Migration Downgrade:**
   If the migration introduced incompatible tables or columns, downgrade to the prior revision:
   ```bash
   python -m alembic downgrade -1
   ```
4. **Restart Services in Sequence:**
   Follow Section 4 startup order.

---

## 8. Phase 14 Operational Verification & Release Invariants

### 8.1 Google Gemini Model Aliasing & Fallback Policy
- **Active Canonical Model:** `gemini-3.5-flash` is the default Google Gemini production model.
- **Model Aliases:**
  - `gemini-2.0-flash` -> `gemini-2.5-flash`
  - `gemini-3.1-pro` -> `gemini-2.5-pro`
  - Canonical choices (`gemini-3.5-flash`, `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3.8-flash`, `gemini-3.5-flash-lite`) pass through directly without modification.
- **Provider Failure Normalization:**
  - Token-exhaustion, empty response, 429 rate limit, 401 unauthorized, and timeouts normalize to structured `LLMResponse(success=False, error=...)` instead of crashing callers.
- **Network Isolation Invariant:**
  - In `ENV=testing`, live outbound network requests to Google Gemini are strictly prohibited unless `ALLOW_LIVE_AI_CALLS_IN_TESTS=1` is explicitly set.

### 8.2 WhatsApp Webhook Cryptographic Security & Ingress Invariants
- **Fail-Closed Secret Guard:** If `WHATSAPP_APP_SECRET` is unset on the server, incoming webhook POST requests fail closed with HTTP 503 Service Unavailable.
- **Raw-Byte HMAC Verification:** Signatures must match HMAC-SHA256 computed strictly over exact raw request body bytes.
- **Signature Failure Contract:** Missing, forged, tampered, or malformed signature headers return HTTP 401 Unauthorized.
- **Deduplication Invariant:** Duplicate event deliveries (e.g. repeated status receipts) are idempotently deduplicated and suppressed without duplicate downstream business actions.
- **Outbound Outreach Disabled:** Outbound buyer messaging is completely disabled until live credentials, consent verification, and Stage-1 human approval are configured.

### 8.3 Docker Desktop Host Startup Requirement
- When running in host Windows environments where Docker Desktop is not running:
  - Docker daemon named pipe `//./pipe/dockerDesktopLinuxEngine` is offline.
  - Interactive operator desktop launch required:
    ```powershell
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    ```
  - Application runtime and image build gates remain `BLOCKED` until the host Docker engine is online.

