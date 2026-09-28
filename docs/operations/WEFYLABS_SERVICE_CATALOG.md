# WEFYLABS — SERVICE CATALOG
## Master Build 12 — Micro-Architecture & Operational Catalog

**Status:** ✅ PRODUCTION CANONICAL  

---

## 1. Services Inventory

| Service Name | Criticality | Owner | Dependencies | Health Endpoint | Primary SLO | Runbook Link |
| :--- | :---: | :--- | :--- | :--- | :--- | :--- |
| **API Gateway** | **CRITICAL** | Core SRE | DB, Redis, Auth | `/health/live` | Avail ≥ 99.9%, Latency p99 ≤ 500ms | [`api-high-errors.md`](runbooks/api-high-errors.md) |
| **Lead Ingestion Engine** | **CRITICAL** | Growth Eng | DB, Redis, Kafka/Outbox | `/api/v1/health-diag` | Ingest p95 ≤ 150ms | [`outbox-backlog.md`](runbooks/outbox-backlog.md) |
| **AI Sales Agent** | **HIGH** | AI Platform | Gemini, Redis, Vector DB | `/health/dependencies` | Turn p95 ≤ 3,000ms | [`ai-provider-outage.md`](runbooks/ai-provider-outage.md) |
| **Omnichannel Comm** | **HIGH** | Messaging Eng | WhatsApp, Meta Cloud | `/health/capabilities` | Webhook ack ≤ 200ms | [`whatsapp-outage.md`](runbooks/whatsapp-outage.md) |
| **Inventory & Search** | **HIGH** | Catalog Eng | PostgreSQL, pgvector | `/api/v1/health-diag` | Query p95 ≤ 200ms | [`search-degradation.md`](runbooks/search-degradation.md) |
| **Deal & Booking OS** | **CRITICAL** | FinOps Eng | PostgreSQL, Razorpay | `/health/ready` | Mutate p99 ≤ 500ms | [`payment-failure.md`](runbooks/payment-failure.md) |
| **Celery Worker Pool** | **CRITICAL** | Core SRE | Redis, Outbox | `/health/dependencies` | Queue wait ≤ 5,000ms | [`celery-backlog.md`](runbooks/celery-backlog.md) |
