# WEFYLABS — APPLIED MIGRATION IMMUTABILITY AUDIT

**Project:** WefyLabs / BeetleLabs — AI-Native Real Estate Revenue Operating System  
**Document ID:** `WEFYLABS_APPLIED_MIGRATION_IMMUTABILITY_AUDIT`  
**Audit Date:** 2026-10-30  
**Scope:** Alembic Revisions `0048`, `0049`, `0050`  
**Authoritative Head:** `0050_broker_subscription_constraint_parity`  
**Audit Status:** **VERIFIED, ACCOUNTED FOR, AND FROZEN**

---

## 1. Executive Summary

Alembic migrations must be strictly immutable once applied to an authoritative target. This audit establishes complete cryptographic and forensic accountability for migrations `0048_schema_reconciliation_parity`, `0049_source_attribution_uuid_parity`, and `0050_broker_subscription_constraint_parity`.

Specifically, this report documents an in-flight idempotency hardening edit performed on `0049_source_attribution_uuid_parity.py`, proves why the schema remained uncorrupted on production, and verifies that the migration DAG is now permanently frozen.

---

## 2. Inventory of Applied Migrations

| Revision ID | Down Revision | Filename | SHA-256 Hash | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| `0048_schema_reconciliation_parity` | `0047_webhook_event_claims` | `apps/api/alembic/versions/0048_schema_reconciliation_parity.py` | `085698b672728f3bb7cb3fc7e5108f2e...` | Baseline parity reconciliation |
| `0049_source_attribution_uuid_parity` | `0048_schema_reconciliation_parity` | `apps/api/alembic/versions/0049_source_attribution_uuid_parity.py` | `d767118fa4bceba34208a0d4aeeb7779...` | UUID column typing & referential integrity |
| `0050_broker_subscription_constraint_parity` | `0049_source_attribution_uuid_parity` | `apps/api/alembic/versions/0050_broker_subscription_constraint_parity.py` | `a165b469956424458f3f8eeecb910e42...` | Broker subscription check constraint parity |

---

## 3. In-Flight Migration Modification Forensic Analysis

### 3.1 Background of the Modification
During the execution lifecycle, migration `0049_source_attribution_uuid_parity.py` was applied to hosted Supabase to transition columns from `VARCHAR(36)` to `UUID`. Subsequently, during container rehearsal and multi-tenant test matrix executions against template databases, the migration encountered errors when run against environments where foreign keys with the same name already existed.

To ensure strict idempotency and prevent test suite breakage, two defensive DDL statements were added:
- `ALTER TABLE source_attributions DROP CONSTRAINT IF EXISTS fk_source_attributions_organization_id;`
- `ALTER TABLE source_attributions DROP CONSTRAINT IF EXISTS fk_source_attributions_lead_id;`

### 3.2 Exact Diff Analysis

```diff
--- 0049_source_attribution_uuid_parity.py (Initial Draft)
+++ 0049_source_attribution_uuid_parity.py (Hardened Final)
@@ -38,6 +38,10 @@
             "ALTER TABLE source_attributions "
             "ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid, "
             "ALTER COLUMN lead_id TYPE uuid USING lead_id::uuid;"
         )
+        op.execute(
+            "ALTER TABLE source_attributions "
+            "DROP CONSTRAINT IF EXISTS fk_source_attributions_organization_id;"
+        )
         op.execute(
             "ALTER TABLE source_attributions "
             "ADD CONSTRAINT fk_source_attributions_organization_id "
@@ -53,6 +57,10 @@
             "WHERE lead_id IS NOT NULL "
             "  AND NOT EXISTS (SELECT 1 FROM leads WHERE leads.id = source_attributions.lead_id);"
         )
+        op.execute(
+            "ALTER TABLE source_attributions "
+            "DROP CONSTRAINT IF EXISTS fk_source_attributions_lead_id;"
+        )
         op.execute(
             "ALTER TABLE source_attributions "
             "ADD CONSTRAINT fk_source_attributions_lead_id "
```

### 3.3 Impact Assessment on Live Supabase Production
1. **Schema Identity:** Because `DROP CONSTRAINT IF EXISTS` is a safe NO-OP if the constraint does not exist, the resulting schema state on production is 100% identical whether executed before or after the edit.
2. **Catalog Integrity:** Foreign keys `fk_source_attributions_organization_id` and `fk_source_attributions_lead_id` are registered and active on live Supabase.
3. **Re-run Safety:** A subsequent test run of `apps/api/scripts/release_migration.py` against live Supabase executed with **Exit Code 0 (NO-OP)** without altering any constraints or tables.

---

## 4. Downgrade Guard & Disaster Recovery Immutability

Migration 0049 includes an explicit fail-closed safety guard in its `downgrade()` function:

```python
null_count = bind.execute(
    sa.text("SELECT count(*) FROM source_attributions WHERE lead_id IS NULL;")
).scalar()
if null_count and null_count > 0:
    raise RuntimeError(
        f"DOWNGRADE ABORTED: Found {null_count} source_attributions records with NULL lead_id. "
        "PostgreSQL 0048 schema enforces NOT NULL on lead_id. "
        "To roll back safely without data loss, adopt the forward-recovery pattern (Migration 0050) "
        "or restore original lead entities."
    )
```

Because 1 historical orphaned marketing attribution record in production now has `lead_id = NULL` (safely preserved rather than deleted), an accidental `alembic downgrade` command will fail closed immediately, preventing data corruption or unhandled PostgreSQL constraint violations.

---

## 5. Certification and Freeze Mandate

1. **Frozen State:** Revisions `0048`, `0049`, and `0050` are marked as **FROZEN**. No further modifications to these files are permitted.
2. **Future Schema Changes:** Any subsequent schema modifications must be authored as revision `0051_...` with down-revision `0050_broker_subscription_constraint_parity`.

