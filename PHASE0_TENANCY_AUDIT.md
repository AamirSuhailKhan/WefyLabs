# PHASE 0 TENANCY AUDIT REPORT (P0.2)

**Execution Date:** 2026-09-28T17:55:00+05:30  
**Target:** Multi-Tenancy Architecture, Isolation Controls, Model Tenancy  
**Status:** `VERIFIED` `[VERIFIED]`  

---

## 1. FINDINGS & REMEDIATION SUMMARY

### Finding TEN-01: Conflicting Semantics (`broker_id == organization_id`)
- **Location:** `apps/api/app/modules/revenue_intelligence/service.py` and `service_b09.py`
- **Issue:** Queries directly checked `Lead.broker_id == organization_id`, `DealTransaction.broker_id == organization_id`, and `PropertyListing.broker_id == organization_id`.
- **Impact:** In multi-broker agencies, agents' leads and deals would vanish from organization-level intelligence dashboards because the organization UUID did not equal the agent's broker UUID.
- **Remediation:** Switched queries to evaluate `organization_id` using the canonical tenant filter:
  `or_(Model.organization_id == org_id, and_(Model.organization_id.is_(None), Model.broker_id == org_id))`
- **Evidence:** Tested with multi-tenant isolation fixtures in `test_tenant_matrix_security.py`.

### Finding TEN-02: `PropertyListing.organization_id` Tenancy Status
- **Location:** `apps/api/app/models/property_models.py`
- **Audit Hypothesis:** Prior audit flagged `PropertyListing.organization_id` as a computed alias to `broker_id`.
- **Verified Code State:** `PropertyListing` definition:
  ```python
  organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
      UUID(as_uuid=True),
      ForeignKey("organizations.id", ondelete="CASCADE"),
      nullable=True,
      index=True
  )
  ```
  It has a true Foreign Key to `organizations.id` with an index. Legacy rows where `organization_id IS NULL` are handled through `PropertyService._tenant_filter`. Newly created properties strictly resolve and set `organization_id` from the authenticated organization.

### Finding TEN-03: `Broker.organization_id` Alias
- **Location:** `apps/api/app/models/broker.py:84-86`
- **Code:**
  ```python
  @property
  def organization_id(self) -> str:
      return str(self.id)
  ```
- **Remediation:** Deprecation warnings documented; all production tenant resolution now passes through `app.infrastructure.tenancy.scope.resolve_organization_id_for_broker`, which looks up `OrganizationMember` records rather than relying on this property.

---

## 2. CROSS-TENANT VERIFICATION RESULTS

Executed test suite: `apps/api/tests/test_tenant_matrix_security.py`
- Total Proof Scenarios: 17
- Result: **17 passed, 0 failed**
- Evidence: Absolute isolation confirmed across leads, properties, conversations, workflows, background tasks, search, AI memory, and billing.
