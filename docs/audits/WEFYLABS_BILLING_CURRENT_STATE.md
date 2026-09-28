# WEFYLABS MASTER BUILD 13 — PHASE 0 PRE-BUILD AUDIT
## Billing, Pricing, Usage, Entitlements & Revenue OS Truth Map

**Audit Timestamp:** 2026-09-27T16:33:00+05:30  
**Auditor Roles:** CTO, Principal Backend/Frontend Engineer, Payments Architect, FinOps / Unit Economics Engineer, Data Architect, Security Engineer, SRE, QA / Test Architect  
**Workspace:** `c:\Users\aamir\OneDrive\Desktop\crm real state`

---

### Executive Overview & Pre-Build Inventory

Prior to writing any new code for **Master Build 13**, a thorough inspection of the repository was conducted across `apps/api`, `apps/web`, database schemas, Alembic migrations, telemetry collectors, and test suites.

WefyLabs previously possessed:
1. **A production-grade Razorpay order & signature verification subsystem** (`apps/api/app/modules/billing/services/razorpay_service.py`, `apps/api/app/routers/billing.py`, `apps/api/app/models/payment_models.py`, `apps/api/alembic/versions/0017_razorpay_billing.py`) verified through 19 passing tests in `apps/api/tests/test_razorpay_production.py` and `test_billing.py`.
2. **A Revenue Intelligence OS (Build 09)** (`apps/api/app/modules/revenue_intelligence/`, `apps/api/app/models/revenue_intelligence_b09_models.py`, `apps/api/alembic/versions/0039_build09_revenue_intelligence.py`) tracking touchpoint attribution, forecasts, leakage events, revenue anomalies, and basic unit economics records.
3. **An Observability, Telemetry & Operations OS (Build 12)** (`apps/api/app/modules/telemetry/`, `apps/web/src/app/operations/page.tsx`) capturing AI token consumption, latency, and costs per organization.
4. **An Outbox Architecture** (`apps/api/app/models/outbox_models.py`) and **Audit Log Layer** (`apps/api/app/models/audit_log.py`).
5. **A basic subscription table** (`apps/api/app/models/subscription.py`) tied to `brokers.id` with a simple status check.

However, several critical enterprise gaps and production risks existed:
- **No canonical billing domain model** linking Organization -> BillingAccount -> BillingCustomer -> Subscriptions -> Invoices -> Payments -> UsageMeters -> Entitlements.
- **Plans and pricing were hardcoded** in a Python dictionary `PLANS` in `razorpay_service.py` and partially in frontend UI components (`GlobalPricing.tsx`, `RazorpayCheckoutModal.tsx`), violating the rule that commercial plans must be database/configuration-driven and versioned.
- **No durable usage metering or aggregation engine**: Usage events (AI tokens, WhatsApp messages, lead exports, seats) were not immutably persisted, deduplicated with idempotency keys, aggregated into billing periods, or converted into invoice line items.
- **Entitlements were implicit or evaluated ad-hoc** rather than via a deterministic, server-side `EntitlementService` with fail-closed authorization.
- **Invoices, Invoice Lines, Credit Notes, and Adjustments were absent**: The system only created `payment_orders` and `payment_transactions`, with no recomputable invoice engine or append-only credit ledger.
- **Unit Economics were decoupled from actual billing**: Build 09 computed estimated unit economics from opportunity budget estimates rather than reconcilable invoices, provider fees, and cost ledger events.
- **Frontend Customer Billing Portal was missing**: `/settings/billing` did not exist; only a generic settings modal existed.

---

### Component Classification Matrix

