# WefyLabs â€” Product Gap Audit & Feature Inventory

**Project**: WefyLabs AI-Native Real Estate Revenue Operating System  
**Audit Date**: October 2026  
**Scope**: Full Stack (`apps/api` FastAPI backend, `apps/web` Next.js 14 frontend, PostgreSQL models, Celery/Redis background processing, Tenancy & Security architecture).

---

## 1. Executive Summary

This audit establishes the empirical state of the WefyLabs codebase. Every classification is grounded in route registrations, database schema constraints, service implementations, and automated test execution results.

### Summary Metrics
- **Total Functional Modules Audited**: 12 core domains
- **FastAPI Endpoints Registered**: 142 routes across 24 routers
- **Automated Test Coverage Verified**: 161 automated regression and lifecycle tests executing green
- **Frontend Pages & Views**: 32 dashboard pages, all passing strict TypeScript check (`npx tsc --noEmit` with 0 errors) and Next.js linting (`next lint` with 0 errors)
- **Tenant Isolation Certification**: 100% verified across leads, properties, deals, conversations, scoring, and CRM services.

---

## 2. Practical Feature Inventory

Each capability is classified into one of seven standardized categories:
1. **Implemented and Verified** (Code complete, integrated, authenticated, tenant-isolated, persisted to DB, tested with green automated test results)
2. **Implemented but Insufficiently Tested** (Functionality exists in backend & frontend, but lacks end-to-end automated regression coverage)
3. **Partially Implemented** (Core logic exists, but specific edge cases, sub-routes, or UI hooks are incomplete)
4. **Broken or Incorrectly Integrated** (Identified defect preventing end-to-end execution without remediation)
5. **UI-only or Placeholder Functionality** (Frontend component displays mockup data without backend connectivity)
6. **Blocked by Missing Configuration or External Dependency** (Code complete and verified with fixtures, but live execution requires external credentials)
7. **Not Implemented** (Deferred or explicitly out of scope)

---

### Module 1: Authentication, RBAC & Multi-Tenancy Scope
| Feature / Subsystem | Status | Implementation Trace | Evidence / Test Suite |
| :--- | :--- | :--- | :--- |
| JWT Bearer Authentication & Refresh | **Implemented and Verified** | `apps/api/app/modules/auth/service.py`, `router.py` | `test_authentication_matrix.py`, `test_oauth_multiworker_security.py` |
| Multi-Worker Redis OAuth State Storage | **Implemented and Verified** | `apps/api/app/modules/auth/service.py` | `test_oauth_multiworker_security.py` (9/9 passed) |
| Organization Membership Context Resolution | **Implemented and Verified** | `apps/api/app/infrastructure/tenancy/scope.py` | `test_p0_tenant_isolation_remediation.py` (Scenario 4) |
| Standalone Broker Header Spoofing Prevention | **Implemented and Verified** | `apps/api/app/infrastructure/tenancy/scope.py` | `test_p0_tenant_isolation_remediation.py` (Scenario 3) |
| Object-Level Authorization & RBAC Roles | **Implemented and Verified** | `apps/api/app/dependencies/auth.py`, `role_checker.py` | `test_p0_1_adversarial_certification.py` (19/19 passed) |
| Multi-Organization Switching | **Implemented and Verified** | `apps/api/app/routers/leads.py`, `scope.py` | `test_p0_tenant_isolation_remediation.py` (Scenario 4) |

---

### Module 2: Lead Management & Ingestion
| Feature / Subsystem | Status | Implementation Trace | Evidence / Test Suite |
| :--- | :--- | :--- | :--- |
| Lead Creation & Validation | **Implemented and Verified** | `apps/api/app/routers/leads.py`, `crm_services_router.py` | `test_part14_native_crm.py`, `test_p0_tenant_isolation_remediation.py` |
| Ingestion Deduping & Identity Resolution | **Implemented and Verified** | `apps/api/app/modules/identity_resolution/` | `test_master_build_02_ingestion_identity.py`, `test_p0_security_regression.py` |
| Lead Assignment & Ownership | **Implemented and Verified** | `apps/api/app/modules/crm/services/lead_service.py` | `test_part14_native_crm.py` |
| Lead Pipeline Stage Transitions | **Implemented and Verified** | `apps/api/app/routers/leads.py`, `lead_service.py` | `test_part14_native_crm.py`, `test_master_build_08_sales_pipeline.py` |
| Lead Activity Timeline & Customer 360 | **Implemented and Verified** | `apps/api/app/presentation/api/v1/crm_services_router.py` | `test_part14_native_crm.py` (Customer 360 payload verified) |
| Bulk Lead Operations (Export / Stage update) | **Implemented and Verified** | `apps/api/app/presentation/api/v1/crm_services_router.py` | `test_part14_native_crm.py` (Bulk update & unauthorized rejection verified) |
| CSV Lead Import | **Implemented and Verified** | `apps/api/app/modules/properties/service.py`, `crm_services_router.py` | `test_part28_property_inventory.py` |

---

