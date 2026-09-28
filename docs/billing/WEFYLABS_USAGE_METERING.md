# WefyLabs Usage Metering & Ingestion Engine
**Master Build 13 — Canonical Metering Architecture**

## 1. Usage Metering Design
Every billable or trackable product action is mapped to a canonical `UsageMeter`:
- `AI_REQUEST`: Count of completed agent/copilot requests.
- `AI_INPUT_TOKEN`: Ingested prompt tokens from AI Gateway telemetry.
- `AI_OUTPUT_TOKEN`: Ingested completion tokens.
- `WHATSAPP_MESSAGE`: Inbound and outbound WhatsApp messages.
- `LEAD_CREATED`: Captured prospects from web, portal, or forwarding connectors.
- `DOCUMENT_PROCESSED`: Deeds, agreements, or floorplans processed by OCR pipeline.
- `WORKFLOW_EXECUTION`: Automated follow-up step dispatches.

---

## 2. Ingestion Idempotency & Concurrency Safety
1. **Append-Only Immutability:** Usage events are never edited or deleted. Corrections are represented as negative adjustment events.
2. **Unique Ingestion Constraint:** The `UsageEvent` table enforces a database-level unique constraint on `(organization_id, idempotency_key)`.
3. **Idempotency Key Structure:**
   - WhatsApp webhook: `wa_msg_{message_id}`
   - AI Request: `ai_trace_{trace_id}_{span_id}`
   - Lead Capture: `lead_ingest_{lead_id}`
4. **Duplicate Deduplication:**
   When an identical event key is submitted (e.g. during Celery worker retry storms or webhook retries), the engine immediately catches the `IntegrityError` or detects existing records, returning `(event, False)` with zero duplicate counts and zero double billing.

---

## 3. Rollup Aggregation Pipeline
1. Raw `UsageEvent` records are ingested continuously into PostgreSQL.
2. At the end of each `BillingPeriod` (or on demand by scheduled Celery worker `billing_aggregate_usage`), `UsageMeteringService.aggregate_usage()` computes durable `UsageAggregate` records grouped by `meter_id`.
3. Invariant: `UsageAggregate.quantity == sum(UsageEvent.quantity)`. Any variance triggers a `USAGE_MISMATCH` reconciliation alert.
