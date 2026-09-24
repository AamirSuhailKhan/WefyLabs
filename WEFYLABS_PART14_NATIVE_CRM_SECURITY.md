# WEFYLABS PART 14 — NATIVE CRM SECURITY SPECIFICATION
============================================================
**Tenant Isolation, RBAC, IDOR Defenses & Compliance Architecture**
*WefyLabs Revenue Operating System*

---

## 1. Multi-Tenant Isolation: The Fundamental Principle

In WefyLabs, tenant isolation is absolute and non-negotiable. 

Under no circumstances can Tenant A view, count, autocomplete, search, mutate, or export records belonging to Tenant B.
- **Tenant Context**: Enforced via verified broker authorization headers (`get_current_broker`), resolving `broker.id` and `broker.organization_id`.
- **Query Boundary**: Every database query explicitly mandates `broker_id == broker.id` or `organization_id == broker.organization_id`.
- **No Client Trust**: Client-supplied `organization_id`, `broker_id`, or `tenant_id` parameters in request bodies are ignored.

---

## 2. Insecure Direct Object Reference (IDOR) Defense Matrix

Every native CRM endpoint verifies that the requested entity belongs to the authenticated tenant before returning data or applying changes.

| Resource Type | IDOR Test Endpoint | Authorization Mechanism | Forbidden Response |
|---|---|---|---|
| **Customer** | `GET /api/v1/crm/customers/{id}` | Verified `Lead.broker_id == broker.id` | `404 Not Found` |
| **Lead** | `GET /api/v1/crm/leads/{id}` | Verified `Lead.broker_id == broker.id` | `404 Not Found` |
| **Stage Transition** | `POST /api/v1/crm/leads/{id}/stage` | Verified `Lead.broker_id == broker.id` | `404 Not Found` |
| **Assignment** | `POST /api/v1/crm/leads/{id}/assign`| Verified `Lead.broker_id == broker.id` & target broker in org | `404 Not Found` / `403 Forbidden` |
| **Deal / Opportunity** | `GET /api/v1/crm/opportunities/{id}`| Verified `DealTransaction.broker_id == broker.id` | `404 Not Found` |
| **Task** | `PATCH /api/v1/crm/tasks/{id}` | Verified `Task.broker_id == broker.id` | `404 Not Found` |
| **Note** | `GET /api/v1/crm/notes` | Scoped to authenticated tenant leads only | Empty List / `404 Not Found` |
| **Appointment** | `GET /api/v1/crm/appointments` | Verified `SchedulingMeeting.broker_id == broker.id` | Filtered list |
| **Universal Search** | `GET /api/v1/crm/search` | Strict tenant predicate across all sub-queries | Zero cross-tenant leakage |
| **Bulk Actions** | `POST /api/v1/crm/bulk/leads` | Pre-verification of every ID in batch | `403 Forbidden` |

---

## 3. Global Search Tenant Isolation & Side-Channel Prevention

Search is a common attack vector for cross-tenant data leakage. WefyLabs implements:
1. **Zero Side-Channel Leakage**: Cross-tenant queries never reveal matching counts, suggestions, or timing differences.
2. **Deterministic Filters**: The SQL query for every entity type (`Lead`, `DealTransaction`, `Task`, `PropertyListing`) includes an explicit `WHERE broker_id = :broker_id` filter before executing string matching.
3. **Normalized Input**: Search queries are stripped of wildcard injection characters and normalized before evaluation.

---

## 4. Bulk Operation Security

Malicious clients might attempt to include foreign IDs in bulk operations:
```json
{
  "operation": "change_stage",
  "lead_ids": [
    "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"  // Belongs to Tenant B
  ],
  "params": {"stage": "qualified"}
}
```
**WefyLabs Technical Defense**:
- The server queries `SELECT id FROM leads WHERE broker_id = :broker_id AND id IN (:lead_ids)`.
- If `len(found_ids) != len(requested_ids)`, the server immediately aborts the operation and responds with:
  `HTTP 403 Forbidden: "One or more requested leads do not belong to the authenticated organization."`
- Zero partial updates are committed.

---

## 5. AI Workforce & Action Security

1. **No Autonomous Destructive Actions**: The AI Workforce cannot autonomously delete customers, purge deal records, reassign bulk owners, or modify contract agreed values.
2. **Action Gating**: All consequential commercial actions are gated by:
   - `READ`: Safe contextual inspection.
   - `SUGGEST`: Proposed intervention surfaced in Customer 360 or Command Center.
   - `CONFIRM`: Human operator explicit approval.
   - `EXECUTE`: Safe invocation through authorized domain services.
3. **Actor Identity Integrity**: The actor identity `AI_AGENT` cannot be spoofed by frontend clients; it is attached strictly by the backend AI Gateway.
4. **Prompt Injection Defense**: Customer inquiry text is sanitized and treated as untrusted data, preventing instruction injection from altering CRM business policies.

---

## 6. Regulatory Compliance & Immutable Audit Logging

All administrative, stage, assignment, bulk, and financial actions generate immutable records in `audit_logs`:
- **SOC2 Type II / ISO27001 / GDPR Compliant**:
  - `actor_id`: Broker UUID.
  - `actor_type`: `user`, `system`, or `ai`.
  - `action`: Specific action code (e.g. `lead.stage_changed`, `lead.bulk_change_stage`).
  - `resource_type` and `resource_id`.
  - `changes`: JSON diff containing before and after states.
  - Records cannot be modified or deleted through CRM APIs.
