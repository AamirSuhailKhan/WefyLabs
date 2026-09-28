# WEFYLABS — OPERATIONS CENTER
## Master Build 12 — Command & Control Reference

**Status:** ✅ PRODUCTION CANONICAL  
**Web Route:** `/operations`  
**API Endpoints:** `/health/*`, `/v1/metrics`, `/v1/incidents`, `/v1/alerts/rules`, `/v1/diagnostics`  

---

## 1. Operator Dashboard Structure

The Operations Center provides real-time situational awareness across five primary panes:

1. **Dependency Health Registry:** Live status, category, latency (ms), and criticality flags for PostgreSQL, Redis, Gemini AI, WhatsApp Cloud API, Celery Workers, Outbox, and pgvector.
2. **SLO & Error Budget Monitor:** Real-time compliance gauges for API Availability, Latency p99, AI Inference p95, DB Query p99, Queue Processing p95, and Error Rate.
3. **AI Quality & Grounding Telemetry:** Evaluates 100 Golden Dataset ground truth cases across Relevance, Faithfulness, Zero-Hallucination, and Safety scores.
4. **Incident Intelligence Engine:** P0–P4 incident tracking, time-to-detect (TTD), time-to-resolve (TTR), affected services, and direct runbook resolution links.
5. **Capacity Exhaustion Forecast:** 30-day and 90-day predictive exhaustion horizons for DB storage, Redis memory, and AI token allocations.
