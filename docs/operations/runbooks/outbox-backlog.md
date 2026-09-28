# RUNBOOK — TRANSACTIONAL OUTBOX BACKLOG & LAG
## Code: RB-OUTBOX-008 | Severity: P2

---

## 1. Symptoms & Triggers
- `outbox_events` table contains > 1,000 pending records.
- Event propagation lag p95 exceeds 30 seconds.

## 2. Diagnostics
1. Query outbox status counts:
   ```sql
   SELECT status, count(*) FROM outbox_events GROUP BY status;
   ```
2. Check for dead-letter events with repeated serialization errors.

## 3. Mitigation & Recovery
- Increase outbox poller concurrency and batch size from 50 to 200.
- Isolate poison-pill events to `DEAD_LETTER` queue for manual inspection.
- Restart outbox dispatcher worker process.
