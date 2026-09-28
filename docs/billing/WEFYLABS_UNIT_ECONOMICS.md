# WefyLabs FinOps & Unit Economics Engine
**Master Build 13 — Canonical Unit Economics Architecture**

## 1. Unit Economics Philosophy
Unit economics cannot rely on synthetic estimates or frontend guesses. They must be derived from actual financial income and real variable operational expense events.

The WefyLabs Unit Economics Engine integrates:
1. **Revenue Source:** `CanonicalInvoice` settlements and `PaymentTransaction` records.
2. **Variable Expense Ledger:** Append-only `CostEvent` entries capturing LLM token expenses, WhatsApp API charges, and payment processing transaction fees.

---

## 2. Core Financial Metrics & Formulas
- **Monthly Recurring Revenue (MRR):**
  $$\text{MRR} = \sum_{\text{Active Subs}} \text{PlanVersion.price} \quad (\text{normalized to monthly})$$
- **Annual Recurring Revenue (ARR):**
  $$\text{ARR} = \text{MRR} \times 12$$
- **Net Revenue:**
  $$\text{Net Revenue} = \text{Gross Revenue} - \text{Refunds} - \text{Credit Adjustments}$$
- **Total Variable Cost:**
  $$\text{Variable Cost} = \text{AI Token Cost} + \text{WhatsApp API Cost} + \text{Gateway Transaction Fees}$$
- **Gross Profit:**
  $$\text{Gross Profit} = \text{Net Revenue} - \text{Total Variable Cost}$$
- **Gross Margin Percentage:**
  $$\text{Gross Margin \%} = \left(\frac{\text{Gross Profit}}{\text{Net Revenue}}\right) \times 100$$

---

## 3. Product Capability Unit Cost Dimensions
| Dimension | Revenue Stream | Variable Cost Driver |
| :--- | :--- | :--- |
| **AI Sales Agent & Copilot** | Monthly Subscription / AI Overage | Input/Output LLM tokens (Gemini / Anthropic) |
| **WhatsApp Lead Engagement** | Included Quota / WhatsApp Overage | Meta Cloud API conversation charges |
| **Document Processing (OCR)**| Document Overage fees | Vision / OCR processing compute |
| **Payment Collections** | Subscription Billing | 2% + GST payment gateway processing fee |

---

## 4. Tenant Profitability Snapshots
Daily snapshots are persisted to `UnitEconomicsSnapshot` per organization. Organizations whose variable costs exceed revenue (negative gross margin) are flagged for FinOps optimization review.
