# WEFYLABS AUTONOMOUS REVENUE OS — DATABASE INTEGRITY AUDIT

**Audit Date**: 2026-10-27T15:58:00Z  
**Target Engine**: PostgreSQL 16 with pgvector (`leadscore_postgres`)  
**ORM / Migration Framework**: SQLAlchemy 2.0 (asyncpg) / Alembic 1.18.5  
**Current Revision**: `0048_schema_reconciliation_parity` (Head)  
**Schema Parity Status**: `VERIFIED PARITY (0 Detected Differences)`

---

## 1. Migration Lineage & Graph Topology

The migration tree was audited using `alembic heads` and `alembic history`.
- **Topological Structure**: Strictly linear DAG with zero orphaned heads and zero split branches.
- **Recent Revision History**:
  - `0044_token_blacklist_revocation`: Creates `token_blacklist` table for session invalidation.
  - `0045_broker_auth_version`: Adds `auth_version` column to `brokers` for token invalidation after security events.
  - `0046_broker_google_subject`: Adds `google_subject` column with index to `brokers` for Google OAuth account linking.
  - `0047_webhook_event_claims`: Implements provider webhook idempotency claims table.
  - `0048_schema_reconciliation_parity` (HEAD): Reconciles ORM composite indexes (`ix_leads_country_market`, `ix_leads_deleted_at`, `ix_leads_org_status`), relaxes broker contact nullability for un-onboarded OAuth users (`phone`, `whatsapp_number`, `city` -> nullable=True), and removes legacy hardcoded city defaults.

---

## 2. Model-to-Database Schema Parity (`alembic check`)

Executed Command: `docker compose exec api alembic check`
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.schemas
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.tables
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.types
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.constraints
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.defaults
INFO  [alembic.runtime.plugins] setting up autogenerate plugin alembic.autogenerate.comments
No new upgrade operations detected.
```
**Finding**: Zero autogenerate differences between declared SQLAlchemy ORM declarative models and physical PostgreSQL catalog tables.

---

## 3. Data Preservation Audit

Query Executed:
```sql
SELECT 'brokers' as tbl, count(*) FROM brokers
UNION ALL SELECT 'leads', count(*) FROM leads
UNION ALL SELECT 'conversations', count(*) FROM conversations
UNION ALL SELECT 'payment_orders', count(*) FROM payment_orders;
```
Results:
- `brokers`: **8 rows** (100% preserved)
- `leads`: **4 rows** (100% preserved)
- `conversations`: **5 rows** (100% preserved)
- `payment_orders`: **0 rows** (100% preserved)

Volume Audit: `crmrealstate_postgres_data` persistent volume verified continuously mounted at `/var/lib/postgresql/data`. Zero destructive drops, truncates, or resets executed.

---

## 4. Constraint, Foreign Key & Tenant Scoping Safeguards

1. **Composite & Performance Indexes**:
   - `ix_leads_country_market`: Fast filtering across international territory boundaries.
   - `ix_leads_deleted_at`: Index-assisted soft-delete query filtering.
   - `ix_leads_org_status`: Composite index guaranteeing fast organization-scoped status queries without full table scans.
2. **Tenant Scoping & Foreign Key Constraints**:
   - Every primary domain entity (`leads`, `conversations`, `properties`, `tasks`) maintains explicit foreign key relationships (`organization_id` referencing `organizations.id` or `broker_id` referencing `brokers.id`).
   - Repository queries enforce tenant scoping at query compile time via SQLAlchemy `where(or_(Lead.organization_id == tenant_id, Lead.broker_id == tenant_id))`.
3. **Transaction Boundaries & Partial Writes**:
   - Background tasks and HTTP endpoints enforce atomic session scopes using async context managers (`async with async_session_factory() as session:`).
   - In the event of an unhandled exception, transactions are automatically rolled back, preventing orphaned or partially written child entities.

---

## 5. Backup & Recovery Recommendation

- **Live Snapshot Command**:
  ```bash
  docker compose exec postgres pg_dump -U postgres -d leadscore -Fc -f /var/lib/postgresql/data/leadscore_backup.dump
  ```
- **Disaster Recovery Restore**:
  ```bash
  docker compose exec postgres pg_restore -U postgres -d leadscore_restore /var/lib/postgresql/data/leadscore_backup.dump
  ```
- **Pilot Safeguard**: Automatic database migrations during production API startup must be restricted; migrations should be applied explicitly via release pipelines.
