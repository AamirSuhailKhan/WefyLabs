# WEFYLABS PHASE 7 — INTERNAL PILOT READINESS & OPERATIONAL RUNBOOK

**Project:** WefyLabs Autonomous Revenue OS / AI Real Estate CRM  
**Target Release:** Restricted Internal Pilot (`RC-PHASE7-INTERNAL-01`)  
**Operational Posture:** Outbound Inert / Recommendation Only / Human-in-the-Loop  
**Target Branch:** `level-3`  
**Runbook Date:** 2026-10-28  

---

## 1. Pilot Scope & Safety Boundaries

The internal restricted pilot is designed for controlled validation by authorized internal personnel under strict safety boundaries:

1. **Mode of Operation:** `PILOT_MODE = RECOMMEND_ONLY`.
2. **Outbound Messaging Lock:**
   - `FOLLOWUP_HUB_DISPATCH_ENABLED = False`
   - `WHATSAPP_ENABLED = False`
   - External APIs (Meta WhatsApp Cloud API, SendGrid/SMTP, Razorpay Live) are disabled or stubbed with test mocks.
3. **Database Segregation:**
   - Acceptance testing and automated validation run exclusively against `leadscore_test_acceptance` or ephemeral CI databases.
   - The live database `leadscore` is protected by runtime interceptors in `database_safety.py`.
4. **Credential Protection:**
   - Gemini API keys, Supabase secrets, and JWT keys must never be logged, printed, or exposed in pilot telemetry.

---

## 2. Environment Startup & Service Verification

### Step 1: Start Core Infrastructure Containers
```powershell
docker compose up -d postgres redis
```

### Step 2: Verify Container Health
```powershell
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```
Expected output:
- `leadscore_postgres`: Up (healthy) bound to `127.0.0.1:5432`
- `leadscore_redis`: Up (healthy) bound to `127.0.0.1:6379`

### Step 3: Verify Alembic Migration Head
```powershell
docker exec leadscore_postgres psql -U postgres -d leadscore -c "SELECT version_num FROM alembic_version;"
```
Expected output: `0048_schema_reconciliation_parity`.

---

## 3. Pre-Flight Safety Verification Procedures

Before initiating any pilot workflows, run the mandatory three-stage pre-flight check:

### Check 1: Static Database Safety Audit
```powershell
python apps/api/scripts/audit_test_database_safety.py
```
- **Standard:** 0 critical shared database mutations found across all test files.

### Check 2: Automated Database Safety Guards
```powershell
python -m pytest apps/api/tests/test_database_safety_guards.py -v
```
- **Standard:** 14 / 14 passed (100%).

### Check 3: CRM Acceptance Pilot Dry Run
```powershell
python apps/api/scripts/run_acceptance_pilot.py
```
- **Standard:** Target validated as `leadscore_test_acceptance`, 16 / 16 checks passed, purge ledger confirms all synthetic entities cleaned up cleanly.

---

## 4. Pilot Workflow Execution Procedures

### 4.1 Synthetic Pilot Organization Provisioning
1. Pilot tenants must be created with `is_demo=True` or identified with slug prefix `pilot-synthetic-`.
2. Synthetic brokers must use non-deliverable email domains (`@pilot.wefylabs.test`).
3. Synthetic phone numbers must use designated test ranges (`+919876500000` to `+919876500999`).

### 4.2 Lead Ingestion & Qualification
1. Submit test leads via `/api/v1/leads` with synthetic payload.
2. Verify lead status initializes to `new` and pipeline stage to `uncontacted`.
3. Check qualification scoring: leads receive automated score (`hot`, `warm`, `cold`) and AI reasoning.
4. Verify AI sales agent generates **recommended actions** without sending automated outbound messages.

### 4.3 Human-in-the-Loop Review
1. Authorized broker reviews AI-generated task recommendations in the CRM UI.
2. Broker manually approves or modifies notes and tasks.
3. Outbound dispatch remains inert; confirmation logs indicate message generation without dispatch.

---

## 5. Monitoring & Observability

### 5.1 Real-Time Container Logs
```powershell
# API HTTP traces and correlation IDs
docker logs -f leadscore_api

# Celery async task execution
docker logs -f leadscore_celery_worker
```

### 5.2 Key Metrics to Track
- **HTTP Error Rate:** Monitor 4xx and 5xx responses via `/metrics`.
- **Database Active Connections:** Verify connections remain under 50.
  ```sql
  SELECT count(*) FROM pg_stat_activity WHERE datname = 'leadscore';
  ```
- **Celery Task Success Rate:** Ensure dead-letter queue count remains 0.

---

## 6. Emergency Procedures & Incident Containment

### Incident 1: Unintended Outbound Dispatch Detected
If an outbound communication is triggered:
1. Immediately kill the Celery worker container:
   ```powershell
   docker stop leadscore_celery_worker
   ```
2. Verify Redis queue:
   ```powershell
   docker exec leadscore_redis redis-cli FLUSHDB
   ```
3. Set environment variable: `FOLLOWUP_HUB_DISPATCH_ENABLED=false` and restart.

### Incident 2: Test Script Target Collision
If a script attempts to connect to `leadscore`:
1. `validate_test_database_target` will abort execution immediately with `UnsafeDatabaseTargetError`.
2. Inspect script configuration: ensure `DATABASE_URL` is pointed to `leadscore_test_acceptance`.
3. Verify live database row counts to confirm zero modifications:
   ```sql
   SELECT count(*) FROM leads;
   SELECT count(*) FROM organizations;
   ```

### Incident 3: Emergency Database Restoration
In the event of database corruption:
1. **NEVER restore directly over `leadscore`**.
2. Restore the backup to a verification database:
   ```powershell
   docker exec -i leadscore_postgres pg_restore -U postgres -d leadscore_restore_emergency /tmp/backup.dump
   ```
3. Perform record-level reconciliation before any table cutover.

