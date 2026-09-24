# WEFYLABS CHANNEL PARTNER AUTHORIZATION & ZERO-TRUST SECURITY MATRIX
## Role-Based Access Control, API Boundary Isolation & Data Protection Policies

---

## 1. Threat Model & Security Principles

The **WefyLabs Channel Partner Portal** exposes supply-side availability and commission tracking to external broker agents, channel partners, and syndicates. Because channel partners are external parties operating in a competitive commercial ecosystem, the system enforces a **Zero-Trust Access Model**:

1. **Complete Tenant Isolation**: Every partner request is strictly filtered by the authenticated user's `organization_id`.
2. **Horizontal Partner Partitioning**: Partner $A$ can never view leads, commissions, agreements, or performance metrics of Partner $B$, even within the same real estate developer's project.
3. **Price Integrity & Margin Shielding**: Channel partners have access to the public `total_price` and standard floor plans, but have zero visibility into internal developer cost books, developer margin metrics, or unreleased private inventory.
4. **Append-Only Auditing**: Every status change, commission approval, and reservation request creates an immutable audit log entry.

---

## 2. Role-Based Access Control (RBAC) Matrix

| Entity / Action | Super Admin / Org Owner | Project Sales Manager | Internal Sales Agent | Channel Partner / Broker |
| :--- | :---: | :---: | :---: | :---: |
| **Developer Onboarding** | Full CRUD | Read-Only | Read-Only | No Access |
| **Project Creation** | Full CRUD | Full CRUD | Read-Only | Read-Only |
| **Unit Inventory Management** | Full CRUD | Full CRUD | Read-Only | Read-Only |
| **Hold / Reserve Unit** | Direct Action | Direct Action | Via Workflow | Request Only |
| **Price Book Alteration** | Full CRUD | Approve & Edit | Read-Only | Read-Only (Base) |
| **Register New Lead** | Yes | Yes | Yes | Yes (Protected) |
| **View Partner Commissions** | All Partners | Project Scope | None | Own Records Only |
| **Approve / Disburse Commission** | Full Authority | Verification Only | No Access | No Access |
| **KYC Document Verification** | Approve / Reject | Review Only | No Access | Submit Only |

---

## 3. API Security & Endpoint Boundary

All endpoints in `apps/api/app/modules/inventory/router.py` enforce institutional authentication guards:

### 1. Developer & Project Endpoints
- `POST /api/v1/inventory/developers`: Restricted to tenant administrative accounts.
- `GET /api/v1/inventory/projects`: Filtered strictly by tenant `organization_id`.

### 2. Unit Reservation & Locking Endpoints
- `POST /api/v1/inventory/units/{unit_id}/reserve`:
  - Validates `Idempotency-Key` header.
  - Acquires atomic distributed lock `inventory:unit:{unit_id}:reservation`.
  - Serializes concurrent reservation requests to prevent double-booking.

### 3. Channel Partner Endpoints
- `POST /api/v1/inventory/partners`: Requires valid business registration data (`rera_registration_number`, `pan_number`).
- `POST /api/v1/inventory/partners/{partner_id}/leads`:
  - Enforces first-touch attribution.
  - Queries active lead protections within the 90-day window.
  - Rejects conflicting duplicates with HTTP 409 Conflict.
- `GET /api/v1/inventory/commissions`: Filtered by `partner_id` parameter matched to the authenticated broker context.

---

## 4. Multi-Tenant Verification & Integrity Testing

Tenant isolation is verified systematically in `tests/test_part19_security.py`:
- Cross-tenant developer lookup returns `404 Not Found`.
- Cross-tenant project listing returns `[]` (empty list).
- Cross-tenant unit retrieval returns `404 Not Found`.
- Cross-tenant channel partner querying returns `404 Not Found`.
- Cross-tenant unit status transitions trigger strict tenant rejection.
