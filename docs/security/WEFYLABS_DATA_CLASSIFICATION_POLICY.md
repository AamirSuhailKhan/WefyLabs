# WEFYLABS — DATA CLASSIFICATION & PII PROTECTION POLICY

**Document Reference:** SEC-POL-003  
**Classification:** INTERNAL  
**Authority:** Privacy Architect + Data Governance Engineer  
**Last Updated:** 2026-09-27 (Master Build 11)  
**Status:** ACTIVE — PRODUCTION TRUTH  

---

## 1. THE 4 CANONICAL DATA CLASSIFICATIONS

Every data attribute processed by WefyLabs is mapped to one of four canonical classifications:

```text
┌─────────────────┬─────────────────────────────────────────────────────────────┐
│ Classification  │ Description & Handling Requirements                        │
├─────────────────┼─────────────────────────────────────────────────────────────┤
│ 1. PUBLIC       │ Freely sharable; property marketing descriptions, images,   │
│                 │ public organization slug, brochures, floor plans.           │
├─────────────────┼─────────────────────────────────────────────────────────────┤
│ 2. INTERNAL     │ Operational data visible to tenant team members; stage,    │
│                 │ lead assignment, tasks, property internal amenities.        │
├─────────────────┼─────────────────────────────────────────────────────────────┤
│ 3. CONFIDENTIAL │ PII & commercial details; buyer phone, buyer email, budget, │
│                 │ conversation transcripts, offer prices, booking amounts.   │
├─────────────────┼─────────────────────────────────────────────────────────────┤
│ 4. RESTRICTED   │ High-risk security and financial credentials; payment method│
│                 │ tokens, client secrets, commission splits, owner private   │
│                 │ contracts, API keys, JWT secrets, database connection URLs. │
└─────────────────┴─────────────────────────────────────────────────────────────┘
```

---

## 2. DATA INVENTORY MAPPING

| Entity | Field | Classification | Masking Rule |
| :--- | :--- | :--- | :--- |
| **Lead** | `name` | CONFIDENTIAL | None (Full for Sales/Manager) |
| **Lead** | `phone` | CONFIDENTIAL | Masked for Read-Only (`+91 99****1234`) |
| **Lead** | `email` | CONFIDENTIAL | Masked for Read-Only (`j***n@example.com`) |
| **Lead** | `budget` | CONFIDENTIAL | Visible to authenticated tenant staff |
| **Property** | `price` / `location` | PUBLIC | Publicly renderable |
| **Property** | `owner_contact` | RESTRICTED | Redacted for AGENT/SALES/READ_ONLY (`[RESTRICTED]`) |
| **Property** | `commission_rate`| RESTRICTED | Restricted to OWNER/ADMIN/FINANCE |
| **Payment** | `card_last4` | CONFIDENTIAL | Permitted in billing receipts |
| **Payment** | `payment_method_token`| RESTRICTED| Strictly encrypted; hidden from UI/logs |
| **AI Context** | `system_prompt` | RESTRICTED | Delimited and guarded from output |
| **AI Context** | `api_keys` | RESTRICTED | Defused via pre-prompt scrubber |

---

## 3. PII & SECRET REDACTION ENGINE

WefyLabs implements an automated regex and heuristic scrubbing pipeline (`scrub_pii_and_secrets`) active on:
- All log outputs (Console, CloudWatch, Prometheus metric labels)
- Outbound AI Gateway prompts (preventing customer secrets from reaching external LLMs)
- Security Event and Audit Log change tracking payloads
- Error diagnostics and response bodies

Patterns neutralized:
- Bearer tokens (`Bearer [REDACTED_TOKEN]`)
- API keys, passwords, and tokens (`api_key: [REDACTED_SECRET]`)
- Credit card numbers (`[REDACTED_CARD]`)
- Unsolicited customer emails and phone numbers in system traces
