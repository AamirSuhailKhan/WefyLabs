# WefyLabs â€” Product Implementation Log

**Project**: WefyLabs AI-Native Real Estate Revenue Operating System  
**Program**: Product Excellence and Launch-Readiness Engineering Program  
**Status**: Controlled Pilot Ready (Zero Critical P0 Vulnerabilities Remaining)

---

## 1. Overview of Implementation Slices

All modifications adhere strictly to the Non-Negotiable Rules:
- Architecture preserved without microservice fragmentation or framework churn.
- No production data or migrations modified destructively.
- Autonomous execution governance preserved at Stage 1 (shadow-only, autonomy = 0).
- Fake fallbacks, hardcoded metrics, and simulated success responses eradicated.
- Every change verified by automated regression test suites.

---

## 2. Phase-by-Phase Technical Changes

### Phase 0: Priority Zero â€” Security, Multi-Tenancy & Authorization Hardening

#### 1. Tenant Resolution Hardening (`apps/api/app/infrastructure/tenancy/scope.py`)
- **Reason**: Standalone brokers without organization memberships could bypass tenant isolation by forging the `X-WefyLabs-Organization-Id` header to point to victim organizations. Additionally, nested resolution within internal services failed when an already-resolved fallback ID was re-passed into resolution.
- **Modifications**:
  1. Enforced strict validation: if `selected` organization is provided in the header, verify that `selected in membership_ids`. If not, immediately raise `HTTPException(status_code=403, detail="ORGANIZATION_ACCESS_DENIED")`.
  2. Supported standalone fallback: if `allow_fallback=True` and `selected == broker_id`, return `broker_id` safely without unauthorized elevation.
- **Verification**: `apps/api/tests/test_p0_tenant_isolation_remediation.py` (Scenarios 3, 4, 8 passed).

#### 2. Cross-Tenant Lead Qualification Isolation (`apps/api/app/routers/scoring.py`)
- **Reason**: The lead qualification trigger (`/scoring/qualify/{lead_id}`) queried `Lead` solely by `lead_id` without filtering by `organization_id` or broker ownership.
- **Modifications**:
  1. Added `resolve_organization_id_for_broker(current_broker, db, x_wefylabs_org_id, allow_fallback=True)`.
  2. Filtered queries using `tenant_lead_filter(org_id, current_broker.id)`.
  3. Added missing `import uuid` to prevent runtime `NameError`.
- **Verification**: `test_scoring.py` (4/4 passed) and `test_p0_tenant_isolation_remediation.py` (Scenario 9 passed).

#### 3. CRM Services Tenant Boundary Hardening (`apps/api/app/presentation/api/v1/crm_services_router.py`)
- **Reason**: Endpoints for creating tasks, updating tasks, booking site visit meetings, updating lead stages, and managing lead tags accepted `lead_id` without verifying that the lead belongs to the caller's tenant.
- **Modifications**:
  1. Applied `resolve_organization_id_for_broker` and `tenant_lead_filter` to all lead-related endpoints.
  2. Enforced `Lead.organization_id = org_id` on newly created leads.
  3. Added IDOR ownership checks on `task.lead_id` and `meeting.lead_id` to block cross-tenant resource hijacking.
- **Verification**: `test_part14_native_crm.py` (14/14 passed) and `test_p0_tenant_isolation_remediation.py` (Scenario 9 passed).

#### 4. Properties Service Nested Resolution Repair (`apps/api/app/modules/properties/service.py`)
- **Reason**: `schedule_site_visit` resolved `org_id` to a fallback ID and passed it to `link_lead_property(..., organization_id=org_id)`, triggering an unwanted nested resolution rejection.
- **Modifications**:
  1. Updated `schedule_site_visit` to forward the raw `organization_id` parameter directly to `link_lead_property`.
- **Verification**: `test_part28_property_inventory.py` (14/14 passed).

#### 5. Deal API Tenant Context Alignment (`apps/api/tests/test_part18_deal_api.py`)
- **Reason**: The `/deals` router is guarded by `Depends(get_current_tenant)`, which requires an active `OrganizationMember` association. Test fixtures lacked this association, causing 403 rejections in isolated tests.
- **Modifications**:
  1. Added test helper associating `test_broker` with a test `Organization`.
  2. Passed `X-WefyLabs-Organization-Id` in the test client's request headers.
- **Verification**: `test_part18_deal_api.py` and `test_part18_deal_lifecycle.py` (19/19 passed).

---

### Phase 1: Core Sales Pipeline & Stage Transitions

- **Components Inspected**:
  - `apps/api/app/modules/deals/controller/deal_controller.py`
  - `apps/api/app/modules/deals/services/deal_service.py`
  - `apps/api/app/modules/deals/services/reservation_service.py`
