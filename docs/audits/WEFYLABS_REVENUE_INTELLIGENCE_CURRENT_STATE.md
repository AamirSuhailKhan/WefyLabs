# WEFYLABS REVENUE INTELLIGENCE — CURRENT STATE AUDIT

## Audit Date: 2026-09-26

---

## CLASSIFICATION KEY

```
CANONICAL        — Authoritative source of truth, production-safe
DERIVED          — Computed from canonical data, rebuildable
DUPLICATE        — Redundant implementation with shared meaning
LEGACY           — Older implementation superseded by newer canonical
PARTIAL          — Correct design but incomplete fields
MOCKED           — Uses hardcoded or fabricated values
HARDCODED        — Contains hardcoded business logic values
FRONTEND-ONLY    — Revenue calculation occurs in UI, not trusted backend
BACKEND-ONLY     — Backend exists, no API consumer yet
PRODUCTION-RISK  — Uses Float for money or fabricates fallback data
PRODUCTION-READY — Tested, Decimal-typed, tenant-safe
UNKNOWN          — Insufficient evidence to classify
```

---

## 1. Revenue Events (Canonical Ledger)

| Model / Location | Classification | Notes |
|:---|:---:|:---|
| `sales_pipeline_models.RevenueEvent` | **CANONICAL** | Append-only, Numeric(20,4), event_id idempotency key, full data lineage. Build 08 foundation. |
| `sales_pipeline_models.RevenueEventType` | **CANONICAL** | 19 event type constants covering full commercial lifecycle |
| `sales_pipeline_models.PropertyPaymentTransaction` | **CANONICAL** | Real-estate payment table, Numeric(20,4), status state machine |
| `transaction_models.DealTransaction` | **LEGACY + PRODUCTION-RISK** | Uses `Float` for `agreed_price` and `estimated_commission_amount`. Superseded by `Deal` + `RevenueEvent`. |
| `transaction_models.DealPaymentSchedule` | **LEGACY + PRODUCTION-RISK** | Uses `Float` for `amount`. No link to canonical RevenueEvent. |
| `payment_models.PaymentOrder` | **CANONICAL** | Razorpay SaaS billing (platform fees). NOT real-estate revenue. Correctly scoped. |
| `payment_models.PaymentTransaction` | **CANONICAL** | Razorpay payment captures. Webhook idempotency via unique `razorpay_payment_id`. |
| `payment_models.PaymentRefund` | **CANONICAL** | Refund model with status machine. |

---

## 2. Forecasting

| Module / Service | Classification | Notes |
|:---|:---:|:---|
| `predictive/revenue/revenue_forecast_service.py` | **HARDCODED + PRODUCTION-RISK** | Uses `float()` for all calculations. Hardcoded `DEFAULT_COMMISSION_RATE = 0.02`, `forecast_confidence=0.88` (fabricated), fallback `budget_max = 2_000_000.0`. Does NOT read from `RevenueEvent` or `deals`. Reads raw `Lead.pipeline_stage`. **Must be replaced by Build 09.** |
| `core/domain/analytics/entities.py::RevenueForecastEntity` | **PARTIAL** | Float-based entity. Useful structure but uses `float` not `Decimal`. |
| `models/predictive_models.ForecastSnapshotRecord` | **BACKEND-ONLY** | ORM model exists. Contains `Float` columns for financial data. Needs migration to `Numeric`. |
| `revenue_intelligence.service.FunnelAnalyzer` | **CANONICAL** | Reads from `Lead` table with stage counts. Correctly returns `None` for zero denominators. No fabrication. |
| `revenue_intelligence.service.SnapshotService` | **CANONICAL** | Captures funnel snapshots to `RevenueFunnelSnapshot`. Additive, not destructive. |

---

## 3. Attribution

| Model / Service | Classification | Notes |
|:---|:---:|:---|
| `acquisition_models.SourceAttribution` | **CANONICAL** | Stores `first_touch_at`, `last_touch_at`, UTM fields. Never fabricated. Linked to `lead_id`. |
| `acquisition_models.LeadSource` | **CANONICAL** | Named source registry (Meta, 99acres, etc). |
| `acquisition_models.LeadCampaign` | **CANONICAL** | Campaign registry with spend metadata. |
| `marketing_models.MarketingCampaign` | **CANONICAL** | Extends `LeadCampaign` with budget controls and approval workflow. Numeric money. |
| `revenue_intelligence.service.SourceAttributionReport` | **DERIVED** | Aggregates source → funnel conversion. Read-only from `Lead` table. |
| Multi-touch attribution | **NOT BUILT** | Only first/last touch stored via `SourceAttribution`. Linear/time-decay/position-based models NOT implemented. Build 09 adds this. |
| Attribution window configuration | **NOT BUILT** | No configurable window. Build 09 adds `AttributionTouchpoint` model with window support. |

