# RUNBOOK — CELERY QUEUE BACKLOG & WORKER SATURATION
## Code: RB-CELERY-004 | Severity: P2

---

## 1. Symptoms & Triggers
- Queue job backlog depth exceeds 500 tasks.
- SLO `queue_processing_p95_ms` exceeds 5,000ms.

## 2. Diagnostics
1. Inspect pending Celery queues:
   ```bash
   celery -A app.core.celery_app inspect active
   ```
2. Check for hung tasks blocking worker concurrency threads.

## 3. Mitigation & Recovery
- Scale Celery worker instances from 4 to 8.
- Identify stuck tasks and ensure worker task timeouts are enforced (`time_limit=60s`).
- Route high-volume bulk imports to dedicated background worker pool.
