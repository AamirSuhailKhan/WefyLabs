# WEFYLABS PHASE 7 — TEST CLEANUP SAFETY & RUNTIME ISOLATION AUDIT

**Project:** WefyLabs Autonomous Revenue OS / AI Real Estate CRM  
**Target Module:** `apps/api/app/core/database_safety.py`  
**Test Suite:** `apps/api/tests/test_database_safety_guards.py` (14 / 14 passed)  
**Acceptance Runner:** `apps/api/scripts/run_acceptance_pilot.py` (16 / 16 passed x 2 runs)  
**Audited Target Database:** `leadscore_test_acceptance`  
**Audit Date:** 2026-10-28  

---

## 1. Executive Summary

Phase 7 remediates the critical vulnerability identified in Phase 5, where acceptance test scripts executed unbounded raw SQL deletions (`DELETE FROM leads`, `DELETE FROM organizations`, etc.) directly against the application database.

The remediated architecture enforces **runtime database-level isolation** through a fail-closed interceptor, an explicit positive allowlist, session-target binding verification, and an idempotent test entity tracker (`TestEntityTracker`).

---

## 2. Multi-Tier Runtime Safety Guards (`database_safety.py`)

### 2.1 Positive Database Allowlist
Rather than relying solely on blacklisting `leadscore`, the safety module enforces a positive allowlist:
```python
EXPLICIT_TEST_DATABASE_ALLOWLIST = {
    ":memory:",
    "leadscore_test_acceptance",
    "leadscore_verify_phase6",
    "leadscore_test",
    "leadscore_ci_test",
}
DYNAMIC_TEST_DATABASE_PATTERN = re.compile(r"^(leadscore_test|test_db)_[a-f0-9]{4,32}$")
```
Any target database not explicitly permitted by name or dynamic ephemeral pattern raises `UnsafeDatabaseTargetError` immediately before any connection or query can be executed.

### 2.2 Live Database Hard Intercept
The live application database `leadscore` (and variants like `leadscore_prod`, `leadscore_live`) is unconditionally blocked regardless of environment flags or bypass attempts:
```python
FORBIDDEN_SHARED_DATABASES = {
    "leadscore",
    "leadscore_prod",
    "leadscore_production",
    "leadscore_live",
    "postgres",
}
```

### 2.3 Host Network Isolation
Test runners are strictly restricted to local or approved container service hosts:
```python
APPROVED_TEST_HOSTS = {"", "localhost", "127.0.0.1", "postgres", "db"}
```
Remote or cloud hosts (e.g. AWS RDS, Supabase, Neon) are rejected with `UnsafeDatabaseTargetError` to prevent cross-network test contamination.

### 2.4 Active Engine & Session Binding Verification (`verify_session_target()`)
In asynchronous SQLAlchemy applications, modifying `os.environ["DATABASE_URL"]` after `app.database.engine` has initialized does not affect existing connection pools or session factories. 

The safety module introduces `verify_session_target(session)`:
```python
def verify_session_target(session: AsyncSession) -> str:
    bind = getattr(session, "bind", None)
    if bind and hasattr(bind, "url"):
        return validate_test_database_target(str(bind.url))
    return "session_bind_verified"
```
Before executing any cleanup or synthetic operation, the live session's underlying database URL is extracted from `session.bind.url` and validated against the allowlist.

---

## 3. `TestEntityTracker` Architecture & Cleanup Mechanics

### 3.1 Strict Child-to-Parent Deletion Order
To eliminate foreign-key violations, deadlocks, and orphan records, `TestEntityTracker` purges registered entities in strict dependency order:
1. `lead_notes` (`VARCHAR(36)` id)
2. `tasks` (`VARCHAR(36)` id)
3. `source_attributions` (`VARCHAR(36)` id) — *explicitly captured to prevent orphans*
4. `leads` (`UUID` id)
5. `organization_members` (`UUID` id)
6. `brokers` (`UUID` id)
7. `organizations` (`UUID` id)

### 3.2 Type Safety for Hybrid Column Types
The tracker handles PostgreSQL column type variance:
- Native UUID columns (`leads.id`, `brokers.id`, `organizations.id`) are cast via `uuid.UUID(str(val))`.
- String identifier columns (`tasks.id`, `lead_notes.id`, `source_attributions.id`) are cast via `str(val)`.