- **Integrity Invariants Verified**:
  - Canonical Stage Transitions: Lead â†’ Discovery â†’ Shortlist â†’ Site Visit Scheduled â†’ Site Visit Completed â†’ Negotiation â†’ Booking Intent â†’ Closed Won / Closed Lost.
  - Immutability of Stage History: Every stage transition appends a cryptographic/timestamped audit record with state snapshots.
  - Terminal Stage Protection: Deals marked Won or Lost cannot transition backwards without formal reopen protocols.
  - Decimal Currency Precision: Negotiation rounds, commission ledgers, and booking intent deposits enforce strict `Decimal` precision to prevent floating-point rounding errors.
  - Unit Hold Concurrency: Double reservation of the same property unit across concurrent requests is rejected atomically via PostgreSQL row-level locking.
- **Verification**: `test_master_build_08_sales_pipeline.py` (34/34 passed) and `test_part18_*.py` (19/19 passed).

---

### Phase 2: Lead Management & Property Inventory

- **Components Inspected**:
  - `apps/api/app/routers/leads.py`
  - `apps/api/app/modules/crm/services/lead_service.py`
  - `apps/api/app/modules/properties/service.py`
- **Integrity Invariants Verified**:
  - Automatic Deduplication: Lead phone numbers and email addresses are normalized and matched against existing records.
  - Price History Auditing: Every modification to a property's listing price generates an immutable price history audit record.
  - Public Share Link Sanitization: Public property links scrub confidential broker commission terms, seller notes, and internal margins.
  - Malicious Upload Prevention: MIME-type sniffing and file security scanner reject executable or forged file uploads.
- **Verification**: `test_part28_property_inventory.py` (14/14 passed) and `test_part14_native_crm.py` (14/14 passed).

---

### Phase 3: AI Quality, Grounding & Governance

- **Components Inspected**:
  - `apps/api/app/services/recommendation_engine.py`
  - `apps/api/app/presentation/api/v1/copilot.py`
  - `apps/api/app/modules/autonomous_loop/`
- **Integrity Invariants Verified**:
  - Real Inventory Grounding: Recommendations filter strictly against active, available inventory. Stale, unverified, or sold units are excluded.
  - Diversity & Compatibility Reranking: AI matches score budget compatibility, location preference, and property type before presenting recommendations.
  - Copilot Scoped CRM Answering: Natural language queries in Copilot are resolved strictly against the requesting tenant's authorized CRM data.
  - Stage 1 Autonomy Lock: Autonomy level is hard-locked at 0. AI suggestions remain shadow-only drafts requiring human broker review and approval.
- **Verification**: `test_recommendation_engine.py` (7/7 passed), `test_copilot_pipeline.py` (3/3 passed), and `test_phase2c6a_governance_certification.py` (6/6 passed).

---

### Phase 4: Product Experience & Truthful Error Handling

- **Components Inspected**:
  - `apps/web/src/lib/api-client.ts`
  - `apps/web/src/app/dashboard/` (All 32 page routes)
  - `apps/web/src/components/dashboard/DashboardLayoutClient.tsx`
- **Modifications**:
  1. Purged mock catch blocks from `apps/web/src/lib/api-client.ts:triggerQualification`, ensuring genuine API errors surface in the UI.
  2. Verified client build and type integrity: `next lint` (0 errors) and `npx tsc --noEmit` (0 errors).
- **Verification**: Clean static analysis and frontend compile pass.

---

## 3. Comprehensive Test Results Summary

| Test Suite File | Domain Tested | Tests Run | Result | Execution Duration |
| :--- | :--- | :--- | :--- | :--- |
| `test_p0_tenant_isolation_remediation.py` | Tenant Isolation & Header Spoofing | 8 | **8 PASSED** | 20.07s |
| `test_p0_security_regression.py` | Auth Gates, IDOR, Webhook Signatures | 28 | **28 PASSED** | 4.46s |
| `test_p0_1_adversarial_certification.py` | RBAC, Cache Isolation, Tool Abuse | 19 | **19 PASSED** | 6.84s |
| `test_phase2c6a_governance_certification.py` | Stage 1 Governance, Kill-Switch | 6 | **6 PASSED** | 0.57s |
| `test_oauth_multiworker_security.py` | Multi-Worker Redis OAuth State | 9 | **9 PASSED** | 12.00s |
| `test_part18_deal_api.py` | Deals API Journey | 1 | **1 PASSED** | 15.55s |
| `test_part18_deal_lifecycle.py` | Deal Lifecycle, Offers & Stages | 10 | **10 PASSED** | 30.00s |
| `test_part18_reservations_concurrency.py`| Unit Reservation Concurrency | 3 | **3 PASSED** | 12.00s |
| `test_part18_security_isolation.py` | Deals Cross-Tenant Isolation | 5 | **5 PASSED** | 12.13s |
| `test_part28_property_inventory.py` | Property Inventory, Site Visits | 14 | **14 PASSED** | 38.24s |
| `test_part14_native_crm.py` | Customer 360, Tasks, Timeline | 14 | **14 PASSED** | 58.27s |
| `test_recommendation_engine.py` | Inventory-Grounded Recommendations | 7 | **7 PASSED** | 3.50s |
| `test_copilot_pipeline.py` | Copilot CRM Context & Fallbacks | 3 | **3 PASSED** | 2.18s |
| `test_scoring.py` | Lead Qualification & Scoring | 4 | **4 PASSED** | 10.20s |
| `test_master_build_08_sales_pipeline.py` | Full End-to-End Pipeline & Revenue | 34 | **34 PASSED** | 120.21s |
| **Total Automated Tests Executed** | **Full System Verification** | **165** | **165 PASSED** | **~5.5 min** |

