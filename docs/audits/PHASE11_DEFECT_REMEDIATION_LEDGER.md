# WEFYLABS PHASE 11 — DEFECT REMEDIATION LEDGER
**Unified Defect Register, Root Cause Analysis, and Verification Evidence**  
**Execution Environment:** Isolated Test Container (`leadscore_test_acceptance`)  
**Auditor:** Principal Software Architect & QA Lead  
**Audit Date:** 2026-10-28  
**Repository Branch:** `level-3` (HEAD: `0383020a865fe315adfda4549f536a594fb10454`)  

---

## 1. Defect Register Summary

| Finding ID | Severity | Workflow / Module | Root Cause | Status |
| :---: | :---: | :--- | :--- | :---: |
| **DEF-10-01** | **CRITICAL** | Revenue Intelligence Team Analytics | Unscoped deal and meeting aggregations leaked competitor broker totals | **REMEDIATED & VERIFIED** |
| **DEF-10-02** | **MEDIUM** | Broker & Org Member ORM Models | Composite PK declaration ambiguity in `OrganizationMember` | **RESOLVED & VERIFIED** |
| **DEF-11-01** | **MEDIUM** | Lead Qualification & AI Scoring | Strict `Literal` constraint on `property_type` in `ExtractedData` | **DOCUMENTED & BOUNDED** |
| **DEF-11-02** | **LOW** | Calendar Slot Search API | Mandatory `lead_id` requirement prevents generic broker slot discovery | **DOCUMENTED & BOUNDED** |
| **DEF-11-03** | **HIGH** | Alembic Migration 0049 Downgrade | `lead_id IS NULL` records block transactional downgrade to 0048 | **MITIGATED IN RUNBOOK** |

---

## 2. Detailed Finding Records

### Finding: DEF-10-01 (CRITICAL — Multi-Tenant Isolation Leak)
- **Affected Workflow:** Revenue Intelligence Team Performance Analytics
- **File / Symbol:** `apps/api/app/modules/revenue_intelligence/service.py` -> `_deal_scope_filter()`, `TeamIntelligenceAnalyzer`
- **Reproduction Steps:**
  1. Provision Organization A (Broker A1, Lead A) and Organization B (Broker B1, Lead B).
  2. Create Deal B_Cross ($500,000) assigned to Broker A1, but tied to Lead B (Organization B).
  3. Query `TeamIntelligenceAnalyzer` for Organization A.
- **Expected Result:** Organization A sees only Deal A ($100,000); Deal B_Cross is completely excluded.
- **Actual Result (Pre-Fix):** Organization A counted Deal B_Cross, leaking $500,000 of competitor deal value into Organization A's pipeline metrics.
- **Root Cause:** `_deal_scope_filter` checked `DealTransaction.broker_id.in_(org_brokers)` without enforcing that the deal's underlying `Lead` was owned by the requesting tenant. Additionally, `SchedulingMeeting` queries were executed without tenant scoping.
- **Customer & Security Impact:** Severe IDOR and data leakage between competing brokerages.
- **Corrective Action Applied:**
  Updated `_deal_scope_filter` to assert `DealTransaction.lead_id.in_(org_leads)` and applied `_meeting_scope_filter` to meetings query.
- **Regression Test:** `apps/api/tests/test_part11_revenue_intelligence.py` -> `test_team_intelligence_scoping_never_leaks_cross_tenant_broker_deals_or_meetings`
- **Verification Evidence:** Automated test passed in 1.42s; Org A closed value asserted at exactly $100,000; Deal B_Cross excluded.

---

### Finding: DEF-10-02 (MEDIUM — ORM Composite Key Warning)
- **Affected Workflow:** Relational Mapping for Broker Memberships
- **File / Symbol:** `apps/api/app/models/broker.py` -> `OrganizationMember`
- **Reproduction Steps:** Reflecting tables or issuing bulk insert queries on `OrganizationMember`.
- **Expected Result:** SQLAlchemy resolves composite primary key without reflection warnings.
- **Actual Result:** SQLAlchemy emitted warnings regarding composite key configuration.
- **Root Cause:** Lack of explicit `PrimaryKeyConstraint('organization_id', 'broker_id')` metadata construct.
- **Corrective Action Applied:** Explicit composite primary key declared on `(organization_id, broker_id)`.
- **Regression Test:** `test_part22_production_integration.py`
- **Verification Evidence:** Tested successfully across pilot fixture setup and teardown.

---

### Finding: DEF-11-01 (MEDIUM — Property Type Literal Constraint)
- **Affected Workflow:** Lead Qualification & Scoring (`POST /api/v1/scoring/qualify`)
- **File / Symbol:** `apps/api/app/services/lead_scorer.py` -> `ExtractedData.property_type`
- **Reproduction Steps:**
  Submit payload with `"property_type": "apartment_3bhk"` or `"commercial"`.
- **Expected Result:** Payload accepted or normalized to residential category.
- **Actual Result:** HTTP 422 Unprocessable Entity:
  `Input should be '1bhk', '2bhk', '3bhk', 'villa' or 'plot'`
- **Root Cause:** `ExtractedData` model uses rigid Pydantic `Literal['1bhk', '2bhk', '3bhk', 'villa', 'plot']`.
- **Customer Impact:** API clients or webhooks sending descriptive property tags fail validation.
- **Corrective Action:** Input normalizer or expanded enum in subsequent sprint; pilot test payloads normalized to valid literals.
- **Verification Evidence:** Scenario 2.1 passed with HTTP 200 using literal `'3bhk'`.

---

### Finding: DEF-11-02 (LOW — Calendar Slot Search Lead Dependency)
- **Affected Workflow:** Calendar Slot Availability Search (`POST /api/v1/calendar/slots/search`)
- **File / Symbol:** `apps/api/app/modules/calendar/` -> `SlotSearchRequest`
- **Reproduction Steps:**
  Submit slot search body containing `broker_id`, `start_date`, and `end_date`, but omitting `lead_id`.
- **Expected Result:** Returns general broker slot availability.
- **Actual Result:** HTTP 422 Unprocessable Entity: `missing field: body.lead_id`.
- **Root Cause:** The calendar engine couples slot search with lead preferences to determine conflict windows.
- **Customer Impact:** Brokers cannot view general free/busy calendar without first picking an active lead.
- **Corrective Action:** API schema requirement documented; test payload updated with valid `lead_id`.

---

### Finding: DEF-11-03 (HIGH — Migration 0049 Asymmetric Downgrade)
- **Affected Workflow:** Alembic Schema Migration Rollback (`downgrade 0048`)
- **File / Symbol:** `apps/api/alembic/versions/0049_source_attribution_uuid_parity.py`
- **Reproduction Steps:**
  1. Upgrade database to revision 0049.
  2. Insert an attribution row where `lead_id IS NULL` (valid in 0049).
  3. Execute `alembic downgrade 0048`.
- **Expected Result:** Clean rollback to schema revision 0048.
- **Actual Result:** PostgreSQL raises `IntegrityError` because revision 0048 enforces `ALTER TABLE source_attributions ALTER COLUMN lead_id SET NOT NULL`.
- **Root Cause:** Schema 0048 does not tolerate nullable `lead_id`.
- **Operational Risk:** If marketing events are logged without immediate lead associations, emergency downgrade to 0048 will fail.
- **Corrective Action / Mitigation:** Runbook `PHASE10_MIGRATION_0049_RUNBOOK.md` updated with pre-downgrade cleanup query:
  ```sql
  DELETE FROM source_attributions WHERE lead_id IS NULL;
  ```
- **Verification Evidence:** Rehearsed successfully during Phase 10 migration verification.

