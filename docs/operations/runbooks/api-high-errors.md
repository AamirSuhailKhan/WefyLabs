# RUNBOOK — API HIGH ERROR RATE SPIKE (5XX)
## Code: RB-API-001 | Severity: P0 / P1

---

## 1. Symptoms & Triggers
- Prometheus alert: `http_requests_total{status=~"5.."}` exceeds 1% of total requests over 3 minutes.
- SLO `error_rate` status transitions to `AT_RISK` or `BREACHED`.

## 2. Immediate Diagnostic Steps
1. Inspect live structured JSON logs for stack traces:
   ```bash
   python -m pytest apps/api/tests/test_master_build_12_observability_reliability.py -k "test_liveness"
   ```
2. Check database connection pool and query health via `GET /health/ready`.
3. Review recent git deployment commit or configuration change.

## 3. Mitigation & Recovery
- **If caused by recent deployment:** Trigger automated rollback to previous release tag.
- **If caused by database connection exhaustion:** Increase pool size or restart hung connection pool.
- **If caused by external provider timeout:** Enable circuit breaker fallback mode.