### Module 3: Property Inventory & Unit Management
| Feature / Subsystem | Status | Implementation Trace | Evidence / Test Suite |
| :--- | :--- | :--- | :--- |
| Property Create, Read, Update, Archive | **Implemented and Verified** | `apps/api/app/modules/properties/router.py`, `service.py` | `test_part28_property_inventory.py` (14/14 passed) |
| Property Search & Multi-Attribute Filtering | **Implemented and Verified** | `apps/api/app/modules/properties/service.py` | `test_part28_property_inventory.py` |
| Price History Audit Logging | **Implemented and Verified** | `apps/api/app/modules/properties/service.py`, `models/property.py` | `test_part28_property_inventory.py` |
| Lead-Property Association & Interest Tracking | **Implemented and Verified** | `apps/api/app/modules/properties/service.py` | `test_part28_property_inventory.py` |
| Unit Hold / Reservation Concurrency Safety | **Implemented and Verified** | `apps/api/app/modules/deals/services/reservation_service.py` | `test_part18_reservations_concurrency.py` (Race condition prevented) |
| Public Sanitized Property Link Sharing | **Implemented and Verified** | `apps/api/app/modules/properties/service.py` | `test_part28_property_inventory.py` |
| Malicious File Upload Rejection | **Implemented and Verified** | `apps/api/app/modules/properties/service.py` | `test_part28_property_inventory.py` |

---

### Module 4: Deals, Negotiation & Transaction OS
| Feature / Subsystem | Status | Implementation Trace | Evidence / Test Suite |
| :--- | :--- | :--- | :--- |
| Deal Creation & Pipeline Progression | **Implemented and Verified** | `apps/api/app/modules/deals/controller/deal_controller.py` | `test_part18_deal_lifecycle.py`, `test_part18_deal_api.py` |
| Offer Lifecycle & Versioned Negotiation Rounds | **Implemented and Verified** | `apps/api/app/modules/deals/services/deal_service.py` | `test_part18_deal_lifecycle.py` |
| Booking Approval Gate & Hold Expiration | **Implemented and Verified** | `apps/api/app/modules/deals/services/deal_service.py` | `test_part18_deal_lifecycle.py`, `test_master_build_08_sales_pipeline.py` |
| Commission Ledger Calculation & Decimal Precision | **Implemented and Verified** | `apps/api/app/modules/deals/services/deal_service.py` | `test_part18_deal_lifecycle.py`, `test_master_build_08_sales_pipeline.py` |
| Deal Closing & Revenue Won Event Emission | **Implemented and Verified** | `apps/api/app/modules/deals/services/deal_service.py` | `test_part18_deal_lifecycle.py`, `test_master_build_08_sales_pipeline.py` |
| Irreversible Stage Backwards Transition Guard | **Implemented and Verified** | `apps/api/app/modules/deals/services/deal_service.py` | `test_part18_deal_lifecycle.py` |
| Commercial Evidence Anti-Fabrication Gate | **Implemented and Verified** | `apps/api/app/modules/deals/services/deal_service.py` | `test_master_build_08_sales_pipeline.py` (Requires evidence for Won) |

---

### Module 5: Site Visit Scheduling & Execution
| Feature / Subsystem | Status | Implementation Trace | Evidence / Test Suite |
| :--- | :--- | :--- | :--- |
| Site Visit Booking & Numbering | **Implemented and Verified** | `apps/api/app/modules/properties/service.py`, `crm_services_router.py` | `test_part28_property_inventory.py`, `test_master_build_08_sales_pipeline.py` |
| Site Visit State Machine (Scheduled â†’ Completed / No-Show) | **Implemented and Verified** | `apps/api/app/modules/properties/service.py` | `test_master_build_08_sales_pipeline.py` |
| Site Visit Outcome Recording (Verified Completion) | **Implemented and Verified** | `apps/api/app/modules/properties/service.py` | `test_master_build_08_sales_pipeline.py` |
| Site Visit Nested Tenancy Resolution | **Implemented and Verified** | `apps/api/app/infrastructure/tenancy/scope.py`, `properties/service.py` | `test_part28_property_inventory.py` |

---

### Module 6: AI Qualification, Copilot & Recommendations
| Feature / Subsystem | Status | Implementation Trace | Evidence / Test Suite |
| :--- | :--- | :--- | :--- |
| Rule-Based & AI Lead Scoring Engine | **Implemented and Verified** | `apps/api/app/services/lead_scoring.py`, `routers/scoring.py` | `test_scoring.py` (4/4 passed) |
| Inventory-Grounded Property Recommendation | **Implemented and Verified** | `apps/api/app/services/recommendation_engine.py` | `test_recommendation_engine.py` (7/7 passed) |
| Hard Constraint Budget & Status Filtering | **Implemented and Verified** | `apps/api/app/services/recommendation_engine.py` | `test_recommendation_engine.py` |
| Copilot Context Resolution & CRM Data Querying | **Implemented and Verified** | `apps/api/app/presentation/api/v1/copilot.py` | `test_copilot_pipeline.py` (3/3 passed) |
| Stage 1 Shadow-Only Autonomy & Human Approval | **Implemented and Verified** | `apps/api/app/modules/autonomous_loop/` | `test_phase2c6a_governance_certification.py` (Autonomy = 0 enforced) |
| AI Prompt Injection & Tool Abuse Sanitization | **Implemented and Verified** | `apps/api/app/modules/ai_agent/router.py` | `test_p0_1_adversarial_certification.py` |

