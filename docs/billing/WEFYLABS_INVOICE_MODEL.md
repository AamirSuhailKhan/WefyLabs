# WefyLabs Canonical Invoice & Money Model
**Master Build 13 — Canonical Invoice Engine**

## 1. Zero Floating-Point Money Philosophy
Financial arithmetic must never suffer from IEEE 754 binary floating-point rounding errors (e.g. `0.1 + 0.2 = 0.30000000000000004`).
The WefyLabs billing domain enforces:
- Python `Decimal` objects with `ROUND_CEILING` or `ROUND_HALF_UP` rounding.
- Canonical `Money(amount: Decimal, currency: str)` immutable value object.
- Minor unit conversions (`paise` for INR, `cents` for USD) exclusively for external payment gateway payload transmission.
- Strict currency matching: attempting to add `Money(10, 'INR')` and `Money(10, 'USD')` raises `CurrencyMismatchError`.

---

## 2. Invoice Generation Pipeline
```
[BillingPeriod Closed]
         |
         v
1. Base Subscription Line Item
   (Quantity: 1.0, UnitPrice: PlanVersion.price)
         |
         v
2. Evaluate Metered Overages
   (Aggregate Usage > Plan Quota -> Overage Line Item added)
         |
         v
3. Subtotal Accumulation
   (Subtotal = sum(Line.subtotal))
         |
         v
4. Tax Computation
   (Tax Amount = (Subtotal * TaxRatePct) rounded)
         |
         v
5. Credit Deduction
   (Available credits fetched from CreditLedger -> auto-applied up to GrossTotal)
         |
         v
6. Net Total Owed
   (Total = GrossTotal - CreditsApplied)
```

---

## 3. Invoice States
- `DRAFT`: Provisional computation pending cycle close.
- `OPEN`: Finalized and payable.
- `PAYMENT_PENDING`: Gateway transaction in progress.
- `PAID`: Payment verified and recorded.
- `PARTIALLY_PAID`: Incomplete remittance.
- `PAST_DUE`: Due date passed without full settlement.
- `VOID`: Erroneous invoice cancelled without financial side effect.
- `REFUNDED`: Full or partial payment reversed.
