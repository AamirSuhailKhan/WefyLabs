# WEFYLABS — ACCESS CONTROL & RBAC POLICY

**Document Reference:** SEC-POL-002  
**Classification:** INTERNAL  
**Authority:** Identity Architect + Application Security Lead  
**Last Updated:** 2026-09-27 (Master Build 11)  
**Status:** ACTIVE — PRODUCTION TRUTH  

---

## 1. IDENTITY & MEMBERSHIP MODEL

Access control in WefyLabs operates across five distinct architectural layers:
```text
ORGANIZATION (Tenant Boundary)
  └── USER (Authenticated Principal)
        └── MEMBERSHIP (Relationship to Organization)
              └── ROLE (Coarse Access Grouping)
                    └── PERMISSION (Fine-Grained Capability)
```

- **Organization:** The primary legal, financial, and data isolation boundary.
- **User / Broker:** The authenticated human or service principal.
- **Membership:** A User's explicit enrollment in an Organization with an assigned role.
- **Role:** One of 10 canonical roles defining authorized scope.
- **Permission:** Granular capabilities evaluated at runtime (e.g. `lead.read`, `billing:manage`).

---

## 2. THE 10 CANONICAL ROLES

| Role | Operational Scope | Export Access | Billing / Admin |
| :--- | :--- | :---: | :---: |
| **OWNER** | Full root tenant ownership, all permissions (`*`), organization lifecycle | ✅ Yes | ✅ Full Admin |
| **ADMIN** | CRM configuration, user management, policy settings, integrations | ✅ Yes | ✅ Full Admin |
| **MANAGER** | Team oversight, pipeline tracking, assignment, lead/property edit | ❌ No | ❌ No |
| **SALES** | Lead interaction, conversation messaging, deal mutation, appointments | ❌ No | ❌ No |
| **AGENT** | Identical to SALES (backwards-compatible alias for field agents) | ❌ No | ❌ No |
| **MARKETING** | Campaign design, lead generation intake, property marketing views | ❌ No | ❌ No |
| **FINANCE** | Payment verification, billing management, revenue intelligence export | ✅ Revenue Only | ❌ No Org Admin |
| **ANALYST** | Read-only reporting access across leads, deals, properties & revenue export | ✅ Revenue Only | ❌ No Mutations |
| **SUPPORT** | Customer service read-only access for inquiry investigation | ❌ No | ❌ No |
| **READ_ONLY** | Strictly read-only observational access; all writes/exports/deletes blocked | ❌ No | ❌ No |

---

## 3. PERMISSION TAXONOMY & BIDIRECTIONAL ALIASING

WefyLabs natively supports both dot-notation and colon-notation with symmetric aliasing:

- **Leads:** `lead.read` ↔ `leads:read`, `lead.write` ↔ `leads:create` / `leads:update`, `lead.export` ↔ `leads:export`, `lead.delete` ↔ `leads:delete`.
- **Properties:** `property.read` ↔ `properties:read`, `property.write` ↔ `properties:create` / `properties:update`.
- **Opportunities:** `opportunity.read` ↔ `deals:read`, `opportunity.write` ↔ `deals:create` / `deals:update`.
- **Conversations:** `conversation.read` ↔ `conversations:read`, `conversation.send` ↔ `conversations:send`.
- **Bookings:** `booking.read` ↔ `bookings:read`, `booking.create` ↔ `bookings:create`, `booking.update` ↔ `bookings:update`.
- **Financials:** `payment.read` ↔ `billing:read`, `payment.write` ↔ `billing:manage`, `revenue.read` ↔ `revenue:read`, `revenue.export` ↔ `revenue:export`.
- **System:** `ai.use`, `ai.execute`, `workflow.manage`, `integration.manage`, `organization.manage`, `audit.read` ↔ `audit:view`.

---

## 4. PRIVILEGE ESCALATION DEFENSE

1. **Role Tampering:** Requests containing modified roles in bodies, query parameters, or client headers are ignored; roles are authoritative only when queried directly from `OrganizationMember` in the database.
2. **Owner Appointment:** Only an existing `OWNER` can promote another member to `OWNER`.
3. **Session Invalidation:** Modifying a member's role triggers immediate session invalidation and audit logging.