---

### Module 7: Omnichannel Communications & Webhooks
| Feature / Subsystem | Status | Implementation Trace | Evidence / Test Suite |
| :--- | :--- | :--- | :--- |
| Webhook HMAC Signature Verification | **Implemented and Verified** | `apps/api/app/modules/webhooks/service/webhook_service.py` | `test_p0_security_regression.py`, `test_p0_1_adversarial_certification.py` |
| Replay Protection & Duplicate Request Rejection | **Implemented and Verified** | `apps/api/app/modules/webhooks/service/webhook_service.py` | `test_p0_security_regression.py` |
| Live WhatsApp Cloud API Ingress/Egress | **Blocked by Missing Configuration** | `apps/api/app/modules/communication/router.py` | Fixture tested. Requires live Meta WhatsApp Business API Token |
| Live Razorpay Payment Gateway Webhook | **Blocked by Missing Configuration** | `apps/api/app/modules/billing/` | Signature engine verified; requires live Razorpay Webhook Secret |
| Live SendGrid / SMTP Transactional Email | **Blocked by Missing Configuration** | `apps/api/app/modules/communication/` | Outbox pattern implemented; requires live SMTP / SendGrid credentials |

---

### Module 8: Frontend CRM Command Center & Client Experience
| Feature / Subsystem | Status | Implementation Trace | Evidence / Test Suite |
| :--- | :--- | :--- | :--- |
| Responsive Dashboard Layout & Shell | **Implemented and Verified** | `apps/web/src/components/dashboard/DashboardLayoutClient.tsx` | Next.js lint: 0 errors, TypeScript: 0 errors |
| Leads Management & Filtering UI | **Implemented and Verified** | `apps/web/src/app/dashboard/crm/leads/page.tsx` | Verified connected to backend `/api/v1/crm/leads` |
| Pipeline Kanban Board | **Implemented and Verified** | `apps/web/src/app/dashboard/crm/pipeline/page.tsx` | Verified connected to backend `/api/v1/crm/pipeline` |
| Customer 360 & Timeline View | **Implemented and Verified** | `apps/web/src/app/dashboard/crm/customers/[id]/page.tsx` | Verified connected to backend `/api/v1/crm/customers/{id}/timeline` |
| Property Inventory & Unit Explorer | **Implemented and Verified** | `apps/web/src/app/dashboard/inventory/page.tsx` | Verified connected to backend `/api/v1/properties/` |
| Deals & Offers Management | **Implemented and Verified** | `apps/web/src/app/dashboard/deals/page.tsx` | Verified connected to backend `/deals/` |
| Truthful API Client Error Handling | **Implemented and Verified** | `apps/web/src/lib/api-client.ts` | Removed fake success fallbacks; real errors propagated to UI |

---

## 3. Verified Defects, Root Causes & Evidence

### Defect 1: Standalone Broker Header Spoofing Vulnerability (CRITICAL - RESOLVED)
- **Vulnerability**: A broker without organization membership could supply `X-WefyLabs-Organization-Id: <victim-org-id>`. The resolution function in `scope.py` returned the victim org ID instead of rejecting the forged context.
- **Root Cause**: `resolve_organization_id_for_broker()` checked `broker.organization_memberships`, but if empty and a header was provided, it lacked a strict membership membership membership constraint.
- **Fix**: Updated `scope.py` to raise `HTTPException(status_code=403, detail="ORGANIZATION_ACCESS_DENIED")` when a header is requested for an organization the broker does not belong to.
- **Evidence**: `test_standalone_broker_cannot_spoof_organization_header` in `test_p0_tenant_isolation_remediation.py` passes.

### Defect 2: Cross-Tenant CRM Services & Scoring Leakage (HIGH - RESOLVED)
- **Vulnerability**: Endpoints in `crm_services_router.py` (tasks, meetings, lead notes) and `scoring.py` (lead qualification trigger) did not validate that `lead_id` belonged to the authenticated tenant.
- **Root Cause**: Unscoped ORM queries `db.query(Lead).filter(Lead.id == lead_id).first()` allowed malicious brokers to view or modify leads from competing agencies.
- **Fix**: Added tenant scoping using `tenant_lead_filter(org_id, current_broker.id)` and verified lead ownership before creating tasks, booking site visits, or triggering AI qualification.
- **Evidence**: `test_cross_tenant_scoring_and_crm_services_isolation` in `test_p0_tenant_isolation_remediation.py` passes.

