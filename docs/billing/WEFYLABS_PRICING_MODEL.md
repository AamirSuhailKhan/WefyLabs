# WefyLabs Pricing Model & Commercial Catalog
**Master Build 13 — Canonical Catalog & Plan Versioning**

## 1. Catalog Architecture
WefyLabs enforces a strict separation of:
- **Product:** Logical grouping of business capabilities (e.g. CRM Real Estate Suite).
- **Plan:** Commercial package tier (e.g. Free, Starter, Pro, Enterprise).
- **Plan Version:** Immutable commercial terms (price, interval, currency, included entitlements).
- **Add-on / Meter:** Usage-based billable dimensions (overage rates, token buckets).

Plans are never hardcoded in client application bundles. The database is authoritative, accessed via `CatalogService`.

---

## 2. Standard Production Plans

| Plan Code | Display Name | Monthly Price (INR) | Annual Price (INR) | Included AI Messages | Included Team Seats | Included WhatsApp | Overage Policy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`free`** | Developer Free | ₹0 / mo | ₹0 / yr | 50 / mo | 1 seat | 0 (Trial only) | Hard Block |
| **`starter`** | Starter Suite | ₹2,999 / mo | ₹29,990 / yr | 250 / mo | 2 seats | 500 / mo | ₹1.50 / msg |
| **`pro`** | Pro Broker | ₹4,999 / mo | ₹49,990 / yr | 1,000 / mo | 10 seats | 2,500 / mo | ₹1.25 / msg |
| **`enterprise`**| Enterprise Elite | ₹14,999 / mo | ₹149,990 / yr | Unlimited | Unlimited | 10,000 / mo | Custom Contract|

---

## 3. Immutability & Versioning Rules
1. **Never Mutate Active Versions:** Once a customer subscribes to a `PlanVersion`, its `price`, `interval`, and `entitlements` cannot be altered in place.
2. **Version Incrementation:** When price points or included quotas are updated, a new `PlanVersion` record is created (e.g. `version=2`). Existing subscriptions remain on `version=1` until explicit upgrade or grandfathered transition.
3. **Proration Formula:**
   When an upgrade occurs mid-cycle, unused credit on the existing plan is calculated deterministically via integer-safe seconds:
   $$\text{Unused Credit} = \text{Old Price} \times \frac{\text{Remaining Seconds in Cycle}}{\text{Total Seconds in Cycle}}$$
   The unused credit is applied as a deduction against the new plan version's initial invoice.
