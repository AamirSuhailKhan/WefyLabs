# WefyLabs Customer Portal Security & Compliance OS — Part 21

## 1. Security Architecture Matrix

| Security Threat | Defense Mechanism | Verified in Suite |
|---|---|---|
| **Identity Spoofing** | JWT signature verification (`role: portal_customer`); lead_id extracted from JWT claims | `test_get_current_portal_customer_valid_jwt` |
| **Broker/Customer Privilege Escalation** | Broker tokens rejected with `403 Forbidden` on `/api/v1/portal/*` endpoints | `test_rejects_broker_jwt_as_portal_customer` |
| **Expired Session Abuse** | JWT expiration validated; expired tokens rejected with `401 Unauthorized` | `test_rejects_expired_customer_token` |
| **Cross-Customer IDOR (Data Tampering)** | Customer cannot upload files to another customer's document ID (`404/403`) | `test_customer_cannot_upload_to_another_customers_document` |
| **Internal CRM Information Leak** | Query-level exclusion of `channel == 'internal_note'`; strip internal notes/margins | `test_internal_crm_notes_never_leak_to_customer` |
| **Token Replay / Brute Force** | Single-use SHA-256 invite token hashing with 7-day expiration | `test_duplicate_payment_proof_submission_idempotency` |
| **Financial State Forgery** | Uploading payment proof only sets `REPORTED`; never grants `VERIFIED` | `test_submit_payment_proof_sets_reported_not_verified` |
| **Adversarial AI Exploitation** | Prohibited concepts filter blocks commission, lead scoring, and internal note probing | `test_ai_blocks_probing_internal_commission_and_margin` |
| **Multi-Tenant Boundary Breach** | Organization ID resolved strictly from JWT; tenant cross-queries yield 404 | `test_independent_tenant_isolation` |

---

## 2. Authentication Boundary Implementation

In `app.modules.portal.dependencies`:
```python
async def get_current_portal_customer(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> PortalCustomerContext:
    token = credentials.credentials
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    
    role = payload.get("role")
    if role != "portal_customer":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Portal endpoints require portal_customer credentials."
        )
        
    lead_id = payload.get("sub")
    org_id = payload.get("organization_id")
    ...
```

---

## 3. Communication Boundary & External Providers

- **WhatsApp Integration**: Remains strictly **DISABLED** per non-negotiable guidelines.
- **SMS / Web Notifications**: Respect customer opt-in status, DND windows, and regional compliance.
- **Razorpay Integration**: Remains strictly in **TEST/MOCK** mode. No live credit card deductions or autonomous subscription charges are permitted.
