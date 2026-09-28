# WefyLabs Payment Architecture & Provider Convergence
**Master Build 13 — Canonical Payment Engine**

## 1. Single Provider Abstraction
To prevent spaghetti integrations and multiple conflicting payment SDK calls across CRM modules, all transaction logic is centralized behind `PaymentProvider` and `RazorpayAdapter`:

```
                       +------------------------+
                       |    PaymentService      |
                       +-----------+------------+
                                   |
                                   v
                       +------------------------+
                       |    PaymentProvider     |
                       |    (Abstract Base)     |
                       +-----------+------------+
                                   |
                 +-----------------+-----------------+
                 |                                   |
                 v                                   v
      +----------------------+             +-------------------+
      |   RazorpayAdapter    |             | Future Adapters   |
      | (Converged Services) |             | (Stripe, etc.)    |
      +----------------------+             +-------------------+
```

---

## 2. Convergence with Existing Infrastructure
Master Build 13 strictly converges with the existing `RazorpayProductionService` in `apps/api/app/modules/billing/services/razorpay_service.py`:
- Reuses verified HMAC-SHA256 signature verification algorithms.
- Preserves idempotency lock keys (`razorpay:order_idemp:{key}`) in Redis.
- Preserves provider identifiers (`razorpay_order_id`, `razorpay_payment_id`, `razorpay_signature`).
- Enforces PCI compliance: zero storage of raw credit/debit card numbers or CVVs. Only tokenized references are retained.

---

## 3. Circuit Breakers & Emergency Pause
1. **Emergency Payment Pause:** Global Redis flag `payments:emergency_pause=1` or `PAYMENTS_EMERGENCY_PAUSE=True` in environment stops all outgoing checkout orders immediately during upstream gateway degradation.
2. **Exponential Backoff:** Outbound API calls to Razorpay endpoints incorporate retry jitter with maximum 3 attempts before flagging `PROVIDER_OUTAGE`.
