# WEFYLABS DISASTER RECOVERY RUNBOOK
# Enterprise Continuity, Database Restoration & Recovery Runbook

---

## 1. Objectives & SLAs

| Metric | Target | Description |
|---|---|---|
| **RPO (Recovery Point Objective)** | **< 5 minutes** | Maximum acceptable data loss window via continuous WAL archiving & snapshotting |
| **RTO (Recovery Time Objective)** | **< 30 minutes** | Target time from disaster declaration to healthy API and worker traffic resumption |
| **Integrity Standard** | **Zero Data Corruption** | Zero orphan records, zero cross-tenant contamination, Outbox consistency preserved |

> [!IMPORTANT]
> **Factual Environment Classification**:
> Full disaster recovery restoration from cold storage was evaluated against schema definitions, Alembic upgrade scripts, and runtime health probes.
> Actual live restoration of external production cloud clusters (AWS/Supabase) is classified as **NOT VERIFIED IN LOCAL RUNTIME** and requires production owner staging execution.

---

## 2. Disaster Recovery Architecture

```
Production Primary (PostgreSQL + pgvector)
      │
      ├── Continuous WAL Archiving (Point-in-Time Recovery - PITR)
      └── Daily Encrypted Snapshots (02:00 UTC) -> Offsite Cold Storage
      │
[DISASTER EVENT] (Database cluster loss / Region failure)
      │
      ▼
1. Provision new PostgreSQL cluster in recovery region
2. Restore latest snapshot + replay WAL logs to target timestamp
3. Verify Alembic schema alignment: python -m alembic heads -> 0030_enterprise_runtime
4. Start WefyLabs API instances with recovery DATABASE_URL
5. Execute /health/deep probe & DataIntegrityChecker.run_full_diagnostic()
6. Resume Celery workers and Beat scheduler
7. Verify Customer 360 & CRM readability
```

---

## 3. Step-by-Step Restoration Procedure

### Step 1: Provision Recovery Target Database
```bash
# Verify network connectivity to recovery database
export DATABASE_URL="postgresql+asyncpg://app_user:recovery_password@recovery-host:5432/leadscore"
```

### Step 2: Restore Data from Backup Artifact
```bash
# If restoring from pg_dump custom archive:
pg_restore -v -h recovery-host -U app_user -d leadscore -F c latest_wefylabs_backup.dump
```

### Step 3: Run Alembic Migration Verification
```bash
cd apps/api
python -m alembic upgrade head
python -m alembic current
# Expected output must include: 0030_enterprise_runtime (head)
```

### Step 4: Run Health & Diagnostic Sanity Verification
```bash
# Execute deep health check
curl -X GET "http://localhost:8000/health/deep"

# Run non-destructive database integrity checker
python -c "
import asyncio
from app.database import AsyncSessionLocal
from app.modules.diagnostics.integrity_checker import DataIntegrityChecker

async def check():
    async with AsyncSessionLocal() as session:
        report = await DataIntegrityChecker.run_full_diagnostic(session)
        print('Integrity Report:', report)
        assert report['overall_integrity_status'] in ('INTEACT', 'HEALTHY')

asyncio.run(check())
"
```

### Step 5: Start Background Workers & Beat Scheduler
```bash
# Start Celery worker pool
celery -A app.celery_app worker -l INFO -c 4

# Start Celery Beat scheduler (distributed locks guarantee singleton tasks)
celery -A app.celery_app beat -l INFO
```

### Step 6: Verify Customer 360 & CRM Readability
- Log in to Next.js dashboard as an Admin.
- Navigate to `/dashboard/crm` and verify lead count and pipeline columns.
- Open a Customer 360 page `/dashboard/crm/customers/{id}` and confirm LeadIntelligencePanel renders conversion probability and propensity scores.

---

## 4. Rollback & Failover Procedures
If database recovery exhibits anomalies or unrecoverable schema divergence:
1. Immediately stop API instances to prevent writing new corrupt records.
2. Terminate Celery Beat to prevent periodic worker runs.
3. Switch DNS/Traffic back to the standby read-replica or previous verified checkpoint.
4. Notify Stakeholders via SecOps & Reliability incident channels.

---
_Status: ARCHITECTURALLY VERIFIED; CLOUD RESTORATION REQUIRES STAGING OWNER ACTION._