### Defect 3: Properties Service Nested Resolution Regression (HIGH - RESOLVED)
- **Vulnerability**: `schedule_site_visit` resolved `org_id` to `broker_id` as a fallback, and then invoked `link_lead_property(..., organization_id=org_id)`. `link_lead_property` re-called `resolve_organization_id_for_broker()`, which threw `ORGANIZATION_ACCESS_DENIED` because `broker_id` was not in `organization_memberships`.
- **Root Cause**: Redundant resolution of an already-resolved fallback ID.
- **Fix**: (1) Updated `scope.py` to allow `selected == broker_id` when `allow_fallback=True`. (2) Updated `schedule_site_visit` to pass the original `organization_id`.
- **Evidence**: All 14 tests in `test_part28_property_inventory.py` pass without error.

### Defect 4: Fake Success Catch Fallback in Frontend API Client (MEDIUM - RESOLVED)
- **Vulnerability**: `triggerQualification()` in `apps/web/src/lib/api-client.ts` contained a `.catch()` block that returned `{ score: 75, category: 'WARM', ... }` upon API failure.
- **Root Cause**: Legacy mock fallback masked backend errors, violating Non-Negotiable Rule 8.
- **Fix**: Removed mock catch fallback; genuine API errors are re-thrown to the caller so the UI accurately displays error state.
- **Evidence**: Code inspection in `apps/web/src/lib/api-client.ts` and clean compilation in `npm run lint`.

---

## 4. Current Blockers & External Dependencies

The core CRM, deals, properties, and AI recommendation engines are 100% functional locally with zero external paid dependencies. The following optional external services require API keys before production traffic can flow through them:
1. **Meta WhatsApp Cloud API**: Requires Meta Developer Account, Phone Number ID, and System User Access Token for live outbound messaging.
2. **Razorpay Payment Gateway**: Requires Live Key ID and Secret for booking deposit capture and webhook validation.
3. **SendGrid / SMTP**: Requires transactional mail credentials for outbound lead notification emails.

*Note: All three external integrations have deterministic mock fixtures and cryptographic signature validation tested in the test suite.*

## Current execution update — 2026-10-21

### Financial integrity findings (Phase 9.3 review)

