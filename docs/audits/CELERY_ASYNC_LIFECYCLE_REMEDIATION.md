# WEFYLABS CRM — CELERY ASYNC LIFECYCLE REMEDIATION AUDIT REPORT

**Date**: 2026-10-27  
**System**: WefyLabs CRM / Autonomous Revenue OS  
**Status**: `VERIFIED FIXED`  
**Target Architecture**: FastAPI, Celery (Prefork), SQLAlchemy 2.0 (asyncpg), PostgreSQL 16 (pgvector), Redis 7

---

## A. Original Root Cause

### 1. Proven Primary Root Cause: Ephemeral Event Loop Closure Corrupting SQLAlchemy Connection Pool
In asynchronous Python applications using SQLAlchemy with `asyncpg`, each underlying database connection is an asyncpg protocol connection tied directly to the `asyncio` event loop on which it was created.

In the previous codebase, individual Celery tasks executed asynchronous code by running helper patterns such as:
```python
def run_async(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
```
When a task completed, `loop.close()` was called. However, SQLAlchemy's global connection pool (`QueuePool` on `engine`) maintained pooled connection objects that were checked back into the pool. These connections retained internal references to the closed event loop and closed sockets.

When the worker process subsequently picked up another task (or when another periodic beat job executed), SQLAlchemy attempted to check out a pooled connection. During `pool_pre_ping`, SQLAlchemy executed a ping (`SELECT 1`) or connection health check using `asyncpg`. Because the connection's bound event loop was closed, `asyncpg` threw:
```
RuntimeError: Event loop is closed
```
The exception propagated through `sqlalchemy.pool.base`, `asyncpg.connection`, and `asyncio.base_events`.

### 2. Secondary Contributing Factors
- **`asyncio.get_event_loop()` Deprecation & Stale Loop Retrieval**:
  Several task modules (e.g. `calendar_tasks.py`) previously invoked `asyncio.get_event_loop()`. In Python 3.10+, `get_event_loop()` without an active running loop on the thread returns the thread's previously set (and closed) loop or warns `DeprecationWarning: There is no current event loop`. When passed coroutines, it produced `RuntimeWarning: coroutine was never awaited` followed by `RuntimeError: Event loop is closed`.
- **Misregistered Celery Beat Task Names**:
  In `app/modules/crm_intelligence/workers/intelligence_tasks.py`, tasks were decorated with relative names (`@celery_app.task(name="monitor_sla_breaches_task")`), whereas `celery_app.conf.beat_schedule` registered them with full dotted module paths (`app.modules.crm_intelligence.workers.intelligence_tasks.monitor_sla_breaches_task`). This caused `KeyError` during task routing.
- **Missing Logger Definitions**:
  In `app/modules/predictive/workers/predictive_tasks.py` and `app/modules/memory/workers/memory_tasks.py`, `logger = logging.getLogger(__name__)` was missing, causing `NameError: name 'logger' is not defined` during task execution.
- **Tenant Context Coercion in Inactive Lead Scanning**:
  `autonomous_loop.evaluate_inactive_leads` was passed `tenant_id="__all__"`. The query in `loop_tasks.py` attempted to cast `"__all__"` directly to a PostgreSQL UUID (`Lead.organization_id == uuid.UUID(tenant_id)`), raising `asyncpg.exceptions.DataError: invalid input for query argument: '__all__'`.
- **Insecure Tenant Fallback**:
  `loop_tasks.py` previously fell back to `'default'` when deriving tenant context, which triggered tenant boundary security alarms.

---

## B. Files Changed

