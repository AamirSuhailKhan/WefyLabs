# WefyLabs — Privacy-Preserving Benchmark Design
## Master Build 14 · Phase 77

---

## 1. Design Principles

Benchmarking in WefyLabs enables tenants to understand how their performance compares
to the aggregate of the platform — **without exposing any individual tenant's data**.

The core contract is:

> **A tenant can see where they sit in the distribution. They can never identify who else is in it.**

---

## 2. Cohort Requirements

| Parameter | Value | Rationale |
|---|---|---|
| Minimum cohort size | **5 tenants** | Below this, re-identification is possible |
| Aggregation output | Percentile bands (P25, P50, P75, P90) | Never raw values |
| Tenant self-exclusion | Always excluded from own cohort stats | Prevents self-comparison bias |
| Cohort definition | `BenchmarkDefinition.cohort_criteria` JSONB | Explicit, auditable |

---

## 3. Benchmark Lifecycle

```
draft ──► active ──► archived
              │
              └──► [cohort too small] → stays draft, no data exposed
```

| Status | Description |
|---|---|
| `draft` | Definition created; cohort not yet populated or < 5 tenants |
| `active` | Cohort ≥ 5 tenants; percentile stats published |
| `archived` | No longer used; historical data preserved for audit |

---

## 4. Metric Definitions

### 4.1 Conversion Rate Benchmark

```
metric_id: "conversion_rate"
formula: leads_converted_to_booking / total_qualified_leads
unit: percentage
aggregation: P50 across cohort (revenue_tier ∈ [mid_market, enterprise])
```

### 4.2 Revenue Velocity Benchmark

```
metric_id: "revenue_velocity"
formula: total_revenue_inr / active_days_in_period
unit: INR/day
aggregation: P25, P50, P75 across cohort
```

### 4.3 Lead Response Time Benchmark

```
metric_id: "lead_response_time_minutes"
formula: median(first_contact_at - lead_created_at) in minutes
unit: minutes
aggregation: P50 across cohort
```

### 4.4 Deal Cycle Duration Benchmark

```
metric_id: "deal_cycle_days"
formula: median(booking_at - lead_created_at) in days
unit: days
aggregation: P25, P50, P75 across cohort
```

---

## 5. Comparison API Contract

```
GET /api/v1/intelligence/benchmarks/{definition_id}/compare

Response:
{
  "benchmark_definition_id": "...",
  "metric_id": "conversion_rate",
  "period": "2026-Q3",
  "cohort_size": 12,   // always ≥ 5, exact number shown
  "cohort_stats": {
    "p25": 0.12,
    "p50": 0.19,
    "p75": 0.28,
    "p90": 0.41
  },
  "your_value": 0.23,   // tenant's own value
  "your_percentile": 67 // where they sit (0–100)
}
```

No raw data from other tenants is returned. The `cohort_stats` are precomputed aggregates.

---

## 6. Privacy Audit Log

Every benchmark comparison API call is recorded in the security audit log:

```json
{
  "event": "benchmark_compared",
  "tenant_id": "<calling_tenant>",
  "definition_id": "<benchmark_id>",
  "cohort_size": 12,
  "timestamp": "2026-09-27T14:00:00Z"
}
```

This enables retrospective analysis if a privacy concern is raised.

---

## 7. Cross-Tenant Learning Prohibition

The following operations are **explicitly forbidden** regardless of opt-in status:

- Using Tenant A's `OutcomeRecord` to update a model served to Tenant B
- Using Tenant A's `IntelligenceSignal` scores in Tenant B's recommendation engine
- Exposing Tenant A's conversation data as training examples for Tenant B's NLP model
- Aggregating fewer than 5 tenant samples into a benchmark metric

These prohibitions are enforced at:
1. **Service layer** — `IntelligenceService` always scopes queries by `tenant_id`
2. **Benchmark service** — cohort size checked before returning any stats
3. **Test layer** — `test_master_build_14_security.py::TestCrossTenantIsolation` validates boundary enforcement