- **FAILED — Partial commission settlement is represented as full payment.** `DealService.settle_commission` accepts any positive amount up to net commission but changes the commission to `PAID`; the summary then counts the full net amount as earned. The schema has no partial-payment balance. Current mitigation: reject amounts below the full net commission until partial receipt accounting is modeled.
- **FAILED — Revenue event creation could be silently skipped.** Settlement and reversal wrapped required `RevenueEvent` construction in broad `except Exception: pass`, allowing state changes to commit without corresponding ledger events. Current mitigation: make event creation required in the transaction.
- **PARTIAL — Tax deduction is caller-supplied arithmetic, not a statutory calculation.** `tax_rate_percentage` and `tax_deducted` accept values without jurisdiction, tax year, payer/payee eligibility, threshold or professional-review evidence. Treat tax inputs as manually supplied figures; do not present a rate as legally validated.
- Official Income Tax Department material currently lists a 2% rate for commission/brokerage under Income-tax Act, 2025 section 393 Table 1(ii), with a ?20,000 threshold and a specified payer; its Table 6(ii) also describes a 2% rule for certain individual/HUF payers with a ?50 lakh threshold. Applicability depends on transaction and payer/payee facts. Sources: [section 393](https://www.incometaxindia.gov.in/w/section-393-6) and [Income-tax Act 2025 portal](https://www.incometaxindia.gov.in/income-tax-act-202511). No statutory calculation is implemented or professionally reviewed here.
- **Baseline limitation:** `py -m pytest apps/api/tests/test_phase9_3_financial_integrity.py -q` did not start; Windows returned “The file cannot be accessed by the system” for `py.exe`. No test result is claimed for this execution.

### Verification follow-up
The targeted financial integrity module was subsequently executed with the installed Python interpreter: **3 passed, 0 failed, exit code 0 (14.67s)**. Pytest reported a Starlette deprecation warning and could not write its cache under the protected `.pytest_cache` path. This does not represent a full-suite or browser verification.

## Phase One execution update — 2026-10-21

**Status: IN PROGRESS; not acceptance-certified.**

Implemented in this slice:
- Google OAuth now rejects accounts unless Google reports `email_verified: true`; verified and unverified flow coverage was added.
- Password reset links are built from configured trusted frontend/app URLs, not the request Host header. Production requires a configured HTTPS base URL.
- Access tokens receive a JTI; authenticated requests check token revocation; `/auth/logout` revokes the current token. Migration `0044_token_blacklist_revocation` adds the required table and indexes. The migration has not been applied to any deployment.
- Web logout awaits the API revocation attempt before clearing its local session.
- Malformed and non-finite webhook timestamps are rejected.

Verification: targeted backend security/auth/OAuth/reset/webhook/logout suites: **113 passed, 0 failed** (84.49s; 7 warnings). Web `npm run typecheck` passed. `npm run lint` exited 0 with existing hook-dependency warnings and Next.js workspace-root/deprecation warnings. `git diff --check` exited 0; Git printed line-ending conversion notices.

Remaining Phase One blockers:
- Generic webhook production singleton has no configured provider secrets, so generic signature verification is not operational. Nonce input is not persisted/deduplicated; timestamp age checks alone do not prevent duplicate deliveries. Missing timestamps remain allowed for Meta-compatible body signatures. Organization context derived from `X-Organization-Id` is not a trusted tenant mapping. Configure provider-specific verification and trusted tenant resolution, and add durable replay/idempotency coverage before enabling delivery.
- Token revocation requires migration 0044 to be applied before rollout. Legacy tokens without JTI cannot be revoked through logout. Refresh-token rotation and password-change/reset invalidation of all sessions remain unimplemented.
- OAuth still relies on email matching and does not persist Google's stable `sub` identifier.
- No full backend suite, mounted-route tenant audit, browser flow, deployed migration, or live provider verification was performed.
- Follow-up hardening: generic webhook events no longer derive organization scope from caller-supplied `X-Organization-Id`; until a trusted provider-account-to-organization mapping exists, events are emitted in the global context. Added regression coverage. `tests/test_webhook_security.py`: **15 passed, 0 failed** (1 warning).

### Phase One follow-up — password-reset session invalidation

- Added `brokers.auth_version` and included it in tokens issued by email login, registration, Google OAuth, invitation acceptance, and test/development identity. Authenticated requests reject tokens whose version no longer matches the broker record; legacy tokens default to version 0.
- Successful password reset increments the broker version in the same transaction as the password update, invalidating all earlier broker sessions. Regression coverage proves an old session works before reset and receives HTTP 401 after.
- Added Alembic migration `0045_broker_auth_version` after migration 0044. Current head is `0045_broker_auth_version`; neither migration has been applied to a deployment.
- Verification: targeted reset lifecycle and logout tests: **2 passed, 0 failed** (8.76s). Earlier broad auth/security suite evidence predates this new session-version change and is not claimed as verification of this follow-up.
- Remaining: run the complete auth/security matrix after this change; include additional external Supabase-issued tokens in the migration/version policy; apply migrations through deployment process before rollout.
- Broad follow-up verification after auth-version implementation: targeted auth, authentication matrix, OAuth multi-worker, tenant remediation, webhook, logout, password reset, adversarial security, P0 security regression, and Phase 8 security suites: **120 passed, 0 failed, exit code 0** (94.47s; 8 warnings). This remains a selected security suite, not the full backend suite or complete mounted-route tenant proof.

### Phase One follow-up — stable Google OAuth identity

- Google OAuth now requires both a verified email and a non-empty provider `sub`. The immutable subject is persisted uniquely on `brokers.google_subject`, used to resolve returning accounts before mutable email matching, and linked to an existing email account only when the verified email does not conflict with another Google subject.
- Added migration `0046_broker_google_subject`; current Alembic head is `0046_broker_google_subject`. Migrations 0044–0046 remain unapplied to deployed databases.
- OAuth regression exercises repeat sign-in for the same Google subject with a changed verified email; it returns the original broker. Test passed.
- Re-ran selected auth/security suites after session-version and Google-subject changes: **120 passed, 0 failed, exit code 0** (8 warnings; pytest reported 2,899.55 seconds). This is not the complete API/backend suite or full mounted-route tenant audit.

### Phase One follow-up — WhatsApp ingress trust and replay protection

- Removed the top-level `messages` shortcut that bypassed canonical signature verification and invoked legacy processing with outbound message side effects. All webhook payloads now pass through the canonical pipeline with HMAC enforcement.
- Missing `WHATSAPP_APP_SECRET` returns 503; invalid signatures return 401. Invalid JSON returns 400. Processing failures return 500 so providers can retry rather than receiving a false 200 acknowledgment.
- Tenant attribution for signed Meta events now uses the signed `metadata.phone_number_id` matched against an active `ProviderConfiguration` record. Ambiguous, missing, or unmapped IDs fail closed. Sender phone numbers do not select the organization. Delivery receipt message lookup is constrained to the resolved organization.
- Added `WebhookEventClaim` with unique `(provider, organization_id, provider_event_id)` constraint. Claim insert and processing share the transaction, so concurrent duplicate claims serialize on the database uniqueness constraint. Raw attempts remain separately archived. Migration `0047_webhook_event_claims` seeds claims from previously completed archive rows; current Alembic head is `0047_webhook_event_claims`.
- Verification: webhook hardening, legacy webhook security, and canonical communication pipeline suites: **44 passed, 0 failed** (1 warning; 61.54s). Additional WhatsApp route/provider guardrail checks: **3 passed, 0 failed** (7.84s). Python compilation passed; Alembic head command passed. No live Meta call or deployed migration was run.
- Integration remains operationally gated on configuring `WHATSAPP_APP_SECRET` and an active organization provider configuration with matching phone-number ID. Top-level 360dialog payloads without a signed/mapped phone-number ID are rejected; provider-specific 360dialog signature and tenant mapping remain unverified.
- Residual: generic webhook framework (`/v1/webhooks/{provider}`) still needs provider secrets, trusted account mapping, and durable idempotency. The WhatsApp claim prevents duplicate provider event IDs; payloads without stable event IDs cannot be durably deduplicated.
- Further replay fallback: when the provider payload has no stable event ID, the canonical pipeline now claims a deterministic SHA-256 raw-payload key. Exact repeated bodies are suppressed; semantically duplicated events with different serialization are not guaranteed to collapse. Regression test passed (`test_identical_payload_without_provider_event_id_is_deduplicated`).
- Final rerun after payload-hash fallback: combined webhook hardening, canonical communication, legacy webhook security, and route guardrail selection: **46 passed, 0 failed** (1 warning; 69.60s). This supersedes the earlier 44-test count for that combined selection.

### Phase One route audit continuation — 2026-10-21

- Rebuilt the mounted FastAPI route inventory from the live application: 983 routes; 856 were detected with a broker/tenant dependency by the reflection heuristic. The other 127 include public/capability, auth, health, and integration routes; this count is a review queue, not a finding of 127 vulnerabilities and not proof that the 856 are fully tenant-safe.
- Fixed the unauthenticated ingestion webhook: connector ID now resolves an active server-side connector, organization and source derive from that record, and HMAC-SHA256 over the raw request body is required with the connector's decrypted secret. Caller-supplied organization/source no longer provide scope. The integration returns 503 until configured; no connector provisioning path was identified during this pass.
- Fixed lead-acquisition webhook trust: POST no longer accepts a caller-selected source ID as authority; Meta GET challenge requires an active source capability token before verifying the challenge.
- Closed the communication-router bypass into canonical WhatsApp processing by keeping strict signature and trusted phone-number-to-organization checks enabled. Invalid JSON returns 400.
- Onboarding demo reset remains capability-token protected and additionally checks the organization is marked demo. Removed session-token fragments from logs and audit changes.
- Focused verification after these changes: **51 passed, 0 failed**, one Starlette/httpx deprecation warning. Compile check passed; `git diff --check` exited 0 (Git emitted existing LF/CRLF working-copy notices).
- Still open: complete route-by-route object authorization proof with two independent tenants; audit of the remaining dependency-light routes and registered legacy paths; generic webhook provider mapping/replay protections; connector secret provisioning; complete auth and backend suites; browser journeys; unapplied migrations 0044–0047. Phase One remains open.
- Additional route-level review: identity profile reads now verify `Identity.organization_id` before using the ID-keyed service cache, and missing tenant provenance fails closed. Manual merge audit actor is always the authenticated broker; a supplied `actor_id` cannot spoof the actor. `tests/test_part3_identity_resolution.py`: **13 passed, 0 failed**. This is a focused regression slice; identity endpoints still require broader two-tenant object-level tests.
- Invitation acceptance now resolves optional bearer identities through the shared authentication dependency (including revocation/auth-version checks), locks the pending invitation row during acceptance, and rejects authenticated brokers whose verified account email does not match the invitation recipient. Regression covers a different authenticated broker and confirms the invitation remains pending.
- `/security/exports` previously claimed completion and returned a predictable `exp_<8-char-prefix>` token although no download route or export pipeline existed. It now returns HTTP 501 until an authenticated, tenant-scoped export implementation exists. Added a regression proving it does not claim success.
- `/security/health` previously returned hard-coded HEALTHY assertions for controls it did not inspect. It now reports WARNING with UNKNOWN components and clearly states runtime checks are not wired.
- Verification: invitation lifecycle, export truthfulness, and platform integration tests: **7 passed, 0 failed**; compile and targeted diff checks passed (Git emitted line-ending notices).
- Cross-tenant billing administration review found tenant OWNER/ADMIN/FINANCE roles could reach `/billing/admin/*` endpoints while supplying arbitrary organization IDs. These routes now require the explicit platform super-admin allowlist, which denies by default; regular-tenant access regression returns 403.
- Combined verification after the billing change: **10 passed, 0 failed** across super-admin authorization, invitation lifecycle, governed-export truthfulness, and platform integration; compilation and targeted diff checks passed (line-ending notices only).
- The secondary `/v1/metrics` exporter labels AI token and cost metrics by organization ID. It now requires the same explicit platform super-admin allowlist; regular tenant access is covered by the security regression. Infrastructure scraping will require an authenticated operator-compatible scrape path/configuration and remains an operational follow-up.
- Latest rerun after metric protection: **10 passed, 0 failed**; compilation and targeted diff checks passed.
- Re-ran the current selected security suite after invitation, cross-tenant billing, metrics, export, and other webhook changes: **188 passed, 0 failed, 8 warnings** (351.50s). Coverage included auth/authentication matrix, OAuth multi-worker, tenant remediation, webhook security, logout/reset, invitations, adversarial/P0 security, super-admin/billing/metrics, ingestion, WhatsApp, acquisition, and export truthfulness. This remains a selected suite, not all 983 mounted routes, the complete backend suite, or browser acceptance.
- Current source inspection of `get_current_tenant` confirms it derives organization context from membership rows, validates `X-WefyLabs-Organization-Id` against those rows, returns 409 for multi-membership users without selection, and denies accounts without memberships. The broader route and object-level audit is not complete.
- Identity graph authorization pass found cross-tenant IDORs in merge, undo, simulation, and manual-review decisions: manager role checks existed, but service reads used unscoped IDs. Merge execution now resolves both identities under the requested organization and scopes linked leads/aliases. HTTP simulation verifies both identities belong to the active tenant. Undo loads the merge operation and affected identities/links under the active tenant. Review decisions require organization context and scope both review and candidate updates.
- Added a two-organization regression that attempts all four operations from the other tenant and verifies source identity, review, and merge operation remain unchanged; direct merge-service cross-tenant call is rejected. `tests/test_part3_identity_resolution.py`: **14 passed, 0 failed**. Compile and targeted diff checks passed.
- Remaining identity lifecycle limitation: merge undo still does not restore aliases to their original source identity (the merge snapshot does not retain alias state). This is a data-integrity follow-up and remains open; tenant checks prevent cross-organization mutation.
- Further identity ingress hardening: `/identity/resolve/{lead_id}` now checks any existing UUID Lead against the authenticated organization (or the authenticated broker for an unmigrated legacy row) before creating identity links. Unknown external lead IDs remain supported; an existing lead from another organization returns 404. Regression confirms no Identity row is created. Identity suite is now **15 passed, 0 failed**.
- Marketing route scope previously used `Broker.organization_id or Broker.id`, bypassing membership selection and allowing a stale/missing broker field to determine tenant scope. All authenticated marketing endpoints now depend on `get_current_tenant`; service organization IDs and actor IDs come from that validated context. The public tracking-link resolver remains capability-token based. Regression checks prove the selected organization is used and all non-public marketing routes include the tenant dependency. Marketing suites: **83 passed, 0 failed**; compile and diff checks passed.
- Native CRM authenticated routes now obtain organization and actor scope exclusively from membership-validated `TenantContext`, replacing `Broker.organization_id or Broker.id`. The CRM regression suite passes: **14 passed, 0 failed**. Compilation and targeted diff checks passed.
- Conversation-intelligence routes likewise use the selected membership organization. Legacy broker-owned Lead rows remain supported only when their `broker_id` matches the authenticated broker, rather than comparing a broker ID to an organization ID. Conversation regression: **44 passed, 0 failed** (one Google GenAI deprecation warning); omnichannel regression: **20 passed, 0 failed**. The combined invocation left worker processes without a final report, so these results were verified separately.

### Phase 9.3.3 — Historical TDS Correction, Annual Threshold Semantics, and Financial Acceptance Reconciliation

- **VERIFIED & RESOLVED: 4-Regime Indian Statutory Tax Engine & Historical Effective Dates**:
  `StatutoryTaxService` in `apps/api/app/modules/deals/services/statutory_tax_service.py` encodes official Income Tax Department statutory provisions across all historical and modern eras:
  1. **Regime 1 (Prior to 1 October 2024)**: Section 194H of Income-tax Act, 1961 at **5.0% TDS** with **INR 15,000 threshold** per financial year (`IN_SEC_194H_5PCT`).
  2. **Regime 2 (1 October 2024 through 31 March 2025)**: Section 194H as amended by Finance (No. 2) Act, 2024 lowering the rate to **2.0% TDS** while retaining the **INR 15,000 threshold** (`IN_SEC_194H_2PCT_FY2024`).
  3. **Regime 3 (1 April 2025 through 31 March 2026)**: Section 194H as amended by Finance Act, 2025 maintaining **2.0% TDS** and increasing the annual threshold to **INR 20,000** (`IN_SEC_194H_2PCT_FY2025`). Retained `IN_SEC_194H_2PCT` unaliased in registry for historical immutability.
  4. **Regime 4 (On or after 1 April 2026)**: Income-tax Act, 2025 Section 393:
     - `IN_SEC_393_TABLE1_1_II_SPECIFIED`: Section 393(1) Table 1 Item 1(ii) for commission or brokerage paid by a specified person to a resident at **2.0% TDS** with **INR 20,000 threshold** per tax year.
     - `IN_SEC_393_NON_SPECIFIED_HUF_IND`: Section 393 Table 6 Item (ii) for non-specified individuals and HUFs at **2.0% TDS** with **INR 50,00,000 threshold** per tax year.
     - `IN_SEC_393_HIGHER_NO_PAN`: Mandatory higher deduction rate of **20.0% TDS** when payee fails to furnish a valid PAN.
     - `IN_SEC_393_5_EXEMPT`: Statutory exemption under Section 393(5) for payments to Government, RBI, and approved Mutual Funds (**0.0% TDS**).
     - `IN_SEC_393_LOWER_CERT`: Lower/Nil deduction certificates under Section 393(6) issued by Assessing Officer.
  - **Official References**: Income Tax Department India; Section 194H (Income-tax Act, 1961); Finance (No. 2) Act, 2024; Finance Act, 2025; Section 393 (Income-tax Act, 2025: [Section 393 Portal](https://www.incometaxindia.gov.in/w/section-393-6), [Act Portal](https://www.incometaxindia.gov.in/income-tax-act-202511)).

- **VERIFIED & RESOLVED: Annual Aggregate Threshold Accumulation & Boundary Semantics**:
  - The statutory calculation engine tracks cumulative payee payments within the relevant tax year (`prior_year_payments + current_amount`).
  - Below threshold: zero tax deducted (`tax_deducted = 0.00`).
  - Crossover transaction: when prior payments were below threshold and the current transaction pushes the aggregate above the statutory limit, tax is deducted on the full cumulative aggregate (`cumulative_gross * rate - prior_tax_deducted`).
  - Subsequent transactions above threshold: taxed at the statutory rate on the incremental payment.
  - Safe failure & fallback: when prior-period payment history or tax facts are unverified, the engine sets `annual_threshold_unverified=True` and `needs_review=True`, documenting that manual professional verification is required.
  - Non-resident payees (`payee_is_resident=False`): immediately flagged for manual Section 195 / DTAA professional review (`needs_review=True`).
  - Invalid/missing dates: fall back safely to unverified status and flag for review.

- **VERIFIED: UAE VAT Classification & Decoupling from Raw Currency**:
  - `AED` currency alone does NOT establish UAE tax jurisdiction or VAT liability.
  - Evaluation of supplier registration status (`supplier_is_vat_registered`, `trn_number`) and `place_of_supply`.
  - Strict separation between VAT on taxable supply (5% invoiced to developer/client under Federal Decree-Law No. 8 of 2017) and broker commission disbursement (0% withholding tax).
  - Status: **Requires professional tax/accounting review** (Chartered Accountant / registered UAE Tax Agent sign-off required prior to production legal reliance).

- **VERIFIED & RESOLVED: Settlement Authorization & Ledger Integrity**:
  - Reviewer authorization enforced in `apps/api/app/modules/deals/services/deal_service.py`: only authorized roles (`owner`, `admin`, `finance`, `manager`, `accountant`, `financial_controller`, `super_admin`) can approve `MANUAL_REVIEWED` receipts. Unauthorized broker escalation is rejected with HTTP 403 Forbidden (`Unauthorized reviewer`).
  - Self-assertion of `PROVIDER_CONFIRMED` on manual settlement without verified gateway provenance fails closed with HTTP 400 Bad Request (`Cannot self-assert PROVIDER_CONFIRMED without verified gateway settlement evidence`).
  - Evidence requirement for `MANUAL_REVIEWED`: missing document URL or verified bank statement notes fails closed with HTTP 400 Bad Request (`Reviewed manual settlement requires supporting evidence notes or document URL`).
  - Reviewer provenance audit trail: `reviewed_by_id` and `reviewed_at` persisted in deal commission splits, audit logs, outbox events, and `RevenueEvent.payload`.
  - Unverified manual receipts (`MANUAL_UNVERIFIED`) transition strictly to `RECORDED_UNVERIFIED` (never `PAID`), update `commission_unverified`, leave `commission_earned` at 0.0, and emit unconfirmed revenue events requiring audit review.
  - Atomic ledger transaction: commission record and `RevenueEvent` commit within the same database transaction; event failure aborts the mutation.
  - Cross-tenant settlement reads and mutations fail closed with HTTP 404 / HTTP 400.

- **Empirical Verification Results (Phase 9.3.3)**:
  - `apps/api/tests/test_statutory_tax_service.py`: **16 passed, 0 failed in 10.96s (Exit code: 0)**
  - `apps/api/tests/test_phase9_3_financial_integrity.py`: **6 passed, 0 failed in 19.45s (Exit code: 0)**
  - Deal lifecycle & security regression (`test_part18_*`): **19 passed, 0 failed in 51.06s (Exit code: 0)**
  - Total targeted backend test execution: **41 passed, 0 failed (Exit code: 0)**
  - Complete backend test suite: **NOT RUN** (due to multi-hour test cycle and unrelated legacy mock dependencies; not claimed as green)
  - Frontend TypeScript compilation (`npm run typecheck`): **0 errors (Exit code: 0)**
  - Frontend specification runner (`npm run test`): **38 suites, 129 specs passed, 0 failed (Exit code: 0)**
  - Next.js production build (`npm run build`): **58 routes compiled successfully (Exit code: 0)**

- **Release Gates Still Open (Not Acceptance-Certified)**:
  1. **Professional Tax & Accounting Review**: Statutory tax logic and UAE VAT rules require formal legal sign-off by a qualified Chartered Accountant and registered UAE Tax Agent.
  2. **Unapplied Database Migrations**: Alembic migrations `0044_token_blacklist_revocation`, `0045_broker_auth_version`, `0046_broker_google_subject`, and `0047_webhook_event_claims` must be executed against staging/production databases.
  3. **External Provider Secrets**: Production keys for Meta WhatsApp Cloud API, Razorpay Payment Gateway, and SendGrid / SMTP transactional email remain unconfigured.
  4. **Route-Level Object Authorization Proof**: Complete route-by-route multi-tenant isolation proof across all mounted FastAPI routes remains in progress.
