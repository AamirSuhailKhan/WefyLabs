# WEFYLABS — SERVICE LEVEL OBJECTIVES (SLO) & SLI POLICY
## Master Build 12 — Production Standard

**Status:** ✅ PRODUCTION CANONICAL  
**Module:** `apps/api/app/modules/observability/slo_manager.py`  

---

## 1. Terminology

- **SLA (Service Level Agreement):** External commercial commitment made to enterprise clients.
- **SLO (Service Level Objective):** Internal engineering target designed with a safety margin above SLA.
- **SLI (Service Level Indicator):** Real-time quantitative measurement (latency, availability percentage, error rate).
- **Error Budget:** The allowable room for failure ($100\% - \text{SLO}$).

---

## 2. Canonical SLO Registry

| SLO Name | Target | Unit | Measurement Window | Direction | Action on Breach |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **`api_availability`** | ≥ 99.9% | percent | 30 days rolling | Must stay ABOVE | Auto-open P1 Incident |
| **`api_p99_latency_ms`** | ≤ 500 ms | ms | 1 hour rolling | Must stay BELOW | Page on-call if error budget < 20% |
| **`ai_response_p95_ms`** | ≤ 3,000 ms | ms | 1 hour rolling | Must stay BELOW | Trip circuit breaker fallback |
| **`db_query_p99_ms`** | ≤ 100 ms | ms | 1 hour rolling | Must stay BELOW | Log slow query & notify DB admin |
| **`queue_processing_p95_ms`** | ≤ 5,000 ms | ms | 1 hour rolling | Must stay BELOW | Scale worker concurrency |
| **`error_rate`** | < 1.0% | percent | 1 hour rolling | Must stay BELOW | Investigate recent deployments |

---

## 3. Error Budget Calculation

For latency and error-rate SLOs:
$$\text{Remaining Error Budget} = \max\left(0, \frac{\text{Target} - \text{Current}}{\text{Target}}\right) \times 100\%$$

### Status Transitions:
- **`MEETING`**: $\text{Remaining Budget} > 20\%$ (Normal operations)
- **`AT_RISK`**: $0\% < \text{Remaining Budget} \le 20\%$ (Feature freezes considered, active investigation)
- **`BREACHED`**: $\text{Remaining Budget} = 0\%$ (P1 Incident triggered, deployment block enforced)
