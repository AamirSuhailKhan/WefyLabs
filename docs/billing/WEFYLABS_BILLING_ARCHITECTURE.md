# WefyLabs Billing & Revenue OS Architecture
**Master Build 13 — Canonical Billing Architecture**

## 1. Overview & Core Philosophy
The WefyLabs Billing Platform transforms the CRM into a financially auditable, entitlement-aware, subscription-capable Revenue OS. It operates under 25 absolute operating principles:
1. **Database Authority:** The internal PostgreSQL database is the single authoritative source of truth. Payment providers (Razorpay, Stripe) are treated as external, untrusted downstream/upstream networks.
2. **Deterministic Financial Math:** Zero floating-point arithmetic. All monetary transactions, taxes, proration calculations, and ledger balances use `Decimal` with integer minor units (paise/cents) through the canonical `Money` and `MoneyCalculator` domain objects.
3. **Server-Side Canonical Enforcement:** Frontend UI never constitutes a security boundary. All entitlement evaluations, subscription state verifications, and quota gates execute server-side outside LLM influence.
4. **Tenant Isolation:** Every billing entity (`BillingAccount`, `Subscription`, `BillingPeriod`, `UsageEvent`, `Invoice`, `CreditLedgerEntry`) strictly carries an `organization_id` foreign key. Cross-tenant reads and mutations are prevented at the database and service layers.
5. **Append-Only Immutable Event Ledgers:** Usage events, credit adjustments, cost telemetry, and provider webhook notifications are stored append-only. Balance calculations are derived from historical event replay.

---

## 2. High-Level Architecture Diagram
```
                     +----------------------------------+
                     |    Customer & Admin Web UI       |
                     |  /settings/billing & Admin Portal |
                     +-----------------+----------------+
                                       | HTTPS (Bearer JWT / Org Context)
                                       v
                     +----------------------------------+
                     |    FastAPI Billing Gateway       |
                     |  /api/v1/billing/portal & admin  |
                     +-----------------+----------------+
                                       |
     +---------------------------------+---------------------------------+
     |                                 |                                 |
     v                                 v                                 v
+-----------------------+   +-----------------------+   +-----------------------+
|  EntitlementService   |   | SubscriptionEngine    |   | UsageMeteringService  |
|  - HARD/SOFT limits   |   | - Plan Lifecycle      |   | - Deduplication       |
|  - Grace Period Gate  |   | - Proration Calc      |   | - Rollup Aggregation  |
|  - Pre-Action Auth    |   | - Billing Periods     |   | - Append-only Events  |
+-----------------------+   +-----------------------+   +-----------------------+
     |                                 |                                 |
     +---------------------------------+---------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                             InvoiceEngine                                     |
|  - Deterministic Line Items (Base Subscription + Meter Overage)               |
|  - Automated Credit Application (Append-only CreditLedger)                    |
|  - Recomputable GST / Tax Breakdown                                           |
+--------------------------------------+----------------------------------------+
                                       |
                                       v
+-------------------------------------------------------------------------------+
|                      PaymentService & RazorpayAdapter                         |
|  - Provider Abstraction (Order creation, Checkout tokenization, Verification)  |
|  - Webhook Pipeline: HMAC-SHA256 Sig -> Deduplication -> Normalized Ingestion |
+--------------------------------------+----------------------------------------+
                                       |
     +---------------------------------+---------------------------------+
     |                                                                   |
     v                                                                   v
+----------------------------------+               +----------------------------------+
|      FinOps & Cost Ledger        |               |   BillingReconciliationService   |
|  - Direct AI token & WhatsApp    |               |  - Detects orphan/missing payments|
|  - Unit Economics (MRR, ARR, GM%)|               |  - Flags refund & aggregate drift |
+----------------------------------+               +----------------------------------+
```

---

## 3. Canonical Domain Entities
1. **`BillingAccount`**: Tracks tenant payment identity, status (`ACTIVE`, `PAST_DUE`, `SUSPENDED`, `CANCELLED`), billing contact email, and provider customer reference without storing raw PCI payment instruments.
2. **`Plan` & `PlanVersion`**: Canonical commercial catalog. Plan versions are immutable once subscribed. Historical contracts are preserved across version increments.
3. **`PlanEntitlement`**: Defines capabilities granted by a plan version (`INTEGER_LIMIT`, `BOOLEAN`, `UNLIMITED`) with enforcement policies (`HARD_LIMIT`, `SOFT_LIMIT`, `OVERAGE`).
4. **`CanonicalSubscription`**: Represents tenant commitment to a plan version. Managed via an auditable finite state machine (`TRIALING`, `ACTIVE`, `PAST_DUE`, `PAUSED`, `CANCEL_AT_PERIOD_END`, `CANCELLED`, `EXPIRED`).
5. **`BillingPeriod`**: Non-overlapping operational cycle windows (`OPEN`, `CLOSED`, `BILLED`). Guarantees exactly one active billing period per subscription.
6. **`UsageMeter`**: Catalog of measurable product telemetry (e.g. `AI_REQUEST`, `AI_INPUT_TOKEN`, `WHATSAPP_MESSAGE`, `DOCUMENT_PROCESSED`).
7. **`UsageEvent`**: Append-only usage ledger entry with deduplication key (`idempotency_key`), actor provenance, and timestamp.
8. **`UsageAggregate`**: Period-level rollups recomputed from immutable usage events.
9. **`CanonicalInvoice` & `InvoiceLine`**: Financial demand for payment. Lines reference plan subscription charges and metered overage items.
10. **`CreditBalance` & `CreditLedgerEntry`**: Append-only credits ledger with directional event types (`CREDIT_ISSUED`, `CREDIT_APPLIED`, `CREDIT_EXPIRED`, `CREDIT_REVERSED`).
11. **`CostEvent`**: Internal operational expense telemetry (LLM provider token costs, WhatsApp message delivery costs, payment processor fees).
12. **`UnitEconomicsSnapshot`**: Historical financial health records tracking gross revenue, net revenue, variable costs, gross margin percentage, and MRR.
