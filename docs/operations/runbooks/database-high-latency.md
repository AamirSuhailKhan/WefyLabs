# RUNBOOK — DATABASE HIGH LATENCY & SLOW QUERIES
## Code: RB-DB-002 | Severity: P1 / P2

---

## 1. Symptoms & Triggers
- Prometheus metric `db_slow_queries_total` incrementing rapidly.
- SLO `db_query_p99_ms` exceeds 100ms for 5 consecutive minutes.

## 2. Diagnostics
1. Query active long-running queries:
   ```sql
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
   FROM pg_stat_activity
   WHERE (now() - pg_stat_activity.query_start) > interval '2 seconds' AND state != 'idle';
   ```
2. Check PostgreSQL lock contention and replication lag.

## 3. Mitigation & Recovery
- Terminate rogue unindexed reporting queries (`pg_terminate_backend(pid)`).
- Ensure queries filter on composite index `(organization_id, created_at)`.
- Route read-heavy analytics queries to standby read replica.
