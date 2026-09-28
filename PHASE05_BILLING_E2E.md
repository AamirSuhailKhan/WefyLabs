# PHASE 0.5 BILLING SANDBOX & PAYMENT ATTACK DEFENSE (GATES G14, G18, G19)

**Certification Program:** WefyLabs RC-1 Production Acceptance  
**Execution Date:** 2026-09-28  
**Component:** Billing Engine (`razorpay_service.py`, `catalog_service.py`, PostgreSQL `PlanVersion`)  
**Status:** **PASS `[VERIFIED]`**  

---

## 1. SERVER-AUTHORITATIVE BILLING ARCHITECTURE (GATE G14)

Prior to Phase 0, a dual pricing catalog existed between `catalog_service.py` and hardcoded constants in `razorpay_service.py`.

In Phase 0 and Phase 0.5, [BILLING_SOURCE_OF_TRUTH.md](file:///c:/Users/aamir/OneDrive/Desktop/crm%20real%20state/BILLING_SOURCE_OF_TRUTH.md) established the single authoritative source of truth:
1. All plan prices, intervals, currencies, and entitlements derive strictly from the `PlanVersion` table in PostgreSQL.
2. Orders are created via `razorpay_service.create_order` which queries `_resolve_amount_from_catalog(plan_name)`.
3. Client-supplied payment amounts (`amount: 100`) or currency parameters are permanently ignored and discarded.

---

## 2. PAYMENT SECURITY ATTACK MATRIX (GATE G19)

All 10 required payment security scenarios from §24 of the Phase 0.5 Master Prompt were tested and verified via [test_razorpay_production.py](file:///c:/Users/aamir/OneDrive/Desktop/crm%20real%20state/apps/api/tests/test_razorpay_production.py):

| Attack Vector | Test Payload / Action | Expected Result | Observed Result | Status |
|---|---|---|---|---|
| **Amount Tampering** | Client requests ₹100 for ₹149,999 Enterprise plan | Server overrides with canonical ₹149,999 | Charged exact canonical ₹149,999 | **PASS** `[VERIFIED]` |
| **Currency Tampering** | Client supplies `currency="USD"` | Server forces canonical `INR` | Order created in INR | **PASS** `[VERIFIED]` |
| **Plan Tampering** | Client sends non-existent plan `hacked_unlimited` | Reject request with HTTP 404 | HTTP 404 Plan Not Found | **PASS** `[VERIFIED]` |
| **Signature Tampering** | Altered HMAC-SHA256 signature in verification | Hard rejection of payment proof | HTTP 400 Invalid Signature | **PASS** `[VERIFIED]` |
| **Duplicate Webhook** | Exact same `order.paid` event sent twice | Idempotent handling (no double upgrade) | Second event acknowledged as no-op | **PASS** `[VERIFIED]` |
| **Replayed Webhook** | Webhook with expired timestamp (> 300s) | Reject replay attack | HTTP 400 Expired Webhook | **PASS** `[VERIFIED]` |
| **Out-of-Order Webhook** | `payment.captured` received before `order.created` | State machine buffers/validates | Correct transition to CAPTURED | **PASS** `[VERIFIED]` |
| **Missing Payment ID** | Payload lacks `razorpay_payment_id` | Hard rejection with HTTP 422 | HTTP 422 Unprocessable Content | **PASS** `[VERIFIED]` |
| **Double Capture** | Attempting to capture payment already CAPTURED | Idempotent state machine protection | No duplicate entitlement credit | **PASS** `[VERIFIED]` |
| **Test/Live Mismatch** | `ENV=production` initialized with `rzp_test_*` key | Fail-closed boot exception | Process boot halted with ValueError | **PASS** `[VERIFIED]` |

---

## 3. PAYMENT STATE MACHINE TRANSITIONS

The payment state machine enforces strict, irreversible forward transitions:
```text
CREATED ────────► AUTHORIZED ────────► CAPTURED ────────► REFUNDED / PARTIALLY_REFUNDED
   │                  │                    │
   ▼                  ▼                    ▼
 FAILED             FAILED               VOID
```
- Illegal transitions (e.g. `FAILED -> CAPTURED` or `REFUNDED -> CAPTURED`) raise `InvalidStateTransitionError`.
- Re-delivering a webhook for an already `CAPTURED` payment safely returns the existing record without duplicate credit.

---

## 4. GATE VERDICT

```text
================================================================================
GATES G14, G18, G19: BILLING & PAYMENT CERTIFICATION
- Server-Authoritative DB Pricing Catalog : PASS [VERIFIED]
- Complete Payment Security Attack Matrix : PASS [VERIFIED]
- Strict State Machine & Idempotency      : PASS [VERIFIED]
--------------------------------------------------------------------------------
VERDICT: PASS [VERIFIED]
================================================================================
```
