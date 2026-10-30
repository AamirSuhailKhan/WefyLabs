# WEFYLABS PHASE 10 — ALEMBIC MIGRATION 0049 PRODUCTION RUNBOOK
**Migration ID:** `0049_source_attribution_uuid_parity`  
**Down Revision:** `0048_schema_reconciliation_parity`  
**Target Table:** `source_attributions`  
**Author:** Principal Database Reliability Engineer (DRE)  
**Date:** 2026-10-28  

---

## 1. Overview & Business Justification

Migration `0049_source_attribution_uuid_parity` resolves referential integrity and type consistency between `source_attributions` and core CRM tables:
1. Reconciles `source_attributions.organization_id` from `VARCHAR(36)` to native `UUID` with foreign key `fk_source_attributions_organization_id` referencing `organizations(id)` on delete `CASCADE`.
2. Reconciles `source_attributions.lead_id` from `VARCHAR(36)` to native `UUID` (nullable) with foreign key `fk_source_attributions_lead_id` referencing `leads(id)` on delete `SET NULL`.
3. Preserves historical marketing attribution even if lead records are merged or purged.

---

## 2. Rehearsal Execution & Evidence on `leadscore_test_acceptance`

Migration 0049 was fully rehearsed against the isolated PostgreSQL container database `leadscore_test_acceptance`:

### A. Pre-Migration Inspection (Revision: `0048`):
```text
Alembic version: ['0048_schema_reconciliation_parity']
Columns:
  organization_id: character varying, nullable=NO
  lead_id: character varying, nullable=NO
Foreign keys:
  (No foreign keys to organizations or leads)
```

### B. Upgrade Execution:
```powershell
python -m alembic -x db_url=postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_test_acceptance upgrade head
```
**Output:**
```text
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 0048_schema_reconciliation_parity -> 0049_source_attribution_uuid_parity, Reconcile SourceAttribution column types and referential integrity.
```

### C. Post-Upgrade Verification:
```text
Alembic version: ['0049_source_attribution_uuid_parity']
Columns:
  organization_id: uuid, nullable=NO
  lead_id: uuid, nullable=YES
Foreign keys:
  fk_source_attributions_lead_id: lead_id -> leads (ON DELETE SET NULL)
  fk_source_attributions_organization_id: organization_id -> organizations (ON DELETE CASCADE)
```

### D. Downgrade Rehearsal:
```powershell
python -m alembic -x db_url=postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_test_acceptance downgrade 0048_schema_reconciliation_parity
```
**Output:**
```text
INFO  [alembic.runtime.migration] Running downgrade 0049_source_attribution_uuid_parity -> 0048_schema_reconciliation_parity, Reconcile SourceAttribution column types and referential integrity.
Schema successfully restored to character varying and nullable=NO.
```

---

## 3. Production Rollout Procedure (for Live `leadscore`)

> [!IMPORTANT]
> The live database `leadscore` is currently at `0048_schema_reconciliation_parity` and was **NOT** upgraded during this audit to preserve strict read-only guarantees.
> Follow this exact runbook during the scheduled maintenance window to apply migration 0049 to production.

### Pre-Requisites:
- Maintenance window approved by CTO.
- Backups verified.

### Step 1: Pre-Migration Health & Row Check
Execute before taking any action:
```bash
python -c "
import asyncio, asyncpg
async def check():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/leadscore')
    v = await conn.fetchval('SELECT version_num FROM alembic_version')
    cnt = await conn.fetchval('SELECT count(*) FROM source_attributions')
    print(f'[PRE-CHECK] Revision: {v}, source_attributions rows: {cnt}')
    await conn.close()
asyncio.run(check())
"
```
*Expected Output:* Revision: `0048_schema_reconciliation_parity`, rows: `3`.

### Step 2: Create Pre-Migration Physical Snapshot
```bash
docker exec -t leadscore_postgres pg_dump -U postgres -d leadscore -F c -b -v -f /var/lib/postgresql/data/leadscore_pre_0049.dump
```

### Step 3: Execute Alembic Upgrade
```bash
cd apps/api
python -m alembic -x db_url=postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore upgrade head
```

### Step 4: Validate Post-Migration Integrity
```bash
python -c "
import asyncio, asyncpg
async def check():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/leadscore')
    v = await conn.fetchval('SELECT version_num FROM alembic_version')
    cols = await conn.fetch(\"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'source_attributions' AND column_name IN ('organization_id', 'lead_id')\")
    fks = await conn.fetch(\"SELECT constraint_name FROM information_schema.table_constraints WHERE table_name = 'source_attributions' AND constraint_type = 'FOREIGN KEY'\")
    print(f'[POST-CHECK] Revision: {v}')
    for c in cols: print(' ', dict(c))
    print(' FKs:', [r['constraint_name'] for r in fks])
    await conn.close()
asyncio.run(check())
"
```
*Verification Assertions:*
1. Revision must equal `0049_source_attribution_uuid_parity`.
2. `organization_id` type must equal `uuid`.
3. `lead_id` type must equal `uuid` and `is_nullable == YES`.
4. `fk_source_attributions_lead_id` and `fk_source_attributions_organization_id` must be present.

### Step 5: Rollback Plan (If Needed)
If any step fails or unexpected application behavior occurs:
```bash
cd apps/api
python -m alembic -x db_url=postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore downgrade 0048_schema_reconciliation_parity
```
Or restore from physical backup:
```bash
docker exec -t leadscore_postgres pg_restore -U postgres -d leadscore --clean /var/lib/postgresql/data/leadscore_pre_0049.dump
```

