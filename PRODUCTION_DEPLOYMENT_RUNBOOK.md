# ==============================================================================
# PRODUCTION DEPLOYMENT RUNBOOK
# ==============================================================================
# Target: Production Service Deployment Sequence
# Enforces zero downtime, safety checks, and unambiguous operational steps.
# ==============================================================================

## Phase 1: Preflight Verification

1. **Clean Working Tree**: Ensure no uncommitted secrets, untracked development artifacts, or local test databases are staged.
   ```bash
   git status
   ```
2. **Alembic Single Head Check**: Verify migration DAG has a single terminal head.
   ```bash
   python -m alembic heads
   # Expected Output: 0024_onboarding_activation_demo (head)
   ```
3. **Infrastructure Probe**: Verify database, Redis, and SMTP reachability.
   ```bash
   python apps/api/scripts/verify_production_infra.py
   ```

---

## Phase 2: Database Backup & Snapshot

1. **Pre-Deployment Metadata Snapshot**:
   ```bash
   python scripts/backup_production_db.py --action snapshot
   ```
   - Verifies all 290 public tables and row counts.
   - Generates SHA-256 integrity hash and stores JSON in `backups/`.
2. **Supabase Cloud State Check**: Confirm automated WAL archiving and PITR status in the Supabase Dashboard.

---

## Phase 3: Build Container & Frontend Artifacts

1. **Backend Docker Build**:
   ```bash
   docker build -t beetlelabs-api:production -f apps/api/Dockerfile.prod apps/api
   ```
2. **Frontend Type Check & Production Bundle**:
   ```bash
   cd apps/web
   npx tsc --noEmit
   npm run build
   cd ../..
   ```

---

## Phase 4: Deploy Backend API

1. **Push Container to Registry**:
   - Push `beetlelabs-api:production` to cloud registry (e.g., Render / GitHub Packages / AWS ECR).
2. **Trigger Staging / Canary Release**:
   - Update API service definition in Render or container orchestrator.
   - Wait for container initialization and verify `/health/liveness` returns HTTP 200.

---

## Phase 5: Execute Database Migrations

1. **Execute Linear Upgrade**:
   ```bash
   python -m alembic upgrade head
   ```
2. **Verify Post-Migration Schema**:
   ```bash
   python scripts/backup_production_db.py --action restore-drill
   ```

---

## Phase 6: Deploy Background Workers

1. **Deploy Celery Worker Service**:
   - Spin up `beetlelabs-celery-worker` service using the newly built production image.
   - Command: `celery -A app.celery_app worker -l info -c 4`
2. **Verify Queue Subscriptions**:
   - Confirm active subscriptions to `lead_queue`, `ai_queue`, `email_queue`, etc.

---

## Phase 7: Deploy Celery Beat Scheduler

1. **Deploy Beat Service**:
   - Spin up exactly ONE instance of `beetlelabs-celery-beat`.
   - Command: `celery -A app.celery_app beat -l info`
2. **Verify Schedule Registration**:
   - Confirm scheduled tasks (e.g. `send-daily-followup-briefing`, `monitor-sla-breaches`).

---

## Phase 8: Deploy Frontend Web Application

1. **Vercel Production Deployment**:
   - Ensure environment variables are set in Vercel Project Settings (`NEXT_PUBLIC_API_URL=https://api.${DOMAIN}/api/v1`).
   - Trigger production deployment via Vercel CLI or Git push to `main`.
2. **Verify Edge Compilation**:
   - Confirm 33/33 static & dynamic routes respond with HTTP 200.

---

## Phase 9: DNS & SSL Routing Activation

1. **Configure DNS Records**:
   - Point `app.${DOMAIN}` to `cname.vercel-dns.com`.
   - Point `api.${DOMAIN}` to `<backend-app-name>.onrender.com`.
2. **Verify TLS Certificates**:
   - Confirm valid SSL/TLS certificates issued without mixed-content warnings.

---

## Phase 10: Production Smoke Test

Execute non-destructive verification:
1. Open `https://app.${DOMAIN}/login` in browser.
2. Sign in with administrative credentials.
3. Access `/dashboard`, `/dashboard/leads`, `/dashboard/properties`, `/dashboard/matching`.
4. Create test workspace, ingest test lead, verify match calculation.
5. Trigger follow-up action and confirm presence in Agent Command Center.
6. Verify `/health/readiness` on API.

---

## Phase 11: Real-Time Monitoring & Error Tracking

1. Monitor live API request rate, latency (p95 < 250ms), and 5xx error percentage (< 0.1%).
2. Monitor Celery task completion rates and Dead Letter Queue backlog.
3. Monitor Redis memory consumption and database connection pool saturation.

---

## Phase 12: Rollback Protocol (If Degradation Occurs)

1. **Frontend**: In Vercel dashboard, click "Instant Rollback" to revert to previous immutable deployment ID (< 2 mins).
2. **Backend**: Trigger Render deployment rollback to previous Docker image digest (< 5 mins).
3. **Database**: If migration introduced an irrecoverable schema defect, initiate PITR restore from the pre-deployment timestamp via Supabase Console.