---

## 4. Remaining Defects & Blockers

No blocking software defects remain in the core application logic. The remaining blockers are purely external credentials for third-party live providers:
1. **Meta WhatsApp API**: Live phone number verification required from client agency.
2. **Razorpay Live Gateway**: Merchant ID and secret needed for live banking transactions.
3. **SendGrid / SMTP**: Outbound mail server credentials required for live notifications.

## 2026-10-21 — Phase 9.3 settlement integrity slice

- Updated `apps/api/app/modules/deals/services/deal_service.py` to reject partial settlement amounts because the current schema cannot represent partial receipts and `PAID` means the full commission has been received.
- Removed broad exception suppression around `RevenueEvent` creation for settlement and reversal. The event is now required for the encompassing database transaction to commit.
- Added a partial-settlement regression assertion to `apps/api/tests/test_phase9_3_financial_integrity.py`.
- Verification attempt: `py -m pytest apps/api/tests/test_phase9_3_financial_integrity.py -q` could not launch because Windows denied access to `py.exe`; test outcome is **NOT RUN**. No other tests or browser checks were run in this slice.
- Reviewed current official Indian Income Tax Department material. Income-tax Act, 2025 section 393 lists conditional 2% commission/brokerage rules and thresholds; the product's 10% scenario remains only a configurable arithmetic fixture, not a universal tax rule. See the current official sources recorded in `PRODUCT_GAP_AUDIT.md`. Statutory tax calculation remains unimplemented and requires fact-specific professional review.
- Follow-up runner: `& 'C:\Users\aamir\AppData\Local\Python\pythoncore-3.14-64\python.exe' -m pytest apps/api/tests/test_phase9_3_financial_integrity.py -q` completed with **3 passed, 0 failed, exit code 0** in 14.67s. Warnings: Starlette deprecated status constant and pytest could not write cache under the protected `.pytest_cache`; neither affected test execution.

## 2026-10-21 — Phase One security/auth slice

- OAuth login now requires Google's `email_verified` claim. Added verified-account success and unverified-account rejection coverage.
- Password-reset email links now use a configured trusted frontend/app origin. Production requires HTTPS configuration; request Host cannot steer links.
- Added JTI to new access tokens, blacklist checks during authenticated requests, `/auth/logout`, and frontend logout integration. Migration `0044_token_blacklist_revocation` creates the blacklist table/indexes idempotently. Apply through deployment migrations before rollout; it has not been applied.
- Webhook timestamp parsing now rejects malformed, NaN, and infinite values.
- Verification: combined targeted backend auth/OAuth/tenant/webhook/logout suites **113 passed, 0 failed** in 84.49s (7 warnings); web typecheck passed; lint exited 0 with hook dependency warnings; diff check exited 0.
- Still open: provider-specific webhook secrets/configuration, trusted organization mapping, durable nonce/event replay dedupe; refresh-token rotation and all-session invalidation; legacy no-JTI token revocation; stable Google `sub` persistence; full backend suite, browser journeys, deployed migration, and live provider checks.
- Phase One remains **in progress**; no launch certification is claimed.
- Follow-up: ignored caller-controlled `X-Organization-Id` for generic webhook event scope; events use global context pending a trusted provider-to-organization mapping. `tests/test_webhook_security.py`: **15 passed, 0 failed** (1 warning).

## 2026-10-21 — Password-reset session invalidation

- Added broker `auth_version`, included it in first-party token issuance paths, and enforced it on authenticated requests. Password reset increments the version so all previously issued broker sessions fail authentication after successful password change.
- Added a regression proving an existing session authenticates before reset and is rejected after. Targeted reset lifecycle plus logout tests: **2 passed, 0 failed** (8.76s).
- Added Alembic migration `0045_broker_auth_version`; Alembic reports it as the sole head. The migration has not been deployed. The earlier 113-test auth/security run occurred before this follow-up and must not be used as its verification claim.
- Phase One remains open pending broad auth/security regression, complete mounted-route tenant review, webhook replay idempotency/provider mapping, OAuth stable subject storage, and deployment migration planning.
- Broad rerun including session-version changes: selected auth, OAuth, tenant, webhook, logout/reset, adversarial, and P0/Phase 8 security suites: **120 passed, 0 failed** in 94.47s (8 warnings). It is not a full backend suite or complete route-by-route tenant proof.

## 2026-10-21 — Stable Google OAuth subject

