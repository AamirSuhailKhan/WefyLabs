# WEFYLABS — DISTRIBUTED TRACING STANDARD
## Master Build 12 — Production Standard

**Status:** ✅ PRODUCTION CANONICAL  
**Module:** `apps/api/app/modules/tracing/tracer.py`  

---

## 1. W3C Trace Context Specification

All distributed communication across HTTP, Webhooks, Celery background tasks, and AI Gateway invocations adheres to the **W3C Trace Context recommendation**:

Format:
```text
traceparent: 00-{trace_id}-{span_id}-{trace_flags}
```
- `version`: `00`
- `trace_id`: 32 hexadecimal characters (16 bytes)
- `span_id`: 16 hexadecimal characters (8 bytes)
- `trace_flags`: `01` (recorded / sampled)

Example:
```text
traceparent: 00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01
```

---

## 2. Inbound & Outbound Headers

- **`X-Request-ID`**: Uniquely tags each discrete client request. If missing, generated via `req-{uuid4().hex[:12]}`.
- **`X-Correlation-ID`**: Correlates multi-step asynchronous customer workflows (e.g. Lead Ingest → WhatsApp Notification → AI Agent Reply).
- **`traceparent`**: W3C distributed trace context header.

---

## 3. Span Chaining and Nesting

Tracing context is maintained in Python asynchronous tasks via `contextvars.ContextVar`.
Spans automatically capture:
- Parent span linkage (`parent_span_id`)
- Duration in milliseconds
- Operation status (`OK` or `ERROR`)
- Error string if an exception was raised
- Metadata attributes (e.g. `organization_id`, `journey_id`, `model_version`)

```python
with Tracer.start_span("lead_ingestion") as parent:
    with Tracer.start_span("database_insert") as child:
        # child.parent_span_id == parent.span_id
        await save_lead()
```
