# WEFYLABS — INCIDENT OBSERVABILITY & INTELLIGENCE
## Master Build 12 — Production Standard

**Status:** ✅ PRODUCTION CANONICAL  
**Module:** `apps/api/app/modules/observability/incident_manager.py`  

---

## 1. Incident Lifecycle

WefyLabs manages incidents through a strict 5-state lifecycle:

```text
    ┌────────┐
    │  OPEN  │ ── (Triggered by anomaly or SLO breach)
    └───┬────┘
        │
    ┌───▼─────────────┐
    │  ACKNOWLEDGED   │ ── (On-call claims ownership, TTD calculated)
    └───┬─────────────┘
        │
    ┌───▼─────────────┐
    │  INVESTIGATING  │ ── (Root cause analysis & telemetry diagnosis)
    └───┬─────────────┘
        │
    ┌───▼─────────────┐
    │    RESOLVED     │ ── (Mitigation validated, TTR calculated)
    └───┬─────────────┘
        │
    ┌───▼────┐
    │ CLOSED │ ── (Postmortem published & preventative actions tracked)
    └────────┘
```

---

## 2. Quantitative Metric Formulas

1. **TTD (Time-to-Detect):**
   $$\text{TTD} = \text{Timestamp}_{\text{Acknowledged}} - \text{Timestamp}_{\text{Created}}$$
2. **TTR (Time-to-Resolve):**
   $$\text{TTR} = \text{Timestamp}_{\text{Resolved}} - \text{Timestamp}_{\text{Created}}$$
3. **No Synthetic Numbers Invariant:**
   All MTTR, MTTD, and availability figures are derived directly from immutable database event records. No synthetic approximations are permitted.

---

## 3. Incident Correlation & Timeline

Every incident record maintains an append-only timeline containing:
- `event_type`: `created`, `acknowledged`, `escalated`, `mitigated`, `resolved`, `comment`
- `actor`: System engine or authenticated operator
- `timestamp`: UTC ISO-8601
- `metadata`: Linked trace IDs, affected services, error snippets
