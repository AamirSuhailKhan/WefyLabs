# WefyLabs Customer Payment Visibility & Escrow Accounting OS — Part 21

## 1. Accounting Visibility vs. Financial Processing

WefyLabs enforces a strict distinction between **Accounting Transparency** and **Autonomous Financial Operations**:

- **Allowed**: Read-only visibility into contractual payment milestones, installment amounts, due dates, escrow bank details, and payment verification status.
- **Allowed**: Customer submission of wire transfer receipts, bank remittance slips, or manager cheque copies (`POST /api/v1/portal/payments/proof`).
- **Prohibited**: Autonomous debiting of customer bank accounts.
- **Prohibited**: Live payment processing via Razorpay (Razorpay remains strictly in `TEST/MOCK` mode).
- **Prohibited**: Automatic transition to `VERIFIED` status upon document upload.

---

## 2. Payment Proof Verification Lifecycle

```
[Customer Uploads Wire Transfer Slip]
                │
                ▼
Record created in `customer_payment_proofs`
Status: REPORTED
(Never VERIFIED automatically)
                │
                ▼
Finance Team Audits Official Escrow Bank Ledger
                │
      ┌─────────┴─────────┐
      ▼                   ▼
   VERIFY              REJECT
      │                   │
Updates proof to      Updates proof to
VERIFIED              REJECTED with reason
Updates booking       Customer notified in
schedule installment  portal to check transfer
to VERIFIED
```

---

## 3. Milestone Status Taxonomy

| Milestone Status | Meaning | Customer Action |
|---|---|---|
| `UPCOMING` | Future construction milestone not yet due | Informational |
| `DUE` | Milestone is payable now | Remit wire transfer to project escrow |
| `REPORTED` | Customer uploaded payment proof; pending audit | None (Under audit) |
| `VERIFIED` | Escrow account confirmed funds received | Verified (Receipt available) |
| `OVERDUE` | Past due date without verified payment | Contact advisor / finance team |
| `CANCELLED` | Milestone modified by mutual agreement | Informational |

---

## 4. Idempotency & Financial Safety

- `CustomerPaymentProofSubmitRequest` supports an optional `idempotency_key`.
- If a customer double-clicks "Submit Proof" or retries due to network failure, the existing proof record is returned without creating duplicate accounting events.
- Client-submitted payment amounts are treated as "reported amounts" and never overwrite the authoritative contractual obligation recorded in `DealBooking.payment_schedule`.
