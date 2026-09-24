# WefyLabs Customer Document Workflow OS — Part 21

## 1. Document Lifecycle & State Machine

WefyLabs implements a multi-party document verification engine that bridges customer self-service uploads with rigorous internal legal and compliance review.

```
       [Broker / System]
               │
        Creates Request (REQUIRED)
               │
               ▼
       [Customer Portal]
               │
      Uploads Document File URL
               │
               ▼
        Status: IN_REVIEW (Internal: UPLOADED)
               │
      ┌────────┴────────┐
      ▼                 ▼
[Broker Review]   [Compliance Audit]
      │                 │
      ├─────────────────┼──────────────────┐
      ▼                 ▼                  ▼
   APPROVE           REJECT        REQUEST REPLACEMENT
      │                 │                  │
Status: APPROVED  Status: ACTION_REQUIRED  Status: ACTION_REQUIRED
(Internal:        (rejection_reason        (rejection_reason
 VERIFIED)         shown to customer)       shown to customer)
```

---

## 2. Customer-Safe Status Mapping

To prevent confusing internal compliance jargon from reaching customers, statuses are projected cleanly:

| Internal DB Status (`DealDocument.status`) | Customer-Visible Status (`customer_status`) | UI Badge Style | Action Required by Customer |
|---|---|---|---|
| `REQUIRED` | `ACTION_REQUIRED` | Red / Rose | Upload requested file |
| `UPLOADED` | `IN_REVIEW` | Amber / Clock | Await compliance review (24h) |
| `VERIFIED` | `APPROVED` | Green / Check | None (Completed) |
| `REJECTED` | `ACTION_REQUIRED` | Red / Rose | Re-upload updated file with reason |
| `EXPIRED` | `ACTION_REQUIRED` | Amber / Clock | Re-upload fresh valid document |

---

## 3. Replacement & Version Preservation

When a customer re-uploads a rejected or expired document:
1. Prior review rejection notes are cleared on the active document record.
2. `uploaded_at` timestamp is updated to current UTC.
3. `uploaded_by_id` records the customer `lead_id`.
4. The document transitions immediately to `IN_REVIEW` (internal `UPLOADED`).
5. An audit log entry is preserved, preventing silent overwrite of transaction history.

---

## 4. Document Security & Storage Isolation

- **IDOR Protection**: Customers can upload only to documents explicitly linked to their active deal (`DealDocument.deal_id == Deal.id AND Deal.lead_id == customer_id`).
- Attempting to upload to another customer's document ID fails with `404 Not Found or unauthorized`.
- Storage references are restricted to verified tenant storage domains.
