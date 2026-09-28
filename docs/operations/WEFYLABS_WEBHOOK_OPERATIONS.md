# WEFYLABS — WEBHOOK OPERATIONS & REPLAY RUNBOOK

## 1. Webhook Endpoints
Universal webhook receiver:
```http
POST /api/v1/lead-acquisition/webhooks/{provider}
```
Supported providers: `meta`, `google`, `indiamart`, `99acres`, `generic`, `zapier`, `hubspot`, `salesforce`.

Authentication:
- Token query parameter: `?token=<webhook_token>`
- Or HTTP header: `X-Webhook-Token: <webhook_token>`
- Or provider-specific signature / key (e.g. `X-Hub-Signature-256` for Meta, `google_key` for Google, `glusr_crm_key` for IndiaMART, `portal_key` for 99acres).

---

## 2. Ingestion Monitoring & Backlog Verification
Querying ingestion logs:
```sql
SELECT source, status, COUNT(*), AVG(latency_ms)
FROM ingestion_logs
WHERE organization_id = :org_id
GROUP BY source, status;
```

Checking Outbox backlog:
```sql
SELECT status, COUNT(*)
FROM outbox_events
WHERE tenant_id = :org_id
GROUP BY status;
```

---

## 3. Webhook Replay Procedure
When a webhook failure occurs due to temporary infrastructure issues:
1. Locate failed record in `original_payloads` and `ingestion_logs`:
   ```sql
   SELECT ingestion_id, raw_payload_json, source
   FROM original_payloads
   WHERE organization_id = :org_id AND ingestion_id = :failed_event_id;
   ```
2. Trigger idempotent replay via administrative API or CLI command:
   ```http
   POST /api/v1/lead-acquisition/intake
   ```
   Passing original payload with original idempotency key.
3. Verification: Ensure status transitions to `ACCEPTED` or `DUPLICATE` without duplicating CRM entities.