| File Path | Description of Change |
|---|---|
| `apps/api/app/core/async_runner.py` | Created centralized, thread-safe persistent event loop runner using `threading.local()`. Disposes `engine.sync_engine.dispose()` on loop replacement or worker reset, preventing stale pooled connections. |
| `apps/api/app/celery_app.py` | Registered Celery signals (`worker_process_init` and `worker_process_shutdown`) to bind and cleanly tear down thread-local worker event loops and dispose inherited database pools post-fork. |
| `apps/api/app/modules/autonomous_loop/workers/loop_tasks.py` | Fixed `__all__` tenant query; implemented strict fail-closed tenant validation; enforced deterministic tenant context resolution from `lead.organization_id` or `lead.broker_id` without defaulting to `"default"`. |
| `apps/api/app/modules/crm_intelligence/workers/intelligence_tasks.py` | Prefixed all 6 tasks with fully qualified paths matching Celery Beat schedule; standardized to `app.core.async_runner.run_async`. |
| `apps/api/app/modules/predictive/workers/predictive_tasks.py` | Defined missing `logger = logging.getLogger(__name__)`; migrated all tasks to centralized `_run_async`. |
| `apps/api/app/modules/memory/workers/memory_tasks.py` | Defined missing `logger = logging.getLogger(__name__)`; migrated tasks to centralized `_run_async`. |
| `apps/api/app/modules/workflow/workers/workflow_tasks.py` | Restored missing `logger = logging.getLogger(__name__)`; standardized runner. |
| `apps/api/app/modules/calendar/workers/calendar_tasks.py` | Migrated tasks from legacy `get_event_loop()` to `run_async`. |
| `apps/api/app/modules/conversation_intelligence/workers/response_tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/discovery/workers/discovery_tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/follow_up/tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/identity_resolution/workers/identity_tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/intelligence/tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/knowledge/workers/knowledge_tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/lead_acquisition/tasks/acquisition_tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/lead_intelligence/workers/scoring_tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/lead_qualification/tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/property_recommendation/tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/prospect_intelligence/workers/prospect_tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/modules/revenue_autopilot/tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/tasks/followup_tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/tasks/onboarding_tasks.py` | Migrated tasks to `run_async`. |
| `apps/api/app/tasks/queue_workers.py` | Migrated tasks to `run_async`. |
| `apps/api/Dockerfile` | Optimized image inheritance to build from existing base layer, preventing Debian mirror network timeouts while ensuring latest code is baked into runtime images. |
| `apps/api/tests/test_celery_worker_lifecycle.py` | Created 9 automated regression tests validating runner lifecycle, pool disposal, exception propagation, thread isolation, task names, and fail-closed tenant validation. |

---

## C. Final Implementation

### Architecture of `app.core.async_runner.run_async`
1. **Thread-Local Persistent Event Loop**:
   - Uses `threading.local()` to store an open `asyncio.AbstractEventLoop` per OS worker thread / prefork child.
   - If the thread has no loop or if the existing loop is closed, creates a new event loop and calls `engine.sync_engine.dispose()` to ensure no connections created on a dead loop are reused.
   - Sets the active loop via `asyncio.set_event_loop(loop)`.
   - Never closes the loop after coroutine execution: `loop.run_until_complete(coro)` executes while the loop remains open for subsequent tasks.
2. **Signal-Hooked Worker Lifecycle**:
   - `worker_process_init` signal calls `reset_worker_event_loop()`. This disposes any parent-process inherited connection pool immediately after process fork, giving the child worker clean pool state.
   - `worker_process_shutdown` signal calls `close_worker_event_loop()`. This cleanly disposes the pool and closes the persistent loop when the worker process terminates.
3. **Session & Pool Isolation**:
   - Every Celery task maintains scoped `async with async_session_factory() as session:` blocks.
   - No `AsyncSession` is shared across tasks or threads.
   - The global `QueuePool` on SQLAlchemy's engine is maintained, keeping performance intact for the API while ensuring connection health in Celery workers.

---

## D. Regression Evidence

### 1. Focused Lifecycle Regression Tests
Command:
```powershell
& "C:\Users\aamir\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m pytest "apps/api/tests/test_celery_worker_lifecycle.py" -v
```
**Results**:
- `test_persistent_event_loop_across_sequential_calls`: **PASSED**
- `test_exception_propagation_and_loop_integrity`: **PASSED**
- `test_thread_isolation_concurrent_runners`: **PASSED**
- `test_nested_or_active_loop_compatibility`: **PASSED**
- `test_reset_worker_event_loop_lifecycle`: **PASSED**
- `test_crm_intelligence_task_registration_names`: **PASSED**
- `test_evaluate_inactive_leads_handles_all_and_uuid_tenant`: **PASSED**
- `test_tenant_security_fail_closed_invalid_tenant`: **PASSED**
- `test_retry_failed_events_handles_all_and_specific_tenant`: **PASSED**