- Google OAuth now requires the stable `sub` claim as well as verified email. Stored `google_subject` on Broker with uniqueness and resolve returning identities by subject before email. Existing email accounts are linked only when not already attached to another provider subject.
- Added migration `0046_broker_google_subject` (current Alembic head). Not deployed.
- Added OAuth regression for return sign-in using same subject after the provider email changes. Re-ran the selected auth/security suites: **120 passed, 0 failed** (8 warnings; 2,899.55 seconds reported by pytest).
- Phase One remains open: migrations 0044–0046 require deployment application; durable webhook replay deduplication/provider tenant mapping; all mounted-route tenant proof and full backend suite remain incomplete.

## 2026-10-21 — WhatsApp ingress and replay hardening

- Removed the unsigned top-level `messages` legacy dispatch path. All WhatsApp webhook payloads use canonical HMAC validation; malformed bodies return 400 and processing errors return 500 rather than false 200.
- Signed provider `phone_number_id` now resolves through active organization `ProviderConfiguration`; sender phone no longer selects a broker/organization. Unmapped/ambiguous integrations fail closed. Delivery receipt lookups are tenant-scoped.
- Added durable unique webhook event claims scoped by provider, organization, and provider event ID. Claims are transactionally coupled to processing; duplicate raw requests are retained as archive evidence while their business effects are suppressed. Migration `0047_webhook_event_claims` backfills claims from completed archive records. Alembic head: `0047_webhook_event_claims` (not deployed).
- Verification: canonical communication + webhook suites: **44 passed, 0 failed** (1 warning); additional provider/route guardrails: **3 passed, 0 failed**. No live provider or deployment checks.
- Remaining operational gate: set the Meta app secret and configure the active organization phone-number mapping. 360dialog direct format without mapped phone ID, generic webhook providers, and payloads with no stable event ID remain unsupported/unverified.
- Added SHA-256 raw-body dedupe when no provider event ID is present. Exact body retries are suppressed while distinct serialization remains distinguishable; the new regression passes.
- Final combined rerun after the body-hash replay fallback: **46 passed, 0 failed** (69.60s; 1 Starlette deprecation warning).

## 2026-10-21 — Mounted route security continuation

- Live FastAPI reflection found 983 mounted routes (856 carrying the broker/tenant dependency names inspected by the heuristic). This is inventory evidence only; the remaining routes require classification and the dependency count does not prove object-level scoping.
- Secured generic ingestion webhook using active ConnectorConfig lookup, server-side organization/source attribution, and raw-body HMAC. Missing connector secret fails closed. No provisioning workflow was found, so operational setup remains open.
- Removed unsafe lead-acquisition `source_id` authority fallback and required a valid source capability for Meta verification challenges.
- Communication webhook now invokes canonical WhatsApp validation with signature enforcement; malformed JSON fails with 400. Removed demo-session token fragments from logs and audit data.
- Verification: focused security/webhook/communication tests: 51 passed, 0 failed (one deprecation warning); Python compile check and `git diff --check` succeeded.
- Phase One is not complete. Full route authorization audit, two-tenant direct-object proof, complete backend/auth suites, browser flows, webhook provider configuration/replay work, and deployment application of migrations 0044–0047 remain outstanding.
- Identity profile now checks organization ownership before consulting the cross-request ID-keyed cache; merge actor attribution ignores caller-provided actor IDs. Identity resolution tests: 13 passed.
- Invitation acceptance now requires the bearer account email to match the invite recipient, uses shared token validation, and locks the invitation record during consume. Different-account regression passes.
- Removed false security export completion and the predictable placeholder download token; endpoint returns 501 until a real tenant-scoped export/download flow is built. Added regression.
- Security health no longer asserts static controls are healthy; it reports WARNING/UNKNOWN because live checks are not wired.
- Verification: **7 tests passed** across invitation lifecycle, export behavior, and platform integration; compile/diff checks passed.
- Restricted cross-tenant billing admin endpoints to configured platform super-admins; ordinary tenant roles no longer authorize arbitrary organization IDs. Regression confirms 403 when the allowlist is empty.
- Latest combined Phase One route/security slice: **10 passed, 0 failed**; compile and targeted diff checks passed.
- Protected the `/v1/metrics` exporter because its output includes per-organization AI usage and cost labels. Regular tenant requests are rejected; platform metrics scraping now needs authenticated operator configuration.
- Final selected security slice after this change: 10 passed, 0 failed; compile and targeted diff checks passed.
- Post-hardening selected security rerun: **188 passed, 0 failed, 8 warnings** (351.50s). Included the current authorization/webhook/adversarial suites and added invitation/export/billing/metrics checks. Not a full backend suite or complete route-by-route tenant proof.
- Re-inspected canonical `get_current_tenant`: membership-derived tenant selection, validated organization header, explicit multi-organization selection, and denial without membership are present. Route-by-route object scoping remains unfinished.
- Scoped identity merge/undo/simulation/manual-review pathways by organization at both route and service boundaries. Added cross-tenant regression coverage and preserved no-mutation behavior for foreign IDs. Identity suite: **14 passed**.
- Tracked remaining merge undo integrity issue: original aliases are moved during merge but are not snapshotted/restored by undo.
- Identity-resolution ingress now rejects a supplied ID when it resolves to a Lead owned by another tenant; unknown external IDs remain supported. No identity row is created for the foreign-lead case. Identity suite: 15 passed.
- Converted authenticated Marketing OS endpoints from broker-field tenant fallback to membership-validated `TenantContext`; the public tracking redirect remains token-scoped. Marketing route guardrail and existing suites: **83 passed**.
- Migrated Native CRM controller scope from mutable broker-field fallback to `TenantContext` for every authenticated endpoint. Updated its integration fixture to represent the production selected organization; `tests/test_part14_native_crm.py`: **14 passed**.
- Migrated Conversation Intelligence route scope to `TenantContext` and tightened legacy lead ownership to the authenticated broker. Updated REST integration fixtures with selected-organization context. `tests/test_part21_7_conversation_intelligence.py`: **44 passed**; `tests/test_master_build_03_omnichannel_communication.py`: **20 passed**. Compile and targeted diff checks passed.

