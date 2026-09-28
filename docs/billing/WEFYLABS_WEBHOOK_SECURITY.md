# WefyLabs Payment Webhook Security & Ingestion Pipeline
**Master Build 13 — Canonical Webhook Architecture**

## 1. Webhook Pipeline Invariant
An unverified webhook is never a billing event.
Every incoming webhook callback must execute the following multi-stage validation pipeline:

```
[Raw HTTP POST]
       |
       v
1. Signature Verification
   (HMAC-SHA256 of raw bytes against RAZORPAY_WEBHOOK_SECRET)
   * Any signature mismatch or empty header -> 400 Bad Request (Halt)
       |
       v
2. Replay & Duplicate Ingestion Protection
   (Lookup ProviderWebhookEvent by event_id)
   * If already processed -> Return 200 OK (Idempotent No-Op)
       |
       v
3. Raw Event Persistence
   (Write ProviderWebhookEvent record with payload and headers)
       |
       v
4. Payload Normalization
   (Convert provider payload into canonical BillingEvent)
       |
       v
5. State Machine Dispatch
   (Update internal Subscription, Invoice, or PaymentAttempt)
       |
       v
6. Acknowledge Provider (200 OK)
```

---

## 2. Cryptographic Implementation
Webhook authentication is implemented via constant-time comparison to prevent timing attacks:
```python
expected_sig = hmac.new(
    secret.encode("utf-8"),
    raw_body_bytes,
    hashlib.sha256
).hexdigest()

if not hmac.compare_digest(expected_sig, signature_header):
    raise WebhookSignatureVerificationError("Invalid webhook signature.")
```

---

## 3. Out-of-Order Delivery Protection
In distributed networks, `subscription.cancelled` can arrive before `payment.failed`.
The system guards against state regression:
- Event timestamps (`occurred_at` / `created_at`) from the provider are stored alongside internal timestamps.
- Transitions must be strictly monotonic according to the finite state machine. A stale transition request that contradicts current internal state enters a reconciliation queue (`BillingReconciliationService`) rather than corrupting tenant data.