**Outcome**: **9 passed in 2.58s** (100% pass rate).

### 2. Targeted Cross-Cutting Regression Suite
Command:
```powershell
& "C:\Users\aamir\AppData\Local\Python\pythoncore-3.14-64\python.exe" -m pytest `
  "apps/api/tests/test_celery_worker_lifecycle.py" `
  "apps/api/tests/test_part35_celery.py" `
  "apps/api/tests/test_docker_import_stability.py" `
  "apps/api/tests/test_tenant_isolation_security.py" `
  "apps/api/tests/test_master_build_11_tenant_security.py" `
  "apps/api/tests/test_part12_followup_dispatch_worker.py" -v
```
**Outcome**: **46 passed in 78.90s** (0 failed, 0 skipped, 0 errored).
- Verified Celery task registration and Beat schedules.
- Verified Docker import stability for all modules.
- Verified tenant isolation, IDOR rejection, and RBAC security boundaries.
- Verified FollowUp dispatch worker idempotency and channel gating.

---

## E. Runtime Verification (Live Docker Stack)

### 1. Container Status
```
NAME                      IMAGE                        STATUS
leadscore_api             crmrealstate-api             Up (healthy)
leadscore_celery_beat     crmrealstate-celery_beat     Up
leadscore_celery_worker   crmrealstate-celery_worker   Up
leadscore_postgres        pgvector/pgvector:pg16       Up (healthy)
leadscore_redis           redis:7-alpine               Up (healthy)
```

### 2. API Health Check (`/health`)
Endpoint: `http://127.0.0.1:8000/health`  
Output:
```json
{
  "status": "healthy",
  "service": "WefyLabs API",
  "version": "1.0.0",
  "environment": "development",
  "dependencies": {
    "database": {
      "status": "ok",
      "latency_ms": 2.17,
      "migration_head": "0048_schema_reconciliation_parity"
    },
    "redis": {
      "status": "ok",
      "latency_ms": 2.17
    },
    "gemini": {
      "status": "configured",
      "provider": "google-gemini",
      "model": "gemini-3.6-flash"
    },
    "smtp": {
      "status": "not_configured"
    }
  },
  "outbox_queue": {
    "pending": 0,
    "failed": 0,
    "dead_letter": 0
  },
  "security_metrics": {
    "AUTH_FAILURE": 0,
    "AUTHZ_FAILURE": 0,
    "RATE_LIMIT": 0,
    "INVALID_WEBHOOK": 0,
    "SUSPICIOUS_INPUT": 0,
    "TENANT_BOUNDARY_VIOLATION": 0,
    "AI_POLICY_REJECTION": 0,
    "SYSTEM_SECURITY_ERROR": 0
  }
}
```

### 3. Live Celery Worker Task Execution (Zero Errors)
Observed in live Docker container logs (`leadscore_celery_worker`) across multiple continuous polling intervals:
- `app.modules.revenue_autopilot.tasks.scan_all_tenants_revenue_opportunities_task`: **SUCCESS** (scanned 8 tenants)
- `app.modules.revenue_autopilot.tasks.evaluate_revenue_opportunities_task` (8 sequential executions for all 8 tenants): **SUCCESS**
- `app.modules.calendar.workers.calendar_tasks.cleanup_expired_holds_task`: **SUCCESS**
- `app.modules.calendar.workers.calendar_tasks.process_due_reminders_task`: **SUCCESS**
- `app.modules.crm_intelligence.workers.intelligence_tasks.monitor_sla_breaches_task`: **SUCCESS**
- `autonomous_loop.evaluate_inactive_leads`: **SUCCESS**
- `autonomous_loop.retry_failed_events`: **SUCCESS**
- `app.tasks.followup_tasks.evaluate_followups`: **SUCCESS**
- `app.tasks.followup_tasks.escalate_stale_lead`: **SUCCESS**
- `follow_up.dispatch_due_executions`: **SUCCESS**

