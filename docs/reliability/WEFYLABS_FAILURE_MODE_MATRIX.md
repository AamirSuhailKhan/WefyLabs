# WEFYLABS — FAILURE MODE & EFFECTS ANALYSIS (FMEA)
## Master Build 12 — Production Reliability Matrix

**Status:** ✅ PRODUCTION CANONICAL  
**Module:** `apps/api/app/modules/reliability/`  

---

## 1. Failure Modes & Mitigations

| Dependency / Component | Failure Mode | Blast Radius | Mitigation Strategy | Degraded Mode Behavior |
| :--- | :--- | :--- | :--- | :--- |
| **PostgreSQL Primary** | Process crash / disk failure | All state mutations | Read-replica standby promotion via streaming WAL. | Read-only mode active; queuing new lead ingest into Redis buffer. |
| **Redis Cache** | Out of memory / connection reset | Session cache & pubsub | Fallback to database queries; transient state reconstructed. | Application serves traffic directly from DB; latency increases ~15ms. |
| **Google Gemini API** | Provider 503 / rate limit | Autonomous AI qualification | Circuit breaker trips to OPEN; rule-based fallback response engine. | CRM, search, manual chat, and lead pipelines remain 100% operational. |
| **WhatsApp Cloud API** | Upstream Meta outage | Outbound messaging | Messages queued in Outbox with exponential backoff & jitter. | UI indicates pending delivery; SMS fallback triggered if urgent. |
| **Celery Worker Crash** | Unhandled task OOM | Background asynchronous tasks | Idempotent task acknowledgment (`acks_late=True`); replacement worker recovers work. | Task retried with exponential backoff; dead-letter queue catches max retries. |
| **Search Engine (pgvector)**| Index rebuild / memory limit | Vector similarity matching | Fallback to relational SQL filters (bedrooms, budget, location). | Search returns exact/range SQL matches without semantic embeddings. |
