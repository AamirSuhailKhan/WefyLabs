# RUNBOOK — REDIS OUTAGE & CACHE RESILIENCE
## Code: RB-REDIS-003 | Severity: P1

---

## 1. Symptoms & Triggers
- `GET /health/ready` returns 503 with `"cache": "error"`.
- Redis connection timeout / ConnectionRefusedError logged.

## 2. Diagnostics
1. Test direct Redis PING:
   ```bash
   redis-cli -u $REDIS_URL PING
   ```
2. Check memory usage and eviction statistics (`INFO memory`).

## 3. Mitigation & Recovery
- Application automatically operates in DB-direct degraded mode.
- If Redis instance crashed, trigger container/service restart.
- Upon reconnection, cache warms automatically; zero durable data loss as state is stored in PostgreSQL.
