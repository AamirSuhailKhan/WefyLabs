# RUNBOOK — PAYMENT GATEWAY & BOOKING TRANSACTION FAILURES
## Code: RB-PAY-007 | Severity: P0 / P1

---

## 1. Symptoms & Triggers
- Razorpay webhook delivery failure or capture rejection spike (> 5% in 10 mins).
- Customer booking in PENDING state without receipt verification.

## 2. Diagnostics
1. Verify Razorpay API status (status.razorpay.com).
2. Check `payments` table for failed idempotency keys or signature mismatches.

## 3. Mitigation & Recovery
- **No Unsafe State Mutations:** Never cancel booking units or trigger blind refunds automatically.
- Keep deal booking in `PAYMENT_PENDING` with 2-hour hold timer.
- Run reconciliation worker task to query Razorpay Payment Status API for untracked captures.