**Crucial Check**: Zero occurrences of `RuntimeError: Event loop is closed`, zero `NameError`, and zero unhandled exceptions after rebuild and container recreation.

---

## F. Database Integrity & Data Preservation

### 1. Persistent Storage Safety
- No volumes were removed or recreated (`crmrealstate_postgres_data` volume preserved).
- No destructive SQL commands (`TRUNCATE`, `DROP DATABASE`, etc.) were executed.

### 2. Alembic Revision Check
Command: `docker compose exec api alembic current -v`
```
Current revision(s) for postgresql+asyncpg://postgres:***@postgres:5432/leadscore:
Rev: 0048_schema_reconciliation_parity (head)
Parent: 0047_webhook_event_claims
```
Command: `docker compose exec api alembic check`
```
No new upgrade operations detected.
```
Schema is at parity with ORM models.

### 3. Record Count Verification
Query:
```sql
SELECT 'brokers' as tbl, count(*) FROM brokers
UNION ALL SELECT 'leads', count(*) FROM leads
UNION ALL SELECT 'conversations', count(*) FROM conversations
UNION ALL SELECT 'payment_orders', count(*) FROM payment_orders;
```
Results:
- `brokers`: 8 (100% preserved)
- `leads`: 4 (100% preserved)
- `conversations`: 5 (100% preserved)
- `payment_orders`: 0 (100% preserved)

---

## G. Security Verification

1. **Tenant Context Isolation**:
   - `autonomous_loop.evaluate_inactive_leads` securely scans only leads belonging to the authorized tenant UUID. When run for `__all__`, it resolves the lead's true `organization_id` or `broker_id` and never falls back to `'default'`.
   - String injection attacks in `tenant_id` fail closed with `ValueError("Invalid tenant_id format: expected UUID or '__all__'")`.
2. **Credential Redaction**:
   - No credentials, tokens, or API keys were printed or added to source code.
   - The compromised Gemini key from past terminal sessions must be rotated in the Google AI Studio console prior to public launch.

---

## H. Remaining Issues

| Issue | Severity | Description | Action Required |
|---|---|---|---|
| Gemini API Key Compromise | Medium | A Google Gemini API key was exposed in historical terminal logs. | Rotate key in Google Cloud / AI Studio console and update `.env`. |
| SMTP Provider Configuration | Low | SMTP status is reported as `not_configured`. | Configure production SMTP credentials when email dispatch is enabled. |
| Dockerfile Debian Package Mirror | Low | Debian package repositories occasionally throttle or time out during fresh base builds on slow connections. | Use pre-built base image `crmrealstate-api:latest` or private container registry for CI/CD builds. |

---

## I. Readiness Assessment

**Final Status**: `VERIFIED FIXED`

### Summary of Criteria Verification:
1. Actual root cause identified and addressed: **YES** (persistent thread-local loop + post-fork pool disposal).
2. Focused regression tests pass: **YES** (9/9 passed).
3. Broader relevant regression tests pass: **YES** (46/46 passed).
4. Real asyncpg/SQLAlchemy integration tested: **YES** (exercised against live PostgreSQL 16 container).
5. Final Docker images rebuilt with corrected code: **YES** (`crmrealstate-api`, `crmrealstate-celery_worker`, `crmrealstate-celery_beat`).
6. Recreated worker executes sequential database tasks without error: **YES** (verified live in Docker).
7. Celery Beat dispatches and worker consumes tasks: **YES** (multiple scheduled tasks verified).
8. Tenant isolation preserved and hardened: **YES** (strict UUID validation and scoping verified).
9. API, PostgreSQL, and Redis remain healthy: **YES** (`/health` returns healthy).
10. Alembic head matches database without schema drift: **YES** (`0048_schema_reconciliation_parity`).
11. Persistent database volume and records preserved: **YES** (8 brokers, 4 leads, 5 conversations).
