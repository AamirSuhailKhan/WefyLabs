# BILLING SOURCE OF TRUTH SPECIFICATION

**Author:** Principal Software Architect + Payments Reliability Engineer  
**Date:** 2026-09-28T17:57:00+05:30  
**Phase:** Phase 0 Production Foundation Hardening (P0.4)  
**Authority:** Single Canonical Database Catalog (`apps/api/app/modules/billing/services/catalog_service.py`)  

---

## 1. THE SINGLE BILLING AUTHORITY PRINCIPLE

The WefyLabs billing architecture recognizes **exactly one pricing authority**:
The database-driven product catalog managed by `CatalogService` backed by `plans`, `plan_versions`, and `plan_entitlements` tables.

```text
               ┌──────────────────────────────┐
               │    Canonical DB Catalog      │
               │       (CatalogService)       │
               │   PlanVersion (Price & Paise)│
               └──────────────┬───────────────┘
                              │ Authoritative Price & Paise
            ┌─────────────────┴─────────────────┐
            │                                   │
            ▼                                   ▼
┌───────────────────────┐           ┌───────────────────────┐
│  Subscription Engine  │           │    Razorpay Service   │
│ (Entitlements, Seats) │           │ (Order, Paise Amount) │
└───────────────────────┘           └───────────────────────┘
            │                                   │
            ▼                                   ▼
┌───────────────────────┐           ┌───────────────────────┐
│     Client UI App     │           │   Payment Gateway     │
│   (Presentation Only) │           │  (Server-Sent Amount) │
└───────────────────────┘           └───────────────────────┘
```

### Invariant Rules:
1. **Never Client-Authoritative:** The client cannot supply an `amount` parameter to `/api/v1/billing/orders`. It supplies only a `plan_id` (or `plan_code` + `interval`).
2. **Server-Side Catalog Resolution:** `RazorpayProductionService.create_payment_order` resolves the exact price in paise from the active `PlanVersion` record in PostgreSQL.
3. **Fail-Closed on Catalog Miss:** In production/staging, if a plan is missing from the canonical catalog or inactive, payment order creation fails closed with `HTTP 500` ("Canonical billing catalog is unavailable. Payment refused.").
4. **Presentation Constants are Non-Authoritative:** Any dictionary constants in UI or service files (`PLANS = {...}`) are classified strictly as **presentation/metadata fallbacks** and never override the database price.

---

## 2. CANONICAL PRICING CATALOG (ACTIVE V1)

| Plan Code | Interval | Price (INR) | Price (Paise) | Max Seats | Active Leads | WhatsApp Messages / mo | AI Tokens / mo | Export Limit | Status |
|---|---|---|---|---|---|---|---|---|---|
| `free` | Monthly | ₹0 | 0 | 1 | 50 | 50 | 25 | 2 | Active |
| `starter` | Monthly | ₹2,999 | 299,900 | 2 | 250 | 500 | 250 | 10 | Active |
| `starter` | Annual | ₹29,990 | 2,999,000 | 2 | 250 | 500 | 250 | 10 | Active |
| `pro` | Monthly | ₹4,999 | 499,900 | 5 | 1,000 | 2,000 | 1,000 | Unlimited | Active |
| `pro` | Annual | ₹49,990 | 4,999,000 | 5 | 1,000 | 2,000 | 1,000 | Unlimited | Active |
| `enterprise` | Monthly | ₹14,999 | 1,499,900 | 20 | Unlimited | 10,000 | 10,000 | Unlimited | Active |
| `enterprise` | Annual | ₹149,990 | 14,999,000 | 20 | Unlimited | 10,000 | 10,000 | Unlimited | Active |

---

## 3. PAYMENT ENVIRONMENT TRUTH & SECURITY CONTROLS

- **Environment Separation:**
  - `LOCAL` / `TESTING`: Test signatures allowed for automation only when `ENV in ("testing", "test")`.
  - `STAGING`: Razorpay `test` mode (`rzp_test_*`). Live charges strictly prohibited.
  - `PRODUCTION`: Razorpay `live` mode (`rzp_live_*`).
- **Signature Bypass Hardening:**
  Removed previous insecure bypass where the literal string `secret_placeholder` allowed signature verification bypass in production. Signature bypass is strictly quarantined to `ENV in ("testing", "test")`.
- **Idempotency & Replay:**
  Every payment order accepts an `idempotency_key` stored in `payment_orders.idempotency_key`. Concurrent or replayed orders with identical keys return the existing active order without re-creating Razorpay entities.
- **Webhook HMAC Verification:**
  Razorpay webhooks verify SHA-256 HMAC against `RAZORPAY_WEBHOOK_SECRET` before processing payment capture or subscription status updates.
