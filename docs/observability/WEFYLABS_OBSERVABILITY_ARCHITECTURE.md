# WefyLabs Observability Architecture
## Master Build 12 — Canonical Reference

> **Version:** Build 12  
> **Status:** ✅ Production  
> **Last Updated:** 2026-09-27

---

## 1. Principles

| Principle | Rule |
|---|---|
| **No Fabrication** | Every metric, latency, and availability claim must have a source and calculation method |
| **No Duplicate Stacks** | Converge into one structured logging, one tracing, one metrics system |
| **Correlation-First** | Every log, span, and metric shares `request_id`, `correlation_id`, `trace_id` |
| **Fail-Closed** | Unknown tenant = REJECT. Unknown SLO = NO_DATA, not assumed-healthy |
| **Real Timestamps** | MTTR, TTD, RTO all derive from actual `datetime` event timestamps |

---

## 2. Architecture Overview

```
 ┌──────────────────────────────────────────────────────────────────────┐
 │                     Incoming Request                                  │
 └───────────────────────────┬──────────────────────────────────────────┘
                             │
              ┌──────────────▼──────────────┐
              │   Middleware: Trace Context  │  ← Parses W3C traceparent
              │   Sets: request_id,          │    Generates: trace_id, span_id
              │         correlation_id,      │    Injects into ContextVar
              │         trace_id, org_id     │
              └──────────────┬──────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
  ┌─────────────┐   ┌──────────────┐   ┌──────────────────┐
  │ JSON Logger │   │    Tracer    │   │   Prometheus      │
  │ (logging/)  │   │ (tracing/)  │   │   Collector       │
  │             │   │             │   │   (metrics/)       │
  │ Structured  │   │ W3C Spans   │   │ HTTP / DB / Redis  │
  │ JSON to     │   │ auto-nested │   │ AI / Queue / Search│
  │ stdout/OTEL │   │ by context  │   │ per-org AI costs   │
  └─────────────┘   └──────────────┘   └──────────────────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │ correlated by trace_id
              ┌──────────────▼──────────────┐
              │    Observability Platform    │
              │  (modules/observability/)    │
              ├──────────────────────────────┤
              │  SLOManager     → 6 SLOs     │
              │  AIEvaluator    → 4 dims     │
              │  IncidentMgr    → P0–P4      │
              │  HealthAggregat → probes     │
              │  BenchmarkEngine→ p95/p99    │
              │  ChaosEngine    → DR drills  │
              └──────────────────────────────┘
```

---

## 3. Module Inventory

| Module | Path | Responsibility |
|---|---|---|
| **JSON Logger** | `app/modules/logging/json_logger.py` | Structured JSON logs with ContextVar propagation |
| **Tracer** | `app/modules/tracing/tracer.py` | W3C traceparent, nested spans, duration recording |
| **Prometheus Collector** | `app/modules/metrics/prometheus_collector.py` | HTTP, DB, Redis, Queue, Search, AI metrics |
| **SLO Manager** | `app/modules/observability/slo_manager.py` | 6 canonical SLOs with rolling-window evaluation |
| **AI Evaluator** | `app/modules/observability/ai_evaluator.py` | Golden dataset, 4-dimension quality scoring |
| **Incident Manager** | `app/modules/observability/incident_manager.py` | P0–P4 lifecycle, TTD/TTR from real timestamps |
| **Health Aggregator** | `app/modules/observability/health_aggregator.py` | Pluggable probes, 10s cache, per-component status |
| **Benchmark Engine** | `app/modules/observability/benchmark.py` | Real-operation p95/p99 measurement |
| **Chaos Engine** | `app/modules/observability/benchmark.py` | DR drills with CHAOS_ENABLED safety gate |
| **Circuit Breaker** | `app/modules/reliability/circuit_breaker.py` | CLOSED→OPEN→HALF_OPEN with async/sync fallback |

---

## 4. Canonical SLOs

All SLOs tracked by `SLOManager` with rolling-window measurements. Values are never assumed — they require recorded samples.

| SLO Name | Target | Unit | Window | Direction |
|---|---|---|---|---|
| `api_availability` | ≥ 99.9% | percent | 30 days | must stay **above** |
| `api_p99_latency_ms` | ≤ 500 ms | ms | 1 hour | must stay **below** |
| `ai_response_p95_ms` | ≤ 3 000 ms | ms | 1 hour | must stay **below** |
| `db_query_p99_ms` | ≤ 100 ms | ms | 1 hour | must stay **below** |
| `queue_processing_p95_ms` | ≤ 5 000 ms | ms | 1 hour | must stay **below** |
| `error_rate` | < 1% | percent | 1 hour | must stay **below** |

### SLO Status Definitions

| Status | Meaning |
|---|---|
| `MEETING` | Within target AND > 20% error budget remaining |
| `AT_RISK` | Within target BUT ≤ 20% error budget remaining |
| `BREACHED` | Outside target — error budget exhausted |
| `NO_DATA` | No samples recorded yet — **not assumed healthy** |

---

## 5. AI Evaluation Pipeline

### Evaluation Dimensions

| Dimension | Threshold | Description |
|---|---|---|
| Relevance | ≥ 0.75 | Response addresses the prompt |
| Faithfulness | ≥ 0.80 | Claims grounded in retrieved context |
| Hallucination | ≥ 0.90 | Absence of fabricated entities (higher = better) |
| Safety | ≥ 0.95 | Passes WefyLabs safety policy |
| Latency | ≤ 3 000 ms | Within AI response SLO |
| Cost | ≤ $0.01 | Within per-request budget |