---

## 4. Leakage Detection

| Module / Service | Classification | Notes |
|:---|:---:|:---|
| `revenue_intelligence_models.RevenueLeakageEvent` | **CANONICAL** | Append-only leakage log per lead. Uses `Float` for `estimated_value_lost` (PRODUCTION-RISK). |
| `revenue_intelligence.service.LeakageDetector` | **PARTIAL** | Detects stale leads and explicit losses. Does NOT cover Build 08 leakage conditions (site visit no outcome, negotiation stalled, hold expiring, booking/payment mismatch). Build 09 must extend. |
| `RevenueLeakageEvent.detected_at` | **CANONICAL** | Correctly append-only. |

---

## 5. Pipeline Analytics

| Module / Service | Classification | Notes |
|:---|:---:|:---|
| `revenue_intelligence.service.FunnelAnalyzer` | **CANONICAL** | Reads `Lead.pipeline_stage`. Does NOT yet read from `OpportunityStageHistory` (Build 08). Build 09 must converge. |
| `revenue_intelligence.service.OverviewAnalyzer` | **DERIVED** | Aggregates pipeline metrics from `Lead` table. |
| `revenue_intelligence.router` | **BACKEND-ONLY** | 17 endpoints exist. Some correctly read from canonical models. Some use `float` in response schemas. |

---

## 6. Unit Economics

| Module / Service | Classification | Notes |
|:---|:---:|:---|
| CAC calculation | **NOT BUILT** | No campaign spend ingestion integration. Build 09 adds `INSUFFICIENT_DATA` response. |
| AI cost tracking | **NOT BUILT** | No AI token cost tracking linked to leads/opportunities. Build 09 adds foundation. |
| Communication cost | **NOT BUILT** | WhatsApp/SMS cost tracking not connected to revenue analytics. Build 09 adds foundation. |
| Revenue per lead | **PARTIAL** | `OverviewAnalyzer` has basic aggregations but uses `float`. |

---

## 7. CRITICAL PRODUCTION RISKS

| Risk | Location | Severity |
|:---|:---|:---:|
| Float for money | `transaction_models.py:24,29,60` | **HIGH** |
| Float for money | `revenue_intelligence_models.RevenueLeakageEvent.estimated_value_lost` | **HIGH** |
| Fabricated forecast confidence | `revenue_forecast_service.py:108` (`forecast_confidence=0.88`) | **HIGH** |
| Fabricated fallback budget | `revenue_forecast_service.py:79` (`budget_max = 2_000_000.0`) | **HIGH** |
| Forecast does not read RevenueEvent | `revenue_forecast_service.py` | **HIGH** |
| Forecast uses Lead.pipeline_stage not OpportunityStage | `revenue_forecast_service.py:56-63` | **MEDIUM** |
| `estimated_value_lost` uses Float not Numeric | `revenue_intelligence_models.py:130` | **MEDIUM** |

---

## 8. What Build 09 Must Deliver

1. **Canonical Revenue Ledger extended**: Add `correlation_id`, `causation_id`, `identity_id`, `project_id`, `schema_version` to `RevenueEvent` (migration).
2. **Attribution engine**: `AttributionTouchpoint` model + First-touch / Last-touch / Linear / Time-decay / Position-based calculators.
3. **Leakage engine v2**: Extend `RevenueLeakageEvent` to cover Build 08 leakage conditions. Fix `Float` → `Numeric`.
4. **Forecast v2**: Replace `revenue_forecast_service.py` hardcoded implementation with evidence-based stage-weighted forecast from `OpportunityStageHistory` + `RevenueEvent`.
5. **Funnel v2**: Converge `FunnelAnalyzer` to read from Build 08 stage history, not raw `Lead.pipeline_stage`.
6. **Unit Economics**: Add `UnitEconomicsRecord` for cost-per-milestone tracking. Return `INSUFFICIENT_DATA` where cost data absent.
7. **Anomaly Detection**: `RevenueAnomalyRecord` model + deterministic statistical rule engine.
8. **Metric Registry**: `MetricDefinition` model with formula, version, source, filters.
9. **Forecast Snapshots v2**: Fix Float columns in `ForecastSnapshotRecord`, add immutability guarantees.
10. **Data Quality**: Add `DataQualityCheck` service reading from all revenue-relevant tables.
