# PART 33.1 — PROPERTY LISTINGS SCHEMA DRIFT FIX
**Resolution of UndefinedColumnError: column property_listings.total_floors does not exist**

---

## 1. Executive Summary

A real runtime schema drift was encountered in the AI Real-Estate Agent Command Center:
```
<class 'asyncpg.exceptions.UndefinedColumnError'>: column property_listings.total_floors does not exist
```
The error manifested during Command Center dashboard initial load when `fetchCommandCenter` (`apps/web/src/components/dashboard/CommandCenterView.tsx`) triggered the backend API (`GET /api/v1/command-center`), which executed SQLAlchemy ORM queries projecting all `PropertyListing` attributes including `property_listings.total_floors`.

Rather than suppressing exceptions, returning mock data, or hiding fields in the UI, the issue was resolved by identifying the exact divergence between the SQLAlchemy model, Alembic revision history, and PostgreSQL metadata, followed by creating and applying a formal, forward, non-destructive Alembic migration (`0025_property_total_floors`).

---

## 2. Root Cause Analysis

### Three Sources Comparison

| Attribute | SQLAlchemy Model (`PropertyListing`) | Alembic Migration DDL | Live PostgreSQL (`information_schema.columns`) |
| :--- | :--- | :--- | :--- |
| `floor_number` | `Integer, nullable=True` | Baseline `9999_production_baseline` | `integer`, `is_nullable=YES`, default `None` |
| `total_floors` | `Integer, nullable=True` | **Omitted** from `0021_property_inventory_crm` and earlier revisions | **MISSING** (`column does not exist`) |
| Remaining 64 columns | All 64 fields match | Baseline + `0014` + `0021` | **ALL 64 columns match exactly** |

### Divergence Mechanism
1. The SQLAlchemy `PropertyListing` model (`apps/api/app/models/property_models.py`) declared:
   ```python
   floor_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
   total_floors: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
   ```
2. When migration `0021_property_inventory_crm.py` was authored for Part 28 to extend the baseline `property_listings` table, `balconies`, `price_min`, `price_max`, `carpet_area`, etc. were explicitly added via `batch_op.add_column(...)`, but `total_floors` was accidentally omitted from the DDL.
3. Because SQLAlchemy ORM selects all mapped columns when constructing entity queries (e.g. in `CommandCenterService.get_command_center_data`):
   ```sql
   SELECT property_listings.id, ... property_listings.floor_number, property_listings.total_floors, ... FROM property_listings
   ```
   PostgreSQL immediately raised `UndefinedColumnError` when compiling the query.

### Comprehensive Schema Audit of Other Critical CRM Tables
A full audit against `information_schema.columns` was executed for all core system tables:
- `property_listings`: Only `total_floors` was missing; all other 65 columns matched.
- `lead_property_interests`: 22/22 columns match perfectly.
- `property_price_history`: 7/7 columns match perfectly.
- `onboarding_states`: 11/11 columns match perfectly.
- `tenant_activations`: 13/13 columns match perfectly.
- `demo_sessions`: 10/10 columns match perfectly.
- `command_center_dismissals`: 10/10 columns match perfectly.
- `tasks`: 15/15 columns match perfectly.
- `leads`: 28/28 columns match perfectly.
- `organizations`: 18/18 columns match perfectly.
- `brokers`: 17/17 columns match perfectly.

**Conclusion**: Schema drift was strictly isolated to `property_listings.total_floors`.

---

## 3. Migration Implementation

- **File**: `apps/api/alembic/versions/0025_property_total_floors.py`
- **Revision ID**: `0025_property_total_floors` (26 chars $\le$ 32 chars to conform with `alembic_version.version_num VARCHAR(32)`)
- **Down Revision**: `0024_onboarding_activation_demo`
- **Design**:
  - Idempotent table and column inspection using `sa.inspect(bind)`
  - Forward-only, additive change (`sa.Column("total_floors", sa.Integer(), nullable=True)`)
  - ZERO table drops, ZERO column renames, ZERO data destruction
  - Reversible downgrade via `batch_op.drop_column("total_floors")`