### Golden Dataset

- Location: `GoldenSample` objects loaded via `ai_evaluator.load_golden_dataset()`
- Format: `{sample_id, prompt, context, expected_answer, tags, version}`
- Versioned: each dataset tagged with `version` string (e.g. `"v1.0"`)
- Test mode: `AIEvaluator(test_mode=True)` uses deterministic scores for CI

---

## 6. Incident Intelligence

### Severity Levels

| Level | Meaning | Response Target |
|---|---|---|
| P0 | Complete outage | Page immediately |
| P1 | Critical degradation | Page within 5 min |
| P2 | Significant impact | Alert within 15 min |
| P3 | Minor impact | Ticket within 1 hr |
| P4 | Informational | Log only |

### Lifecycle

```
OPEN → ACKNOWLEDGED → INVESTIGATING → RESOLVED → CLOSED
```

### Key Invariants

- **TTD** (Time-to-Detect): `acknowledged_at` − `created_at` — from real ISO timestamps
- **TTR** (Time-to-Resolve): `resolved_at` − `created_at` — from real ISO timestamps  
- **MTTR** in report: mean of all real TTR values — labelled `"mttr_source": "derived_from_event_timestamps"`
- **Dedup**: same title within 5-minute window returns existing open incident

### Auto-Detection

| Trigger | Method | Severity |
|---|---|---|
| SLO breach | `detect_slo_breach(slo_name, current, target)` | P1 |
| Error rate spike ≥ 5% | `detect_error_spike(error_rate_pct)` | P0 |

---

## 7. Health Aggregation

### Probe Registration

```python
agg = HealthAggregator()
agg.register("database", _check_db_probe)   # async def → ComponentHealth
agg.register("redis",    _check_redis_probe)
health = await agg.check_all()
```

### Status Rules

| Condition | Overall Status |
|---|---|
| All components `HEALTHY` | `HEALTHY` |
| Any component `UNHEALTHY` | `UNHEALTHY` |
| Any `DEGRADED`, none `UNHEALTHY` | `DEGRADED` |

- Cache TTL: **10 seconds** (avoids probe stampede)
- Probe timeout: **5 seconds** (times out → `UNHEALTHY`)

---

## 8. Circuit Breaker

State machine: `CLOSED` → `OPEN` → `HALF_OPEN` → `CLOSED`

| Config | Default |
|---|---|
| `failure_threshold` | 5 consecutive failures |
| `recovery_time_seconds` | 30 s |

**Fallback safety**: `_invoke_fallback` distinguishes async coroutine functions from sync callables using `inspect.iscoroutinefunction` — prevents `TypeError: 'str' object can't be awaited`.

---

## 9. Chaos / DR Drills

- **Safety gate**: `ChaosEngine(enabled=False)` by default. Set `enabled=True` only in staging.
- Disabled engine returns `outcome="ABORTED"` — never injects failures silently.
- **RTO** recorded from actual recovery timing — not estimated.
- **Drill types**: `database_failover`, `cache_eviction`, `ai_provider_outage`, `worker_restart`

---

## 10. Correlation Protocol

Every log, span, and metric must share:

```json
{
  "request_id":      "req-uuid4",
  "correlation_id":  "corr-uuid4",
  "trace_id":        "32-hex-chars (W3C)",
  "span_id":         "16-hex-chars (W3C)",
  "organization_id": "org-uuid",
  "user_id":         "user-uuid"
}
```

Set via `set_trace_context(...)` in middleware; propagated automatically via `ContextVar`.

---

## 11. Build 12 Test Results

| Domain | Tests | Status |
|---|---|---|
| MB12-OBS: Structured Logging | 8 | ✅ 8/8 |
| MB12-OBS: Distributed Tracing | 6 | ✅ 6/6 |
| MB12-OBS: Prometheus Metrics | 4 | ✅ 4/4 |
| MB12-SLO: SLO Manager | 8 | ✅ 8/8 |
| MB12-EVAL: AI Evaluation | 8 | ✅ 8/8 |
| MB12-INC: Incident Manager | 8 | ✅ 8/8 |
| MB12-HLTH: Health Aggregator | 6 | ✅ 6/6 |
| MB12-PERF: Benchmark Engine | 6 | ✅ 6/6 |
| MB12-CB: Circuit Breaker | 6 | ✅ 6/6 |
| MB12-DRLL: Chaos/DR Drills | 4 | ✅ 4/4 |
| **TOTAL** | **64** | ✅ **64/64** |

---

## 12. WefyLabs Build Status

```
01 Foundation / Production Truth                  ✅
02 Lead Ingestion / Identity Graph                ✅
03 Communication / WhatsApp / Conversation OS     ✅
04 Property / Inventory / Matching                ✅
05 AI Gateway / RAG / Knowledge / Memory          ✅
06 AI Sales Agent / Safe Execution                ✅
07 Follow-Up / NBA / Workflow                     ✅
08 Sales Pipeline / Opportunity / Booking         ✅
09 Revenue Intelligence / Attribution / Forecast  ✅
10 World-Class UX / Command Center / Mobile       ✅
11 Enterprise Security / Compliance / Governance  ✅
12 Observability / AI Eval / Reliability / Ops    ✅  ← COMPLETE
```
