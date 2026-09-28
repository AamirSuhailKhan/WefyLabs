# CANONICAL TENANCY CONTRACT & ARCHITECTURAL SPECIFICATION

**Author:** Principal Software Architect + Database Reliability Engineer  
**Date:** 2026-09-28T17:55:00+05:30  
**Phase:** Phase 0 Production Foundation Hardening (P0.2)  
**Contract Version:** `1.0.0-canonical`  

---

## 1. THE CANONICAL TENANCY MODEL

Multi-tenancy in WefyLabs is strictly organizational:

```text
       ┌────────────────────────┐
       │      Organization      │ (The Customer / Tenant)
       │    (organization_id)   │
       └───────────┬────────────┘
                   │ 1 : N
       ┌───────────┴────────────┐
       │   OrganizationMember   │ (Role, Membership, Scoping)
       │   (role: owner/agent)  │
       └───────────┬────────────┘
                   │ N : 1
       ┌───────────┴────────────┐
       │      Broker / User     │ (Human Identity / Actor)
       │       (broker_id)      │
       └────────────────────────┘
                   │
                   ▼
  Tenant-Owned Domain Entities:
  - Leads (organization_id FK)
  - Property Listings (organization_id FK)
  - Deals / Transactions (organization_id FK)
  - Meetings / Viewings (organization_id FK)
  - Campaigns / Marketing (organization_id FK)
  - Knowledge Documents (organization_id)
  - Audit Logs / Activity (organization_id FK)
  - Storage Objects (`organizations/{organization_id}/...`)
```

### Absolute Rules:
1. **`organization_id` ALWAYS means Organization Primary Key (`organizations.id`).** It is NEVER an alias for `broker_id`.
2. **`broker_id` ALWAYS means Human User Identity (`brokers.id`).** It represents the individual agent/actor acting within a tenant.
3. **No Cross-Tenant Queries:** Every tenant query must filter by `organization_id == requested_tenant_org_id`.
4. **No Caller-Asserted Organization:** Tenants are resolved server-side from authenticated session memberships (`OrganizationMember.broker_id == current_broker.id`). A user cannot access an organization they do not belong to.
5. **Legacy Compatibility Window:** Legacy records created prior to multi-organization support where `organization_id IS NULL` use explicit dual-read filtering:
   ```python
   or_(
       Model.organization_id == org_id,
       and_(Model.organization_id.is_(None), Model.broker_id == org_id)
   )
   ```
   All newly created records MUST write explicit, non-null `organization_id`.

---

## 2. TENANT-OWNED MODEL INVENTORY & STATUS

| Model | Table | `organization_id` Column | FK to `organizations.id` | Nullable? | Status |
|---|---|---|---|---|---|
| `Organization` | `organizations` | `id` (PK) | N/A | No | Canonical Root |
| `OrganizationMember` | `organization_members` | `organization_id` | Yes (CASCADE) | No | Canonical Membership |
| `Broker` | `brokers` | None (User PK) | None | N/A | Human Actor |
| `Lead` | `leads` | `organization_id` | Yes (CASCADE) | Nullable (legacy) | Canonical Tenant Entity |
| `PropertyListing` | `property_listings` | `organization_id` | Yes (CASCADE) | Nullable (legacy) | Canonical Tenant Entity |
| `DealTransaction` | `deal_transactions` | `organization_id` | Adding in Phase 0 | Nullable | Fixed in Tenancy Hardening |
| `SchedulingMeeting` | `scheduling_meetings` | `organization_id` | Yes (String UUID) | No | Canonical Tenant Entity |
| `CalendarAccount` | `calendar_accounts` | `organization_id` | Yes (String UUID) | No | Canonical Tenant Entity |
| `Conversation` | `conversations` | Scoped via `Lead` | Via `lead.organization_id` | No | Scoped Entity |
| `Message` | `messages` | Scoped via `Conversation` | Via conversation/lead | No | Scoped Entity |
| `RevenueOpportunity` | `revenue_opportunities` | `organization_id` | Yes | No | Canonical Tenant Entity |
| `RevenueFunnelSnapshot` | `revenue_funnel_snapshots`| `organization_id` | Yes | No | Canonical Tenant Entity |
| `KnowledgeDocument` | `knowledge_documents` | `organization_id` | Yes | No | Canonical Tenant Entity |
| `PaymentOrder` | `payment_orders` | `organization_id` | Yes | Nullable (pre-auth) | Canonical Tenant Entity |
| `MarketingCampaign` | `marketing_campaigns` | `organization_id` | Yes (CASCADE) | No | Canonical Tenant Entity |

---

## 3. AUDIT OF BROKER-AS-ORGANIZATION PATTERNS

### Remediated Patterns:
1. `apps/api/app/modules/revenue_intelligence/service.py`:
   - Pre-Hardening: `Lead.broker_id == organization_id`
   - Remediated: Canonical tenant dual-read filter `or_(Lead.organization_id == org_id, and_(Lead.organization_id.is_(None), Lead.broker_id == org_id))`
2. `apps/api/app/modules/property_recommendation/candidate_retriever.py`:
   - Pre-Hardening: `broker_uuid = uuid.UUID(organization_id)` with `PropertyListing.broker_id == broker_uuid`
   - Remediated: Explicit `org_uuid = require_organization_id(organization_id)` matching `PropertyListing.organization_id == org_uuid`
3. `apps/api/app/models/broker.py`:
   - Pre-Hardening: `@property def organization_id(self) -> str: return str(self.id)`
   - Flagged for complete removal once all legacy callers migrate to `resolve_organization_id_for_broker(db, broker.id)`.

---

## 4. TENANT ISOLATION TEST MATRIX (PROVEN)

Verified via automated test suite in `apps/api/tests/test_tenant_matrix_security.py`:
- **Proof 01:** Tenant A cannot read Tenant B leads (`PASSED`)
- **Proof 02:** Tenant A cannot modify Tenant B leads (`PASSED`)
- **Proof 03:** Tenant A cannot read Tenant B conversations (`PASSED`)
- **Proof 04:** Tenant A cannot send messages via Tenant B integration (`PASSED`)
- **Proof 05:** Tenant A cannot view Tenant B properties (`PASSED`)
- **Proof 06:** Tenant A cannot invoke tools against Tenant B properties (`PASSED`)
- **Proof 07:** Tenant A cannot access Tenant B analytics (`PASSED`)
- **Proof 08:** Tenant A cannot export Tenant B data (`PASSED`)
- **Proof 09:** Tenant A cannot retrieve Tenant B search results (`PASSED`)
- **Proof 10:** Tenant A cannot trigger Tenant B workflows (`PASSED`)
- **Proof 11:** Tenant A cannot access Tenant B background jobs (`PASSED`)
- **Proof 12:** Tenant A cannot access Tenant B AI memory (`PASSED`)
- **Proof 13:** Tenant A cannot access Tenant B documents (`PASSED`)
- **Proof 14:** Tenant A cannot manipulate Tenant B appointments (`PASSED`)
- **Proof 15:** Tenant A cannot access Tenant B billing records (`PASSED`)
- **Proof 16:** Tenant A cannot obtain Tenant B data through guessed IDs (`PASSED`)
- **Proof 17:** Tenant A cannot bypass isolation through alternate routes (`PASSED`)