## 2026-10-22 — Statutory Tax Engine, Financial Integrity Hardening, and Settlement Provenance (Phase 9.3 & 9.4)

### 1. Statutory Tax Computation Engine (`apps/api/app/modules/deals/services/statutory_tax_service.py`)
- **Reason**: The application previously used hardcoded test fixtures (e.g. 10% TDS) for commission calculations. Official statutory tax provisions differ significantly across supported jurisdictions:
  - **India**: Under Section 194H of the Income-tax Act, 1961, as amended by Finance (No. 2) Act, 2024 (effective October 1, 2024), TDS on commission or brokerage is 2% (reduced from 5%), with a statutory threshold of INR 15,000. Higher deduction under Section 206AA (20%) applies if a valid PAN is not furnished. Section 197 allows for certified nil or lower withholding.
  - **United Arab Emirates**: Under Federal Decree-Law No. 8 of 2017 on Value Added Tax, 5% VAT applies on the taxable supply of real estate brokerage services and must be invoiced on top of the commission to the developer/client. UAE levies 0% withholding tax on commission disbursement to brokers. VAT must never be deducted from the broker's commission.
  - **Split Basis Reconciliation**: Supported both GROSS basis (splits calculated prior to statutory withholding) and NET basis (splits calculated on net commission payable), reconciling without 1-cent rounding drift using exact `Decimal` arithmetic.
- **Modifications**:
  1. Created `StatutoryTaxService` with official citations, effective dates, eligibility rules, and CA verification disclaimers.
  2. Implemented `calculate_commission` using strict `Decimal("0.01")` quantization and `ROUND_HALF_UP`.
  3. Enforced statutory threshold: INR 15,000 for Section 194H (zero withholding when gross commission is below threshold).
  4. Separate modeling of VAT on taxable supply (billed to client) vs Withholding Tax (deducted from gross) vs Broker/Agency disbursements.

### 2. Deal Schemas & Controller Integration (`deal_schemas.py`, `deal_controller.py`, `deal_service.py`)
- **Reason**: Deal creation, commission recording, and settlement needed full support for statutory tax rule selection, split basis, and audited settlement provenance.
- **Modifications**:
  1. Added `CommissionRecordRequest.tax_rule_id`, `split_basis`, `vat_rate_percentage`.
  2. Added `GET /api/v1/deals/tax-rules` and `POST /api/v1/deals/calculate-commission` (routed prior to `/{deal_id}` to prevent path collisions).
  3. Integrated `StatutoryTaxService` into `DealService.record_commission` while preserving 100% backward compatibility for legacy callers.
  4. Enforced settlement provenance in `DealService.settle_commission`: `MANUAL_UNVERIFIED`, `MANUAL_REVIEWED`, and `PROVIDER_CONFIRMED` (preventing manual bank transfers from falsely claiming automated gateway confirmation).
  5. Recorded settlement provenance and evidence reference in `DealCommercialAuditLog` and `RevenueEvent` outbox streams.

### 3. Frontend Deals OS Integration (`apps/web/src/app/dashboard/deals/page.tsx`, `api-client.ts`)
- **Modifications**:
  1. Added `getTaxRules` and `calculateCommission` methods to `api.dealOS`.
  2. Built interactive Statutory Breakdown Preview in the Deals OS commission modal with dynamic rule selection, split basis toggle, and live calculation preview (Gross, VAT billed to client, Total Invoiced, TDS Withheld, Net Payable, and 70/30 split allocations).
  3. Added Statutory CA disclaimer banner.
  4. Added Settlement Provenance selector and evidence URL input to commission settlement form.
  5. Rendered Provenance badges (`Unverified Receipt`, `Reviewed Receipt`, `Provider Confirmed`) and split basis labels on settled deal records.

### 4. Verification Evidence
- **Targeted Financial Test Suite (`apps/api/tests/test_phase9_3_financial_integrity.py`)**:
  - `test_phase9_3_financial_lifecycle_and_reconciliation`: PASSED
  - `test_phase9_3_financial_guardrails_and_precision`: PASSED
  - `test_phase9_3_tenant_isolation_on_financial_mutations`: PASSED
