# STAGE1_WORKER_ROOT_CAUSE.md
# Phase 2C.6E — Celery Worker Root Cause Analysis

**Generated:** 2026-10-07T16:54:00+05:30  
**Classification:** PHASE_2C_6E_ROOT_CAUSE  
**Status:** ROOT CAUSE IDENTIFIED AND FIXED

---

## CLASSIFICATION

**Root Cause Class:** B + H — Worker crashes on startup at task execution level

The Celery worker process starts successfully, connects to Redis, and registers all tasks. However, every `autonomous_loop.process_sales_loop_event` task execution fails immediately with:

```
RuntimeError: There is no current event loop in thread 'MainThread'.
```

---

## PROVEN CAUSE

### Python 3.14 `asyncio.get_event_loop()` Breaking Change

The production runtime is **Python 3.14.0** (`pythoncore-3.14-64`).

Python 3.10 deprecated the implicit creation of a new event loop when `asyncio.get_event_loop()` is called from a thread without a running event loop. Python 3.14 makes this a **hard RuntimeError**.

### The Broken Pattern in `loop_tasks.py`

```python
# BROKEN — Python 3.14 raises RuntimeError here
loop = asyncio.get_event_loop()           # RuntimeError in Py3.14
if loop.is_running():
    future = asyncio.run_coroutine_threadsafe(_run(), loop)
    return future.result()
else:
    return asyncio.run(_run())
```

This pattern appeared in all 4 tasks:
- `process_sales_loop_event_task`
- `retry_failed_events_task`
- `evaluate_inactive_leads_task`
- `generate_daily_pilot_snapshots_task`

---

## EVIDENCE

### Worker Startup Log (broken run)

```
[16:51:40] celery@LAPTOP-MCIDT71B ready.
[16:51:40] Task autonomous_loop.process_sales_loop_event[f4f1f360...] received
[16:51:41] [LOOP_WORKER] Processing event: type=NEW_LEAD lead=6fc2be10...
[16:51:41] ERROR [LOOP_WORKER] Event processing error:
           There is no current event loop in thread 'MainThread'.
```

### Observed Metrics Before Fix

| Metric | Value |
|---|---|
| Worker process starts | YES |
| Worker connects to Redis | YES |
| Tasks registered | YES (autonomous_loop.process_sales_loop_event present) |
| Task received | YES |
| Task executes | NO — RuntimeError line 120 |
| Task retried | YES (3x max) |
| Queue depth (post-failure) | 0 (claimed but failed) |
| sales_loop_events COMPLETED | 3 (partial asyncio.run() success) |

---

## DEPLOYMENT ENVIRONMENT

| Property | Value |
|---|---|
| Deployment platform | Render.com (production) |
| Python version | 3.14.0 |
| Celery version | 5.6.3 |
| Redis | Upstash (TLS `rediss://`) |
| Celery app module | `app.celery_app.celery_app` |
| Queue for process_sales_loop_event | `sales-loop-orchestration` |

---

## CANONICAL WORKER COMMAND

From `render.yaml` (production) and `Procfile` (platform):

```bash
celery -A app.celery_app.celery_app worker \
  --loglevel=info --concurrency=4 \
  -Q sales-loop-orchestration,lead_queue,email_queue,...[all queues]
```

_End of Root Cause Analysis_
