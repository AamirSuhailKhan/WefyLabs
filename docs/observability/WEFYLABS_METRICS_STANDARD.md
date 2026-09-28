# WEFYLABS — METRICS & PROMETHEUS STANDARD
## Master Build 12 — Production Standard

**Status:** ✅ PRODUCTION CANONICAL  
**Module:** `apps/api/app/modules/metrics/prometheus_collector.py`  
**Endpoint:** `GET /metrics` and `GET /api/v1/metrics`  

---

## 1. Golden Signals & RED Architecture

WefyLabs observes all critical tiers using the **RED** (Rate, Errors, Duration) framework and the **Four Golden Signals** (Latency, Traffic, Errors, Saturation):

| Signal | Metric Name | Type | Description |
| :--- | :--- | :---: | :--- |
| **Rate** | `http_requests_total` | Counter | Total HTTP requests by `method`, `path`, `status` |
| **Duration** | `http_request_duration_avg_seconds` | Gauge | Moving average duration in seconds |
| **Errors** | `http_requests_total{status=~"5.."}` | Counter | Server-side 5xx error count |
| **Saturation** | `db_queries_total`, `db_slow_queries_total` | Counter | Query volume and slow queries exceeding 100ms |
| **Cache Efficiency**| `redis_cache_hits_total`, `redis_cache_misses_total`| Counter | Redis cache hit vs miss ratio |
| **AI Workload** | `ai_prompt_tokens_total`, `ai_completion_tokens_total`| Counter | AI token consumption per `organization_id` |
| **AI Unit Economics**| `ai_cost_usd_total` | Counter | Accumulated AI expenditure per `organization_id` in USD |

---

## 2. Cardinality Safety Rules

1. **Strictly Prohibited Labels:** Never use customer-specific high-cardinality values as metric dimensions:
   - ❌ `lead_id`
   - ❌ `phone_number`
   - ❌ `email`
   - ❌ `conversation_id`
   - ❌ `trace_id`
2. **Permitted Labels:**
   - ✅ `method` (GET, POST, PUT, DELETE)
   - ✅ `status` (200, 201, 400, 401, 403, 404, 500)
   - ✅ `path` (parameterized route, e.g. `/api/v1/leads`)
   - ✅ `organization_id` (bounded tenant identifier for multi-tenant billing)

---

## 3. Exposition Format

Metrics are exported in OpenMetrics / Prometheus standard text format:
```prometheus
# HELP http_requests_total Total number of HTTP requests processed
# TYPE http_requests_total counter
http_requests_total{method="GET",path="/health/live",status="200"} 42
http_requests_total{method="POST",path="/api/v1/leads",status="201"} 18

# HELP http_request_duration_avg_seconds Average request duration
# TYPE http_request_duration_avg_seconds gauge
http_request_duration_avg_seconds 0.0425

# HELP ai_cost_usd_total Total AI spend in USD per org
# TYPE ai_cost_usd_total counter
ai_cost_usd_total{organization_id="org-enterprise-01"} 0.024500
```