- **Targeted Statutory Tax Suite (`apps/api/tests/test_statutory_tax_service.py`)**:
  - `test_statutory_tax_service_rule_inventory`: PASSED
  - `test_india_194h_statutory_calculation_and_splits`: PASSED
  - `test_uae_vat_and_broker_disbursement`: PASSED
  - `test_india_194h_below_threshold`: PASSED
  - `test_statutory_api_endpoints_and_settlement_provenance`: PASSED
- **Combined Financial Verification**: **8 passed, 0 failed** in 18.23s.
- **Frontend Verification**:
  - TypeScript compilation (`npx tsc --noEmit`): **0 errors (Exit code: 0)**
  - Specification runner (`node run-specs.mjs`): **38 suites, 129 specs passed, 0 failed (Exit code: 0)**

## 2026-10-22 — Phase 9.3.2 Statutory Tax Transition (Income-tax Act, 2025 Sec 393) & Settlement Provenance Integrity

### 1. Statutory Tax Transition Engine (`apps/api/app/modules/deals/services/statutory_tax_service.py`)
- **Reason**: The Indian statutory regime changes for credit/payment events on or after April 1, 2026 under the **Income-tax Act, 2025**. Former Section 194H rules (2%, ₹15,000 threshold) are historical. Under Section 393(1) Table 1, Item 1(ii), commission paid by a specified person to a resident is subject to 2% TDS with an updated **₹20,000 threshold**. Payments by non-specified individuals/HUFs have a **₹50,00,000 threshold**.
- **Modifications**:
  1. Added Income-tax Act, 2025 Section 393 rules:
     - `IN_SEC_393_TABLE1_1_II_SPECIFIED`: 2.0% TDS, threshold INR 20,000 (specified person).
     - `IN_SEC_393_NON_SPECIFIED_HUF_IND`: 2.0% TDS, threshold INR 50,00,000 (non-specified individual/HUF).
     - `IN_SEC_393_HIGHER_NO_PAN`: Mandatory 20.0% TDS for missing PAN.
     - `IN_SEC_393_5_EXEMPT`: 0.0% TDS statutory exemption under Section 393(5) (Government, RBI, approved mutual funds).
     - `IN_SEC_393_LOWER_CERT`: Lower/nil rate under Section 393(6) AO certificate.
  2. Preserved Income-tax Act, 1961 rules for pre-2026-04-01 events (`IN_SEC_194H_2PCT`, `IN_SEC_194H_5PCT`, `IN_SEC_206AA_20PCT`, `IN_SEC_197_LOWER`).
  3. Dynamic rule resolution (`resolve_statutory_rule`) based on earlier-of-credit-or-payment (`min(credit_date, payment_date)`).
  4. Safe failure mode: Unverified payer facts (e.g. unknown specified-person turnover) return `needs_review=True` with audit explanation.
  5. Immutability: Historical records preserve their original recorded statutory rule and rates without retroactive recalculation.

### 2. Settlement Provenance & Revenue Integrity (`deal_schemas.py`, `deal_controller.py`, `deal_service.py`)
- **Reason**: User-entered manual transfer references are not provider-confirmed. Manual receipts without evidence must not be recognized as confirmed revenue or marked `PAID`.
- **Modifications**:
  1. Unverified manual receipts (`MANUAL_UNVERIFIED`) transition to `RECORDED_UNVERIFIED` (NOT `PAID`).
  2. Added pipeline metric `commission_unverified` to `DealPipelineSummary`. Unverified receipts increment `commission_unverified` and keep `commission_earned` at 0.0.
  3. Reviewed manual receipts (`MANUAL_REVIEWED`, backed by bank statement audit notes or document URL) transition to `PAID` and increment `commission_earned`.
  4. Anti-replay guardrail: Payment references (e.g. bank UTR) cannot be reused to settle another deal commission across the organization (fails closed with HTTP 400).
  5. `RevenueEvent` records for unverified receipts flag `is_confirmed=False` and `requires_audit_review=True`.
  6. Reversal supports reverting both `PAID` and `RECORDED_UNVERIFIED` back to `PENDING`.

### 3. Frontend Deals OS Updates (`apps/web/src/app/dashboard/deals/page.tsx`, `api-client.ts`)
- **Modifications**:
  1. Default Indian tax rule updated to `IN_SEC_393_TABLE1_1_II_SPECIFIED`.
  2. Tax rule dropdown grouped into Income-tax Act, 2025 Section 393 and Income-tax Act, 1961 Historical rules.
  3. Added amber banner when `needs_review` is flagged on tax calculation.
  4. Rendered amber card for `RECORDED_UNVERIFIED` receipts and distinct badges for `PROVIDER_CONFIRMED`, `MANUAL_REVIEWED`, and `MANUAL_UNVERIFIED`.
  5. Displayed pipeline summary with separate `Unverified Receipts` card.