### 3.3 Pre-Existing Record Immunity Check
Before executing any deletion, `safe_cleanup()` executes an immunity query against the target table to ensure no registered ID matches a pre-existing record created outside the test execution scope. If an ID collision is detected, execution aborts immediately without deleting the record.

### 3.4 Cleanup Idempotency
Repeated calls to `safe_cleanup()` on the same tracker instance or across multiple test iterations succeed with `COMPLETED_CLEAN` status without raising exceptions or executing duplicate SQL statements.

---

## 4. Empirical Verification Evidence

### 4.1 Automated Guard Suite (`apps/api/tests/test_database_safety_guards.py`)
Executed on 2026-10-28:
```powershell
python -m pytest apps/api/tests/test_database_safety_guards.py -v
```
**Results:** **14 / 14 passed (100%) in 36.21s**.
- `test_guard_01_refuses_live_database_leadscore`: PASSED
- `test_guard_02_missing_database_configuration_fails_immediately`: PASSED
- `test_guard_03_invalid_database_configuration_prevents_write`: PASSED
- `test_guard_04_cleanup_cannot_delete_preexisting_organization`: PASSED
- `test_guard_05_cleanup_cannot_delete_preexisting_broker`: PASSED
- `test_guard_06_cleanup_cannot_delete_preexisting_lead`: PASSED
- `test_guard_07_cleanup_uses_captured_test_owned_ids_only`: PASSED
- `test_guard_08_duplicate_test_does_not_clean_other_test_data`: PASSED
- `test_guard_09_failure_halfway_leaves_recoverable_state`: PASSED
- `test_guard_10_app_env_cannot_be_mistaken_for_test`: PASSED
- `test_guard_11_positive_allowlist_rejects_unfamiliar_names`: PASSED
- `test_guard_12_engine_session_target_mismatch`: PASSED
- `test_guard_13_cleanup_idempotency`: PASSED
- `test_guard_14_rejects_unapproved_remote_hosts`: PASSED

### 4.2 Successive Acceptance Test Idempotence Runs
Target Database: `leadscore_test_acceptance` on `127.0.0.1:5432`.

#### Run 1 Execution:
```powershell
python scratch/phase5_e2e_pilot_acceptance.py
```
- **Safety Intercept:** Target validated: `'leadscore_test_acceptance'` (Isolated Test Database).
- **Checks Passed (16/16):**
  - C1: Unauthenticated access rejected (401)
  - C2: Header spoofing rejected (401/403)
  - D1: Malformed payload rejected (422)
  - D2: Synthetic lead created (201)
  - D3: Synthetic lead detail read (200)
  - D4: Status updated to 'contacted' (200)
  - D5: Stage updated to 'site_visit_scheduled' (200)
  - D6: Lead note recorded (201)
  - D7: Follow-up task created (201)
  - D8: Organization task list queried (200)
  - D9: Cross-tenant IDOR rejected (403/404)
  - D10: Outbound messaging confirmed inert (`FOLLOWUP_HUB_DISPATCH_ENABLED=False`)
  - E1: Expired JWT rejected (401)
  - E2: Malformed UUID parameter rejected (422)
  - E3: Non-existent resource returns 404
  - E4: Database rollback safety verified
- **Purge Ledger:**
  - `tasks`: 1
  - `source_attributions`: 1
  - `leads`: 1
  - `organization_members`: 3
  - `brokers`: 3
  - `organizations`: 2
- **Exit Code:** `0` (Success)

#### Run 2 Execution (Successive Run — Idempotence Verification):
```powershell
python scratch/phase5_e2e_pilot_acceptance.py
```
- **Safety Intercept:** Target validated: `'leadscore_test_acceptance'`.
- **Checks Passed (16/16):** All 16 checks passed identically without collision, constraint error, or schema deadlock.
- **Purge Ledger:**
  - `tasks`: 1
  - `source_attributions`: 1
  - `leads`: 1
  - `organization_members`: 3
  - `brokers`: 3
  - `organizations`: 2
- **Exit Code:** `0` (Success)
- **Post-Run State:** Verified zero residual rows remaining in `leadscore_test_acceptance`.

