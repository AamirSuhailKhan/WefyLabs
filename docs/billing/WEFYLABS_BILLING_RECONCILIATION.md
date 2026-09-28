# WefyLabs Billing & Revenue Reconciliation Engine
**Master Build 13 — Canonical Reconciliation Architecture**

## 1. Automated Anomaly Detection
The `BillingReconciliationService` continuously compares internal subscriptions, invoices, payments, and usage rollups against external gateway state and expected invariants.

Detected Anomaly Classes:
1. **`REFUND_MISMATCH`**: Cumulative refunds exceed the captured transaction amount ($\sum \text{Refunds} > \text{Captured Amount}$).
2. **`USAGE_MISMATCH`**: The period's `UsageAggregate.quantity` does not match the sum of raw immutable `UsageEvent.quantity` records.
3. **`INVOICE_TOTAL_MISMATCH`**: The stored invoice `total` differs from $\text{Subtotal} + \text{Tax} - \text{Discounts} - \text{CreditsApplied}$.
4. **`SUBSCRIPTION_MISMATCH`**: Discrepancy between internal active subscription and payment provider subscription status.
5. **`ORPHAN_PAYMENT`**: Payment captured at gateway with no matching internal `BillingAccount` or `CanonicalInvoice`.

---

## 2. Integration with Build 09 Revenue Intelligence
Discrepancies do not silently mutate financial balances. They create an immutable `RevenueReconciliationRecord` in the database:
- Linked to the affected `organization_id`
- Stored difference amount (`discrepancy_amount`) and reason
- Status flagged as `PENDING_REVIEW` or `RESOLVED`
- Integrates with the operations command center for audit review.

---

## 3. Automated Reconciliation Job Schedule
- **Usage Aggregate Reconciliation:** Runs hourly via Celery worker (`billing_reconcile_usage`).
- **Payment & Refund Reconciliation:** Runs nightly at 02:00 UTC comparing Razorpay settlement batches against internal `PaymentTransaction` records.