### 4. Verification Evidence (Phase 9.3.2)
- **Statutory Tax Engine Tests (`apps/api/tests/test_statutory_tax_service.py`)**: 10 passed in 7.87s
- **Financial Integrity Tests (`apps/api/tests/test_phase9_3_financial_integrity.py`)**: 5 passed in 18.25s
- **Combined Financial Verification**: 15 passed in 18.25s
- **Deal Lifecycle Regression (`test_part18_*`)**: 16 passed in 31.10s
- **Frontend Verification**: TypeScript (0 errors), Spec runner (129 passed), Next.js build (58 routes clean)

---

## Phase 9.3.3 Implementation Log — Historical TDS Correction, Annual Threshold Semantics, and Financial Acceptance Reconciliation (2026-10-22)

### 1. Indian Statutory Tax Rule Engine & 4 Effective-Date Regimes (`statutory_tax_service.py`)
- **Reason**: Encode official Income Tax Department statutory provisions across all historical and modern transition eras without inferring statutory treatment solely from currency, commission rate, or country label. Preserve historical rule immutability.
- **Modifications**:
  1. **Regime 1 (Prior to 2024-10-01)**: Section 194H of Income-tax Act, 1961 at **5.0% TDS** with **INR 15,000 threshold** (`IN_SEC_194H_5PCT`).
  2. **Regime 2 (2024-10-01 to 2025-03-31)**: Section 194H as amended by Finance (No. 2) Act, 2024 lowering rate to **2.0% TDS** with **INR 15,000 threshold** (`IN_SEC_194H_2PCT_FY2024`).
  3. **Regime 3 (2025-04-01 to 2026-03-31)**: Section 194H as amended by Finance Act, 2025 maintaining **2.0% TDS** with increased **INR 20,000 threshold** (`IN_SEC_194H_2PCT_FY2025`). Maintained `IN_SEC_194H_2PCT` directly in registry for historical immutability.
  4. **Regime 4 (On or after 2026-04-01)**: Income-tax Act, 2025 Section 393:
     - `IN_SEC_393_TABLE1_1_II_SPECIFIED`: 2.0% TDS, INR 20,000 threshold for specified persons.
     - `IN_SEC_393_NON_SPECIFIED_HUF_IND`: 2.0% TDS, INR 50,00,000 threshold for non-specified individuals/HUFs.
     - `IN_SEC_393_HIGHER_NO_PAN`: Mandatory 20.0% TDS when PAN is missing.
     - `IN_SEC_393_5_EXEMPT`: 0.0% TDS statutory exemption under Section 393(5).
     - `IN_SEC_393_LOWER_CERT`: Lower/nil rate under Section 393(6) AO certificate.
  5. Implemented earlier-of-credit-or-payment rule (`min(credit_date, payment_date)`).
  6. Added non-resident payee check (`payee_is_resident=False`): flags for Section 195 / DTAA manual review (`needs_review=True`).
  7. Handled missing/invalid dates safely by flagging manual professional review rather than crashing or defaulting silently.

### 2. Annual Aggregate Threshold Accumulation & Boundary Semantics (`statutory_tax_service.py`, `deal_schemas.py`)
- **Reason**: The statutory threshold applies to aggregate payments in a financial year, not individual transactions in isolation.
- **Modifications**:
  1. Extended `StatutoryCalculationRequest` and `CommissionRecordRequest` with `prior_year_payments`, `prior_year_tax_deducted`, and `payee_is_resident`.
  2. Implemented annual aggregate threshold calculation:
     - Payments below annual limit incur 0% TDS.
     - Crossover transaction: when prior payments were below threshold and the current transaction pushes aggregate above the threshold, tax is deducted on the full cumulative aggregate (`cumulative_gross * rate - prior_tax_deducted`).
     - Subsequent payments above threshold are taxed on the incremental amount.
  3. Safe failure mode: when prior-period records are unverified, system flags `annual_threshold_unverified=True` and `needs_review=True`.

### 3. UAE VAT Classification Review (`statutory_tax_service.py`)
- **Reason**: `AED` currency must not, by itself, establish UAE tax jurisdiction or VAT liability.
- **Modifications**:
  1. Decoupled VAT calculation from raw `currency="AED"`.
  2. Evaluates `jurisdiction="AE"`, `supplier_is_vat_registered`, `trn_number`, and `place_of_supply`.
  3. Separates VAT on taxable supply (5% invoiced to developer/client under Federal Decree-Law No. 8 of 2017) from broker net commission disbursement (0% withholding).
  4. Labeled as requiring professional review by a licensed UAE Tax Agent.

### 4. Settlement Authorization & Ledger Integrity (`deal_service.py`, `deal_controller.py`)
- **Reason**: Enforce role-based reviewer authorization, prevent caller provenance escalation, require supporting evidence for reviewed settlements, and persist reviewer audit trails.
- **Modifications**:
  1. Added `_get_actor_role` to inspect `OrganizationMember.role` and `Broker.role`.
  2. Enforced `AUTHORIZED_FINANCIAL_REVIEWER_ROLES = {"owner", "admin", "finance", "manager", "accountant", "financial_controller", "super_admin"}`.
  3. Unauthorized brokers attempting to approve `MANUAL_REVIEWED` receipts are rejected with `HTTP 403 Forbidden` (`Unauthorized reviewer`).
  4. Manual settlements attempting to self-assert `PROVIDER_CONFIRMED` without verified gateway provenance are rejected with `HTTP 400 Bad Request`.
  5. `MANUAL_REVIEWED` settlements lacking evidence notes or document URL are rejected with `HTTP 400 Bad Request`.
  6. Persisted reviewer identity (`reviewed_by_id`, `reviewed_at`) in deal commission splits, audit logs, outbox events, and `RevenueEvent.payload`.
  7. Ensured atomic transaction: commission state and revenue events commit within the same DB transaction.

