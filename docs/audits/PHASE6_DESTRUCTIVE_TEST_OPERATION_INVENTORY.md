# WEFYLABS AUTONOMOUS REVENUE OS — PHASE 6 DESTRUCTIVE TEST OPERATION INVENTORY
## Repository-Wide Audit of Database Mutating Tooling, Scripts, and Test Harnesses

**Audit Date**: 2026-10-28T19:30:00+05:30  
**Repository**: WefyLabs / BeetleLabs AI Real Estate CRM  
**Base Commit**: `0383020a865fe315adfda4549f536a594fb10454`  
**Auditor Roles**: Principal Application Security Engineer & Release Reliability Auditor  
**Deliverable**: Master Prompt 6 — Phase F

---

## 1. Executive Summary

A repository-wide code audit was conducted across all unit tests, integration test suites, smoke test scripts, operational utilities, and scratch tooling. The objective was to catalog all operations capable of executing `DELETE`, `UPDATE`, `TRUNCATE`, `DROP TABLE`, `DROP SCHEMA`, database restorations, or synthetic tenant provisioning, and evaluate whether they operate under strong environment guards or risk targeting the live database `leadscore`.

### Key Findings:
1. **Pytest Unit & Integration Suite (`apps/api/tests/`)**:
   - Safely isolated. `conftest.py` configures `TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"` and enforces `ENV="testing"` via `scope_test_environment(monkeypatch)`. In-memory SQLite is isolated per test function.
2. **Acceptance / Standalone Runner Tooling (`scratch/`)**:
   - `phase5_e2e_pilot_acceptance.py` historically connected to `leadscore` due to lack of target guards. **Now remediated with `validate_test_database_target` and `TestEntityTracker` in Phase E.**
3. **Database Bootstrap & Maintenance Scripts (`apps/api/scripts/`)**:
   - `init_db.py`: Certified bootstrap script. Includes `--check-only` mode and target schema scoping, but accepts general PostgreSQL URLs.
   - `seed_global_data.py`: Certified idempotent seed data for global geographic definitions.

---

## 2. Risk-Ranked Inventory of Database Mutating Operations

### 2.1 Critical Risk (Direct Shared Database Mutation Capability)

| Script / Test File | Operation / Code Pattern | Target DB Resolution | Environment Guard Status | Risk Description | Remediation Implemented / Required |
|---|---|---|---|---|---|
| `scratch/phase5_e2e_pilot_acceptance.py` | `delete(Lead)`, `delete(Broker)`, `delete(Organization)` | Inherited `settings.DATABASE_URL` (`leadscore`) | **REMEDIATED** | Historically executed directly on live stack during Phase 5 container dry run | Integrated `validate_test_database_target` and `TestEntityTracker`. Targets `leadscore_test_acceptance`. Fails closed if pointed to `leadscore`. |

---

### 2.2 High Risk (DDL / Schema Drops / Migrations)

| Script / Test File | Operation / Code Pattern | Target DB Resolution | Environment Guard Status | Risk Description | Remediation Implemented / Required |
|---|---|---|---|---|---|
| `apps/api/tests/test_database_bootstrap_and_migrations.py` | `DROP SCHEMA IF EXISTS {test_schema} CASCADE` | Ephemeral UUID schema name | Guarded by schema UUID regex | Tests dynamic multi-schema creation and disposal | Isolated to test schema prefixes; verified safe. |
| `apps/api/scripts/init_db.py` | `Base.metadata.create_all`, Alembic head stamp | CLI `--db-url` or `settings.DATABASE_URL` | Restricted by `ALLOWED_ENVIRONMENTS` check | Can provision tables on designated database | Guarded with `--check-only` flag and confirmation. Must never be run with destructive flags on live database. |
| `apps/api/tests/test_master_build_14_benchmarking.py` | `Base.metadata.drop_all(eng)` | `sqlite:///:memory:` | Guarded by engine fixture | Drops in-memory SQLite tables between benchmark runs | Strictly in-memory; zero network target capability. |
| `apps/api/tests/test_master_build_14_intelligence.py` | `Base.metadata.drop_all(eng)` | `sqlite:///:memory:` | Guarded by engine fixture | Drops in-memory SQLite tables | Strictly in-memory; zero network target capability. |

---

### 2.3 Medium Risk (Direct SQL / Deletions in Unit Test Harnesses)

| Script / Test File | Operation / Code Pattern | Target DB Resolution | Environment Guard Status | Risk Description | Remediation Implemented / Required |
|---|---|---|---|---|---|
| `apps/api/tests/conftest.py` | `Base.metadata.drop_all` (autouse fixture) | `sqlite+aiosqlite:///:memory:` | Strictly bound to `:memory:` | Drops SQLite tables at end of test function | Proven 100% isolated to memory; cannot reach PostgreSQL. |
| `apps/api/tests/test_enterprise_foundation.py` | `lead.deleted_at = datetime.now(...)` | `sqlite+aiosqlite:///:memory:` | Bound to SQLite session | Soft-delete behavioral test | In-memory only. Soft delete only. |
| `apps/api/tests/test_leads.py` | `ac.delete("/api/v1/leads/{id}")` | In-memory TestClient / SQLite | Bound to `db_session` fixture | REST API soft-delete endpoint test | Operates on synthetic test leads in memory. |

---

### 2.4 Low Risk (Read-Only / Forensic Scripts)

| Script / Test File | Operation / Code Pattern | Target DB Resolution | Environment Guard Status | Risk Description | Remediation Implemented / Required |
|---|---|---|---|---|---|
| `scratch/phase6_db_reconciliation.py` | `SELECT count(*)`, `md5(...)` | `leadscore` and `leadscore_verify_phase6` | `SET default_transaction_read_only = on` | Read-only forensic comparison | Enforces connection read-only mode; cannot issue writes. |
| `scratch/verify_every_table.py` | `SELECT {pk_cols} FROM {tbl}` | `leadscore` and `leadscore_verify_phase6` | `SET default_transaction_read_only = on` | Read-only full-table audit | Enforces connection read-only mode; cannot issue writes. |
| `scratch/inspect_priority_records.py` | `SELECT id, name FROM {tbl}` | `leadscore` and `leadscore_verify_phase6` | Read-only SELECT statements | Sanitized record verification | Read-only. |

---

## 3. Operational Best Practices & Guardrails

To prevent future acceptance scripts or developer tooling from mutating shared databases:

1. **Rule 1 — Universal Test Target Gate**: Any standalone test runner or acceptance script must call `validate_test_database_target(db_url, env)` before opening a database session.
2. **Rule 2 — TestEntityTracker Mandatory for Endpoints that Commit**: Tests verifying HTTP endpoints that commit transactions must register all created primary keys with `TestEntityTracker` and execute cleanup strictly through `safe_cleanup()`.
3. **Rule 3 — Hard Rejection of Production Database Names**: The application framework rejects connection strings containing `leadscore`, `leadscore_prod`, or `leadscore_production` whenever `ENV` is `testing` or `test`.
4. **Rule 4 — No Direct Container Execution Against Live Database**: Acceptance tests must not be copied into the production container without overriding `DATABASE_URL` to an isolated database.

---

## 4. Conclusion

All mutating test scripts across the repository are now categorized and accounted for. Standalone acceptance testing has been remediated with fail-closed target guards, and the standard Pytest suite remains strictly bounded to in-memory SQLite.