### Applied Migration DDL
```python
def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "property_listings" in tables:
        prop_cols = [c["name"] for c in inspector.get_columns("property_listings")]
        with op.batch_alter_table("property_listings") as batch_op:
            if "total_floors" not in prop_cols:
                batch_op.add_column(sa.Column("total_floors", sa.Integer(), nullable=True))
```

---

## 4. Verification Evidence

### Failure Reproduction Before Migration
```
Attempting to query PropertyListing via SQLAlchemy ORM...
REPRODUCED EXPECTED EXCEPTION:
Exception Type: <class 'sqlalchemy.exc.ProgrammingError'>
Exception Message: (sqlalchemy.dialects.postgresql.asyncpg.ProgrammingError) <class 'asyncpg.exceptions.UndefinedColumnError'>: column property_listings.total_floors does not exist
[SQL: SELECT property_listings.id, ... property_listings.total_floors ... FROM property_listings LIMIT $1::INTEGER]
```

### Execution After Migration
```
Attempting to query PropertyListing via SQLAlchemy ORM...
Query succeeded: <app.models.property_models.PropertyListing object at 0x000002233F674D70>
```

### Live Database Schema Metadata
```
PostgreSQL information_schema.columns for property_listings:
- total_floors: integer, nullable=YES, default=None
- floor_number: integer, nullable=YES, default=None
Total columns: 66/66 (100% matched to PropertyListing model)
```

### Live Command Center Execution
Direct execution of `CommandCenterService.get_command_center_data` against the live Supabase PostgreSQL database:
```
Testing Command Center for broker: 17a569ed-e289-46e4-8c64-722692111721
Testing get_command_center_data...
Success! Summary metrics: {'critical_actions_count': 0, 'high_actions_count': 0, ...}
Priorities count: 0
Today schedule count: 0
Inventory opportunities count: 0
Inventory gaps count: 0
Daily briefing greeting: Good morning, Aamir
ALL LIVE COMMAND CENTER QUERIES EXECUTED WITH ZERO ERRORS!
```

---

## 5. Test Verification Summary

| Test Suite | Scope | Result | Passing |
| :--- | :--- | :--- | :--- |
| **Part 33.1** | `test_part33_1_schema_drift.py` | **PASS** | **7/7** |
| **Part 28** | Property Inventory CRM | **PASS** | **14/14** |
| **Part 29** | AI Matching Engine | **PASS** | **107/107** |
| **Part 30** | Agent Command Center | **PASS** | **80/80** |
| **Part 31** | Onboarding & Activation | **PASS** | **88/88** |
| **Part 32** | Production Hardening & Reliability | **PASS** | **95/95** |
| **Part 33** | Launch Infrastructure & Deployment | **PASS** | **32/32** |
| **Part 27** | Follow-up Automation Engine | **PASS** | **15/15** |
| **Frontend Typecheck** | Next.js 15.5.24 `npx tsc --noEmit` | **PASS** | **0 errors** |
| **Frontend Build** | Next.js `npm run build` | **PASS** | **33/33 static pages generated** |
| **Alembic Validation** | `python -m alembic heads` | **PASS** | **Single head: `0025_property_total_floors`** |

---

## 6. Deployment & Rollback Considerations

1. **Automated Migration on Startup**:
   `apps/api/entrypoint.sh` executes `python -m alembic upgrade head` inside transactional DDL before starting Uvicorn workers. If migration fails, deployment fails immediately and stops bad pods from serving traffic.
2. **Worker Isolation**:
   Celery workers and beat processes in `render.yaml` do NOT run migrations, preventing concurrent migration conflicts.
3. **Rollback**:
   If required, downgrade is supported via `python -m alembic downgrade -1`, which invokes `batch_op.drop_column("total_floors")` safely. Existing data in all other 65 columns remains untouched.
