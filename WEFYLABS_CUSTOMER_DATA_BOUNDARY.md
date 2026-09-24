# WefyLabs Customer Data Boundary OS — Part 21

## 1. Principles of Data Isolation

The WefyLabs customer data boundary adheres to strict, non-negotiable security rules:

1. **Zero-Trust Client Identity**: Customer identity (`lead_id`) and tenancy (`organization_id`) are derived exclusively from cryptographically verified JWT tokens. Client-provided path variables or headers cannot override this context.
2. **Dedicated Projection Layer**: Internal SQLAlchemy ORM models (`Lead`, `Deal`, `DealBooking`, `UnifiedMessage`) are **never returned directly** across the `/api/v1/portal/*` boundary.
3. **Dedicated Customer DTOs**: Only explicit, customer-safe Pydantic models are serialized to JSON.

---

## 2. Redaction Matrix

The following internal CRM fields are stripped at the serialization boundary:

```
+─────────────────────────────────────────+──────────────────────────────────────────+
| Internal Model                          | Redacted / Prohibited Fields            |
+─────────────────────────────────────────+──────────────────────────────────────────+
| Deal                                    | gross_commission, net_commission,       |
|                                         | commission_percentage, partner_split_id, |
|                                         | closing_probability_pct, risk_level,     |
|                                         | ai_internal_notes, risk_factors          |
+─────────────────────────────────────────+──────────────────────────────────────────+
| Lead                                    | score, ai_urgency_score, lead_score_tier,|
|                                         | internal_comments, conversion_velocity,  |
|                                         | qualification_reasoning, internal_notes  |
+─────────────────────────────────────────+──────────────────────────────────────────+
| UnifiedMessage                          | channel == 'internal_note',              |
|                                         | supervisor_comment, sentiment_score,     |
|                                         | ai_coaching_suggestion                   |
+─────────────────────────────────────────+──────────────────────────────────────────+
| DealBooking                             | broker_commission_due, agency_split,     |
|                                         | override_approval_manager_id             |
+─────────────────────────────────────────+──────────────────────────────────────────+
| DealCommission                          | ENTIRE MODEL IS PROHIBITED FROM PORTAL   |
+─────────────────────────────────────────+──────────────────────────────────────────+
```

---

## 3. Communication Channel Sanitization

In `CustomerPortalService.get_messages()`:
```python
stmt = select(UnifiedMessage).where(
    UnifiedMessage.lead_id == lead_uuid,
    UnifiedMessage.channel != "internal_note"  # Strict confidentiality boundary
).order_by(UnifiedMessage.created_at)
```
- Messages marked with `channel == "internal_note"` or internal supervisor reviews are filtered at the database query level.
- Even if a customer attempts to query messages directly, internal notes never reach application memory.

---

## 4. Multi-Tenant Enforcement

Every portal query executes with a composite filter:
- Customer lead match: `Deal.lead_id == lead_uuid`
- Active deal filter: `Deal.status == "ACTIVE"`
- Soft delete guard: `Deal.deleted_at.is_(None)`
- Organization boundary: `Lead.organization_id == organization_id`

Cross-tenant access or cross-customer access yields an immediate `404 Not Found` or `403 Forbidden`.
