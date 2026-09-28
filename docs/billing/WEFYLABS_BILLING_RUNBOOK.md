# WefyLabs Billing Operations Runbook
**Master Build 13 — Production Operations Guide**

## 1. Emergency Payment Pause
If upstream payment gateway (Razorpay) exhibits high error rates or transaction degradation:
```bash
# Enable Emergency Payment Pause via Redis
redis-cli SET payments:emergency_pause 1
redis-cli SET payments:emergency_pause_reason "Upstream gateway downtime incident #892"

# Verify pause status
curl -H "Authorization: Bearer <TOKEN>" https://api.wefylabs.com/api/v1/billing/admin/status
```
When paused, checkout attempts immediately return HTTP 503 with user-friendly retry advisories without dropping customer cart or subscription data.

---

## 2. Reconciling Orphan or Mismatched Payments
If `BillingReconciliationService` flags a payment captured externally with no internal invoice:
1. Query the discrepancy record:
   ```sql
   SELECT * FROM revenue_reconciliation_records WHERE discrepancy_type = 'ORPHAN_PAYMENT' AND status = 'PENDING';
   ```
2. Inspect gateway transaction logs for the `razorpay_payment_id`.
3. Locate corresponding `organization_id` from metadata or contact email.
4. Manually associate and trigger retroactive invoice settlement via admin API:
   ```bash
   POST /api/v1/billing/admin/reconcile-payment
   {
     "payment_id": "pay_xxx",
     "organization_id": "uuid-xxx",
     "reason": "Resolving orphan payment from delayed webhook"
   }
   ```

---

## 3. Manual Credit Adjustment Procedure
To grant operational credits for downtime compensation or contractual discounts:
```bash
POST /api/v1/billing/admin/issue-credit
{
  "organization_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "amount": "1000.00",
  "currency": "INR",
  "reason": "Downtime SLA service credit compensation - Incident #901"
}
```
This writes an immutable append-only `CreditLedgerEntry` (`CREDIT_ISSUED`), updates the cached `CreditBalance`, and automatically applies the deduction to the tenant's next renewal invoice.

---

## 4. Webhook Replay & Reprocessing
If webhooks were missed during network partition:
1. Re-fetch failed webhook IDs:
   ```sql
   SELECT id, provider_event_id FROM provider_webhook_events WHERE status = 'FAILED';
   ```
2. Replay event safely through the idempotent ingestion pipeline:
   ```bash
   POST /api/v1/billing/admin/reprocess-webhook/{event_id}
   ```
   *Guaranteed invariant:* Already-processed events will be treated as idempotent no-ops.
