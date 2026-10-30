# WEFYLABS PHASE 7 — CI/CD SAFETY GATES & AUTOMATED TEST PIPELINE AUDIT

**Project:** WefyLabs Autonomous Revenue OS / AI Real Estate CRM  
**Workflow File:** `.github/workflows/ci.yml`  
**Target Branches:** `main`, `level-1`, `level-2`, `level-3`  
**Static Gate Scanner:** `apps/api/scripts/audit_test_database_safety.py`  
**Guard Test Suite:** `apps/api/tests/test_database_safety_guards.py`  
**Acceptance Pilot Runner:** `apps/api/scripts/run_acceptance_pilot.py`  
**Audit Date:** 2026-10-28  

---

## 1. Executive Summary

Phase 7 updates the continuous integration pipeline (`.github/workflows/ci.yml`) to enforce multi-layered database safety and isolation gates. Automated pipelines are configured to prevent shared database mutations, enforce ephemeral test database isolation, verify single migration heads, and execute acceptance test scenarios with bounded entity cleanup before any code can merge.

---

## 2. Trigger Configuration & Scope

```yaml
on:
  push:
    branches: [ main, level-1, level-2, level-3 ]
  pull_request:
    branches: [ main, level-3 ]
```
Every pull request and push targeting release, development, or stabilization branches triggers the automated safety gate pipeline.

---

## 3. Pre-Test Static Safety Gates

### 3.1 Git Conflict Marker & Whitespace Gate
```yaml
- name: ── GIT INTEGRITY ── Check for whitespace errors or merge conflict markers
  run: git diff --check HEAD~1 || true
```
Prevents accidental merge conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) or whitespace corruption from entering the codebase.

### 3.2 Static Database Safety Audit Gate
```yaml
- name: ── DATABASE SAFETY GATE ── Static test isolation audit
  run: |
    python apps/api/scripts/audit_test_database_safety.py
```
- Scans all 228 test modules and scripts.
- Blocks builds if hardcoded connections to `leadscore` or unisolated `TRUNCATE` calls are detected.
- Fails with exit code `1` if any critical violation is found.

### 3.3 Alembic Single Head Gate
```yaml
- name: ── MIGRATION INTEGRITY ── Verify single Alembic head
  run: |
    HEAD_COUNT=$(poetry run python -m alembic heads 2>/dev/null | grep "(head)" | wc -l)
    if [ "${HEAD_COUNT}" -gt 1 ]; then
      echo "[FAIL] Multiple Alembic heads detected! Run 'alembic merge' to resolve."
      exit 1
    fi
```
Ensures schema migrations never fork or leave ambiguous revision heads.

---

## 4. Ephemeral Test Database Provisioning

The GitHub Actions runner provisions dedicated, isolated service containers:

```yaml
services:
  postgres:
    image: postgres:16-alpine
    env:
      POSTGRES_DB: leadscore_test
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - 5432:5432
  redis:
    image: redis:7-alpine
    ports:
      - 6379:6379
```

- **Target Database Name:** `leadscore_test` (explicitly allowed by `EXPLICIT_TEST_DATABASE_ALLOWLIST`).
- **Connection URL:** `postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_test`
- **Isolation Guarantee:** The ephemeral database is spun up fresh per workflow run and destroyed upon job termination, ensuring zero shared state.

---

## 5. Mandatory Test & Acceptance Stages

### Stage 1: Runtime Database Safety Guards
```yaml
- name: ── DATABASE SAFETY GUARDS ── Enforce runtime isolation & tracker
  env:
    ENV: testing
    DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_test
  run: |
    cd apps/api
    poetry run pytest tests/test_database_safety_guards.py -v
```
Executes all 14 database isolation guard tests, validating that live database names are intercepted, host restrictions are enforced, and cleanup routines are idempotent.

### Stage 2: Core Regression & Tenant Isolation Suite
```yaml
- name: Run Pytest Suite
  env:
    ENV: testing
    DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_test
  run: |
    cd apps/api
    poetry run pytest -v --tb=short
```
Executes tenant isolation, RBAC evaluation, Celery worker lifecycle, and core CRM unit test suites.

### Stage 3: CRM Acceptance Scenario with Bounded Cleanup
```yaml
- name: ── CRM ACCEPTANCE SUITE ── Isolated CRM dry run & cleanup
  env:
    ENV: testing
    DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_test
    TEST_DATABASE_URL: postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_test
    FOLLOWUP_HUB_DISPATCH_ENABLED: "false"
    WHATSAPP_ENABLED: "false"
  run: |
    cd apps/api
    poetry run python scripts/run_acceptance_pilot.py
```
Executes synthetic tenant onboarding, lead lifecycle, task follow-up, and error recovery against `leadscore_test`, verifying that all registered entities are cleanly purged via `TestEntityTracker`.

---

## 6. Pipeline Failure Conditions

A pull request or branch build is strictly blocked and cannot be merged if:
1. `audit_test_database_safety.py` detects any test file connecting to `leadscore`.
2. Any of the 14 database safety guard tests fail.
3. Multiple Alembic migration heads exist.
4. An acceptance test leaves residual synthetic entities or fails during cleanup.
5. Outbound messaging is enabled in test configurations.
6. Bandit or detect-secrets identifies security vulnerabilities or leaked secrets.

