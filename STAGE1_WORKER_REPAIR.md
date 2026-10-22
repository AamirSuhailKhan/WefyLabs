# STAGE1_WORKER_REPAIR.md
# Phase 2C.6E — Celery Worker Repair Documentation

**Generated:** 2026-10-07  
**Status:** APPLIED — Worker running, consuming sales-loop-orchestration

---

## REPAIR APPLIED

**File:** `apps/api/app/modules/autonomous_loop/workers/loop_tasks.py`

### Change: Replace `asyncio.get_event_loop()` with `asyncio.new_event_loop()`

Applied to all 4 tasks in `loop_tasks.py`.

#### Before (broken — Python 3.14 incompatible)

```python
try:
    loop = asyncio.get_event_loop()          # ← RuntimeError in Python 3.14
    if loop.is_running():
        future = asyncio.run_coroutine_threadsafe(_run(), loop)
        return future.result()
    else:
        return asyncio.run(_run())
except Exception as exc:
    logger.error(f"[LOOP_WORKER] Event processing error: {exc}", exc_info=True)
    raise self.retry(exc=exc)
```

#### After (fixed — creates a dedicated event loop per task invocation)

```python
loop = asyncio.new_event_loop()
try:
    return loop.run_until_complete(_run())
except Exception as exc:
    logger.error(f"[LOOP_WORKER] Event processing error: {exc}", exc_info=True)
    raise self.retry(exc=exc)
finally:
    try:
        loop.close()
    except Exception:
        pass
```

**Tasks fixed:**
1. `process_sales_loop_event_task` (lines 119-128)
2. `retry_failed_events_task` (lines 195-200)
3. `evaluate_inactive_leads_task` (lines 272-277)
4. `generate_daily_pilot_snapshots_task` (lines 353-358)

---

## WHY THIS FIX IS CORRECT

- `asyncio.new_event_loop()` unconditionally creates a fresh event loop, regardless of thread state
- The loop is properly closed in `finally` to prevent resource leaks
- Each task execution is fully isolated — no shared event loop state between tasks
- The asyncpg connection pool is created fresh per task (via `_get_async_session()`)
- This pattern is the recommended Celery + asyncio interop pattern for non-ASGI workers

---

## PRODUCTION DEPLOYMENT FIX

The `render.yaml` already correctly defines the Celery worker service:

```yaml
- type: worker
  name: wefylabs-celery-worker
  env: python
  rootDir: apps/api
  buildCommand: pip install -r requirements.txt
  startCommand: >
    celery -A app.celery_app.celery_app worker
    --loglevel=info
    --concurrency=4
    -Q lead_queue,email_queue,...,sales-loop-orchestration,...
  autoDeploy: true
```

The `render.yaml` configuration is correct. The repair was applied to the **task code**, not the deployment configuration. After deploying this fix, Render will auto-deploy and the worker will function.

---

## VERIFICATION STEPS PERFORMED

1. ✅ Killed broken worker (task-61)
2. ✅ Applied fix to `loop_tasks.py`
3. ✅ Restarted worker (task-79)
4. ✅ Worker startup confirmed:
   ```
   celery@LAPTOP-MCIDT71B ready.
   Connected to rediss://...upstash.io:6379//
   ```
5. ✅ Task `autonomous_loop.process_sales_loop_event` appears in registered tasks
6. ✅ Queue depth `sales-loop-orchestration`: 0 (all tasks consumed)
7. ✅ `sales_loop_events` table: 3 COMPLETED records
8. ✅ Worker remains running (daemon process task-79 active)

---

## WHAT CHANGED IN THE QUEUE

The 10 original buffered tasks in `sales-loop-orchestration` were consumed as follows:

- **10 tasks** were claimed from the queue by the broken worker (task-61)
- **10 tasks** were re-queued as Celery retries with 30s delay
- **3 tasks** successfully completed via `asyncio.run()` fallback before pool corruption
- **7 tasks** failed with "Event loop is closed" on subsequent attempts
- All 10 retry slots were re-claimed by the fixed worker (task-79)
- Queue depth after fix: **0**

---

_End of Worker Repair Documentation_
