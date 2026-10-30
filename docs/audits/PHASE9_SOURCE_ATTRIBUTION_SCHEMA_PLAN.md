# PHASE 9 AUDIT REPORT: SOURCE ATTRIBUTION SCHEMA RECONCILIATION & REFERENTIAL INTEGRITY PLAN

**Document ID:** `PHASE9_SOURCE_ATTRIBUTION_SCHEMA_PLAN`  
**Date:** 2026-10-28  
**Auditor:** Principal Database Reliability Engineer & Release Auditor  
**Repository Branch:** `level-3`  
**Isolated Test DB:** `leadscore_test_acceptance`  
**Live DB Status:** `leadscore` (STRICTLY READ-ONLY — 0 MUTATIONS)  

---

## 1. Background & Problem Statement

In `apps/api/app/models/acquisition_models.py:489-494`, the `SourceAttribution` ORM model was declared with string-based foreign keys lacking database-level referential constraints:

```python
# PREVIOUS LEGACY MODEL DEFINITION
id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
```

In PostgreSQL:
- `leads.id` is defined as `UUID(as_uuid=True)` (native PostgreSQL `uuid`).
- `organizations.id` is defined as `UUID(as_uuid=True)` (native PostgreSQL `uuid`).
- `source_attributions.lead_id` and `organization_id` were stored as `character varying(36)` without foreign key references.

### Forensic Finding: Root Cause of Residual Records
During the Phase 6 and Phase 7 forensic investigations, two residual records were identified in `source_attributions` after synthetic leads had been deleted. The absence of foreign key constraints (`ON DELETE SET NULL` or `ON DELETE CASCADE`) allowed orphan attribution rows to persist in PostgreSQL whenever lead entities were removed. Furthermore, cross-type joins (`leads.id = source_attributions.lead_id`) required explicit typecasting in SQL (`::uuid`), creating runtime query fragility.

---

## 2. Referential Policy & Schema Parity Design

The referential policy was established based on enterprise CRM marketing domain invariants:
1. **Preservation of Marketing Intelligence:** If a canonical lead is merged or purged, historical acquisition provenance (UTM campaigns, touchpoints, channel attribution) must not be lost from marketing ROI models. Therefore, `lead_id` must be `nullable=True` with `ON DELETE SET NULL`.
2. **Strict Tenant Cascade:** If an entire organization tenant is deleted, all associated source attributions must be cleanly purged. Therefore, `organization_id` must have `ON DELETE CASCADE`.
3. **Native PostgreSQL UUID Parity:** Both columns must be converted to native PostgreSQL `uuid` types using `USING column::uuid`, matching `leads.id` and `organizations.id`.

### Remediated ORM Model (`apps/api/app/models/acquisition_models.py`):
```python
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[Any] = mapped_column(
        UUIDType, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # The canonical CRM Lead this attribution belongs to
    lead_id: Mapped[Optional[Any]] = mapped_column(
        UUIDType, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True
    )
```

---

## 3. Isolated Migration & Rollback Verification

The migration was thoroughly verified against the isolated test database `leadscore_test_acceptance` using an automated verification harness (`scratch/test_source_attribution_migration.py`). The live database `leadscore` was never modified.

### Execution Log Evidence:
```
[1] Baseline check on leadscore_test_acceptance...
Baseline columns: [('lead_id', 'character varying', 'NO'), ('organization_id', 'character varying', 'NO')]

[2] Executing Upgrade Migration...
Upgrade migration executed successfully.

[3] Introspecting migrated columns and constraints...
Migrated columns: [('lead_id', 'uuid', 'YES'), ('organization_id', 'uuid', 'NO')]
FK Constraints found: {'fk_source_attributions_lead_id': 'n', 'fk_source_attributions_organization_id': 'c'}
Referential integrity constraints correctly configured.

[4] Testing Referential Integrity in practice...
Inserted test lead and test attribution successfully.
Referential check PASSED: Nonexistent lead was rejected by foreign key.
SET NULL policy PASSED: Lead deletion preserved attribution record with lead_id set to NULL.

[5] Testing Rollback Migration...
Rollback executed successfully.

[6] Introspecting rolled-back schema...
Reverted columns: [('lead_id', 'character varying', 'NO'), ('organization_id', 'character varying', 'NO')]
Rollback test SUCCESSFUL! Isolated DB restored exactly to baseline.
```

---

## 4. Alembic Migration Implementation

Alembic migration revision `0049_source_attribution_uuid_parity.py` was authored in `apps/api/alembic/versions/` chaining directly from head `0048_schema_reconciliation_parity`.

### Migration Structure:
```python
revision: str = "0049_source_attribution_uuid_parity"
down_revision: Union[str, None] = "0048_schema_reconciliation_parity"

def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE source_attributions ALTER COLUMN lead_id DROP NOT NULL;")
        op.execute(
            "ALTER TABLE source_attributions "
            "ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid, "
            "ALTER COLUMN lead_id TYPE uuid USING lead_id::uuid;"
        )
        op.execute(
            "ALTER TABLE source_attributions "
            "ADD CONSTRAINT fk_source_attributions_organization_id "
            "FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;"
        )
        op.execute(
            "ALTER TABLE source_attributions "
            "ADD CONSTRAINT fk_source_attributions_lead_id "
            "FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL;"
        )
```

---

## 5. Live Database Integrity Verification

Before and after isolated test execution, the live `leadscore` database was queried using strictly read-only diagnostics. The live counts remained 100% invariant:

| Table | Live `leadscore` Row Count | Parity Status |
| :--- | :--- | :--- |
| `leads` | 4 | Invariant |
| `organizations` | 7 | Invariant |
| `brokers` | 8 | Invariant |
| `organization_members` | 7 | Invariant |
| `source_attributions` | 3 | Invariant |

Unit tests in `apps/api/tests/test_part21_lead_acquisition.py` passed with 73/73 tests green.

