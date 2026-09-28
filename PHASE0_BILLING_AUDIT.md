# PHASE 0 BILLING & PAYMENTS AUDIT REPORT (P0.4)

**Execution Date:** 2026-09-28T17:57:00+05:30  
**Target:** `apps/api/app/modules/billing/` and `render.yaml`  
**Status:** `REMEDIATED & VERIFIED` `[VERIFIED]`  

---

## 1. FINDINGS & VULNERABILITIES RESOLVED

### Finding BILL-01: Razorpay Test Mode in Production Manifest
- **Pre-Hardening Reality:** `render.yaml` specified `RAZORPAY_ENVIRONMENT: test`. Production deployment would accept mock test cards and fail live transactions.
- **Remediation:** Added fail-fast startup validator in `EnterpriseSettings.validate_production_security`:
  - `ENV == production` + `RAZORPAY_KEY_ID.startswith("rzp_test_")` -> FAILS STARTUP.
  - `RAZORPAY_ENVIRONMENT == live` + non-live keys -> FAILS STARTUP.
  - `render.yaml` documented for live credential injection upon release gate approval.

### Finding BILL-02: Split Pricing Authority
- **Pre-Hardening Reality:** `razorpay_service.py` maintained a static hardcoded `PLANS` dictionary containing price amounts in paise, while `catalog_service.py` maintained dynamic database models (`Plan`, `PlanVersion`, `PlanEntitlement`). This risked price divergence between what the UI displayed and what Razorpay charged.
- **Remediation:** Added `_resolve_amount_from_catalog` to `RazorpayProductionService`:
  ```python
  async def _resolve_amount_from_catalog(self, plan_id: str) -> Optional[int]:
      # Resolves price in paise from PlanVersion table in PostgreSQL
  ```
  In production, if the catalog is unreachable or the plan is not found, order creation fails closed (`HTTP 500`) rather than charging a potentially incorrect hardcoded amount.

### Finding BILL-03: Insecure Test-Mode Signature Bypass
- **Pre-Hardening Reality:** `verify_payment_signature` and `verify_webhook_signature` bypassed verification if `secret_key == "secret_placeholder"`. A production deployment with an unset or default secret accepted `"valid_test_signature"` for arbitrary transactions.
- **Remediation:** Quarantined signature bypass exclusively to `settings.ENV in ("testing", "test")`.

---

## 2. TEST EXECUTION EVIDENCE

Executed test suite: `apps/api/tests/test_razorpay_production.py`
```text
============================= 15 passed in 38.11s =============================
- TestPaymentStateMachine: valid transitions, idempotent no-ops, illegal transitions rejected: PASSED
- test_get_plans_catalog: PASSED
- test_create_order_authoritative_pricing: PASSED
- test_create_order_idempotency: PASSED
- test_create_order_invalid_plan: PASSED
- test_verify_payment_success: PASSED
- test_verify_payment_tampered_signature_rejected: PASSED
- test_webhook_valid_signature_and_processing: PASSED
- test_webhook_invalid_signature_rejected: PASSED
- test_refund_full_and_partial_flow: PASSED
- test_tenant_idor_order_and_refund_isolation: PASSED
- test_emergency_payment_pause: PASSED
- test_zero_secret_leak_in_api_responses: PASSED
```
