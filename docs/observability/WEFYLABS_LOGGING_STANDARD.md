# WEFYLABS — STRUCTURED LOGGING STANDARD
## Master Build 12 — Production Standard

**Status:** ✅ PRODUCTION CANONICAL  
**Module:** `apps/api/app/modules/logging/json_logger.py`  

---

## 1. Principles

1. **Structured Single-Line JSON:** Every log record emitted to standard out must be a single valid JSON object.
2. **Zero Print Statements:** `print()` is strictly forbidden in all server and worker runtime code.
3. **Automated Secret & PII Scrubbing:** All messages, extra payloads, and stack traces must automatically redact bearer tokens, API keys, credentials, credit card numbers, phone numbers, and email addresses.
4. **ContextVar Propagation:** Context variables (`request_id`, `correlation_id`, `trace_id`, `span_id`, `organization_id`, `user_id`) automatically inject into every log entry without manual passing.

---

## 2. Standard Log Schema

```json
{
  "timestamp": "2026-09-27T10:20:45.416905+00:00",
  "level": "INFO",
  "message": "[HTTP RESPONSE] GET /health/startup | Status: 200 | Latency: 12.4ms",
  "logger": "app.infrastructure.middleware.observability_middleware",
  "service": "wefylabs-api",
  "module": "http",
  "environment": "production",
  "request_id": "req-7c49e20427e4",
  "correlation_id": "corr-8a033e4ddea7",
  "trace_id": "3cecafa8e825461aab9259e61e216a2a",
  "span_id": "68e6b3c66fb64dd1",
  "organization_id": "org-enterprise-01",
  "user_id": "usr-01",
  "extra": {
    "latency_ms": 12.4,
    "status_code": 200
  }
}
```

---

## 3. Log Levels & Semantics

- **DEBUG:** Verbose diagnostics for development. Suppressed in production.
- **INFO:** Lifecycle milestones, completed HTTP transactions, worker jobs, safe telemetry.
- **WARNING:** Recoverable conditions, degraded provider fallbacks, cache misses under load, circuit breaker state transitions.
- **ERROR:** Unhandled exceptions, failed DB transactions, unrecoverable provider errors, SLO breaches.
- **CRITICAL:** Data corruption alerts, unauthorized cross-tenant attempts, complete service outages.

---

## 4. Redaction Rules

The logging formatter enforces recursive masking via `_scrub_payload()`:
- Tokens matching `Bearer <token>` are replaced with `Bearer [REDACTED_TOKEN]`.
- API keys, passwords, and secrets matching `(api_key|secret|password|auth_token)=<value>` are replaced with `[REDACTED_SECRET]`.
- Email addresses are scrubbed as `[REDACTED_EMAIL]`.
- Phone numbers are scrubbed as `[REDACTED_PHONE]`.
- Any dictionary key matching `SENSITIVE_FIELD_NAMES` (`password`, `token`, `secret`, `access_token`, `refresh_token`, `api_key`, `authorization`, `client_secret`) has its value replaced with `[REDACTED_SECRET]`.