| Subsystem / Component | File Location | Classification | Evidence / Audit Notes |
| :--- | :--- | :--- | :--- |
| **Razorpay SDK Integration & Signature Verification** | `apps/api/app/modules/billing/services/razorpay_service.py` | `VERIFIED THROUGH TEST` | Constant-time HMAC-SHA256 signature verification, webhook processing, order creation, refund logic; passes 19 tests in `test_razorpay_production.py`. |
| **Payment Order, Transaction & Refund Relational Models** | `apps/api/app/models/payment_models.py` | `VERIFIED IN CODE` | Normalized tables `payment_orders`, `payment_transactions`, `payment_refunds`, `payment_webhook_events`, `payment_audit_logs`. |
| **Payment State Machine** | `apps/api/app/modules/billing/services/payment_state_machine.py` | `VERIFIED THROUGH TEST` | Finite state machine preventing regression of terminal states (`CAPTURED`, `REFUNDED`). |
| **Authoritative Plan Catalog** | `razorpay_service.py:PLANS` & `GlobalPricing.tsx` | `HARDCODED / PRODUCTION RISK` | Hardcoded Python dictionary and React state. Must converge into canonical database-driven `Plan`, `PlanVersion`, and `PlanEntitlement` models. |
| **Broker-Centric Legacy Subscription** | `apps/api/app/models/subscription.py` | `LEGACY / PARTIAL` | Bound to `broker_id` instead of canonical multi-tenant `organization_id`. Needs convergence to multi-tenant `Subscription`. |
| **Entitlement Enforcement** | Scattered across routers / copilot tools | `PARTIAL / PRODUCTION RISK` | No centralized `EntitlementService`. Frontends show plans; backend lacks formal quota metering per billing period. |
| **Usage Metering & Event Ingestion** | `telemetry_controller.py`, `prometheus_collector.py` | `PARTIAL / BACKEND ONLY` | Prometheus metrics exist in memory for AI tokens, but no immutable append-only `UsageEvent` or `UsageAggregate` database ledger. |
| **Invoice & Invoice Line Engine** | None | `UNKNOWN / ABSENT` | No invoice generation, proration, tax, or discount calculation engine. |
| **Credit Ledger & Adjustments** | None | `UNKNOWN / ABSENT` | No append-only credit ledger (`CreditNote`, `CreditBalance`, `BillingAdjustment`). |
| **Revenue Intelligence Integration** | `apps/api/app/modules/revenue_intelligence/` | `VERIFIED THROUGH TEST` | Build 09 provides attribution and leakage events. Must converge with real billing events (invoices, payments, refunds). |
| **Cost Ledger** | None | `UNKNOWN / ABSENT` | Internal cost (vendor AI costs, WhatsApp costs) not logged to a dedicated immutable `CostEvent` ledger. |
| **Customer Billing UI** | `apps/web/src/app/settings/page.tsx`, `RazorpayCheckoutModal.tsx` | `FRONTEND ONLY / PARTIAL` | Checkout modal exists, but comprehensive `/settings/billing` page with plan comparisons, usage gauges, invoices, and credits is missing. |
| **Admin Operations Billing Center** | `apps/web/src/app/operations/page.tsx` | `PARTIAL` | System health checks billing status, but lacks detailed reconciliation, refund queues, and provider health telemetry. |

---

### Convergence Strategy (Zero Greenfield, Full Continuity)

1. **Retain and Extend Proven Subsystems:**
   - Preserve existing Razorpay adapter logic, signature verification, and webhook replay protection in `razorpay_service.py` while wrapping it in a canonical provider-agnostic `PaymentService`.
   - Maintain full backward compatibility for `/api/v1/billing/orders`, `/verify`, `/plans`, `/webhook`, and `/status`.
2. **Introduce Canonical Billing Domain:**
   - Implement `BillingAccount`, `Plan`, `PlanVersion`, `PlanEntitlement`, `Subscription`, `SubscriptionItem`, `UsageMeter`, `UsageEvent`, `UsageAggregate`, `BillingPeriod`, `Invoice`, `InvoiceLine`, `CreditNote`, `CreditBalance`, `CostEvent`, and `UnitEconomicsSnapshot` in `apps/api/app/models/billing_models.py`.
   - All tenant-owned records strictly reference `organization_id`.
3. **Connect to Build 09 & Build 12:**
   - Feed AI token and latency telemetry from Build 12 into `UsageEvent` and `CostEvent`.
   - Feed invoice, payment, refund, and credit transactions into Build 09's `RevenueReconciliationRecord` and `UnitEconomicsRecord`.
4. **Build Frontend Excellence:**
   - Create a clean, data-driven `/settings/billing` page adhering to the Stripe/Linear design aesthetic.
   - Zero hardcoded plan features or balances in React.