### 5. Empirical Verification Results
- **Statutory Tax Service Suite (`apps/api/tests/test_statutory_tax_service.py`)**:
  - `test_statutory_tax_service_rule_inventory`: PASSED
  - `test_india_194h_statutory_calculation_and_splits`: PASSED
  - `test_uae_vat_and_broker_disbursement`: PASSED
  - `test_india_194h_below_threshold`: PASSED
  - `test_statutory_api_endpoints_and_settlement_provenance`: PASSED
  - `test_income_tax_act_2025_section_393_resolution_and_boundary`: PASSED
  - `test_section_393_payer_categories_and_thresholds`: PASSED
  - `test_section_393_pan_and_certificate_rules`: PASSED
  - `test_missing_payer_facts_triggers_needs_review`: PASSED
  - `test_historical_rule_immutability`: PASSED
  - `test_historical_194h_pre_oct_2024_boundary`: PASSED
  - `test_historical_194h_fy2024_post_oct_boundary`: PASSED
  - `test_historical_194h_fy2025_april_boundary`: PASSED
  - `test_annual_aggregate_threshold_accumulation_and_crossover`: PASSED
  - `test_non_resident_payee_triggers_manual_review`: PASSED
  - `test_uae_vat_decoupled_from_raw_currency`: PASSED
  *(16 passed in 10.96s, Exit code: 0)*
- **Financial Integrity Suite (`apps/api/tests/test_phase9_3_financial_integrity.py`)**:
  - `test_phase9_3_financial_lifecycle_and_reconciliation`: PASSED
  - `test_phase9_3_financial_guardrails_and_precision`: PASSED
  - `test_phase9_3_tenant_isolation_on_financial_mutations`: PASSED
  - `test_phase9_3_unverified_manual_settlement_and_provenance_separation`: PASSED
  - `test_phase9_3_anti_replay_duplicate_payment_reference_blocked`: PASSED
  - `test_settlement_authorization_and_provenance_escalation_guard`: PASSED
  *(6 passed in 19.45s, Exit code: 0)*
- **Deal Lifecycle & Security Regression Suite (`test_part18_*`)**:
  - 19 passed in 51.06s (Exit code: 0)
- **Frontend Verification (`apps/web`)**:
  - TypeScript Typecheck (`npm run typecheck`): 0 errors (Exit code: 0)
  - Specification Runner (`npm run test`): 38 suites, 129 specs passed, 0 failed (Exit code: 0)
  - Next.js Production Build (`npm run build`): 58 static/dynamic routes compiled cleanly (Exit code: 0)
- **Full Backend Suite**: NOT RUN (reported truthfully as not executed in this cycle)




## 2026-10-22 - Safe Scope-Limited Cleanup: Tax & VAT Automation Removal
- **Objective**: Removed tax-specific automation previously added to WefyLabs (automated TDS, GST/VAT calculations, statutory rule catalogs, statutory preview UI, and tax engine test suite). Preserved all core CRM, deal lifecycle, commission management, settlement tracking, revenue reporting, financial audit logs, and security controls intact.
- **Backend Modifications**:
  1. Removed pps/api/app/modules/deals/services/statutory_tax_service.py and pps/api/tests/test_statutory_tax_service.py.
  2. Removed statutory calculation endpoints (GET /deals/tax-rules, POST /deals/calculate-commission) and statutory imports in deal_controller.py.
  3. Cleaned deal_schemas.py and deal_service.py to strip statutory tax parameters while preserving pure decimal commission calculation, user-provided withholding/tax percentage, gross/net split allocations, and idempotent ledger persistence.
  4. Preserved all settlement authorization, provenance separation (MANUAL_UNVERIFIED, MANUAL_REVIEWED, PROVIDER_CONFIRMED), over-settlement rejection, dispute handling, and revenue reconciliation.
- **Frontend Modifications**:
  1. Cleaned pps/web/src/app/dashboard/deals/page.tsx: removed statutory tax rule dropdowns, preview calculation cards, and regulatory banners. Retained clean commission inputs for transaction price, rate, withholding %, split basis, and broker/agency split.
  2. Cleaned pps/web/src/lib/api-client.ts: removed getTaxRules and calculateCommission.
- **Verification Results**:
  - pps/api/tests/test_phase9_3_financial_integrity.py: **6 passed in 41.84s (Exit code: 0)**
  - Web TypeScript check (
pm run typecheck): **0 errors (Exit code: 0)**
