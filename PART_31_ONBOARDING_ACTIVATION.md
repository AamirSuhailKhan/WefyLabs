# PART 31 — PRODUCTION-GRADE CUSTOMER ONBOARDING, TENANT ACTIVATION & DEMO MODE
*Production Technical Architecture, Progressive Onboarding State Machine, Centralized Deterministic Activation Engine, Ephemeral Isolated Demo Mode, and Formula-Sanitized Ingestion*

---

## 1. Executive Summary & Product Philosophy

Part 31 introduces **zero-founder-intervention onboarding** for multi-tenant real estate agencies. Rather than confronting new agency founders with an intimidating settings dashboard, the onboarding engine progressively guides the user through the CRM's core value loop:

```
SIGN UP ➔ VERIFY ➔ WORKSPACE PROFILE ➔ FIRST PROPERTY ➔ FIRST LEAD ➔ AI MATCHING ➔ FOLLOW-UP TASK ➔ COMMAND CENTER (ACTIVATED)
```

### Key Invariants Maintained:
1. **Server-Authoritative State**: Onboarding and activation progress is computed and verified by backend services against real database entities. Frontend UI state is never trusted blindly.
2. **Deterministic Activation (0–100 Score)**: A tenant is activated only when core business entities exist in the live database (Organization + Property + Lead + Match + Task/Follow-up).
3. **Seamless Existing Tenant Protection**: Organizations created prior to Part 31 that already have properties and leads automatically evaluate as fully activated with zero disruption or forced re-onboarding.
4. **Hermetic Demo Isolation**: Demo mode operates inside dedicated ephemeral organizations (`is_demo=True`). Demo data never contaminates production queries, and external side effects (real emails via Brevo, WhatsApp, Razorpay payments, external calendar writes) are strictly blocked.
5. **CWE-1236 Formula Injection Neutralization**: All CSV import cells starting with dangerous calculation prefixes (`=`, `+`, `-`, `@`, `\t`, `\r`) are neutralized before storage.
6. **Safety Rules**: WhatsApp remains **COMPLETELY DISABLED**; Razorpay LIVE mode remains **DISABLED**. Exactly one single Alembic head maintained (`0024_onboarding_activation_demo`).

---

## 2. Architecture & Data Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                   FRONTEND: Next.js 15 App Router                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  /onboarding (Multi-step progressive wizard)                     │  │
│  │  - Agency profile, timezone, and currency configuration         │  │
│  │  - Data source selection (Demo Playground, Manual, CSV Import)   │  │
│  │  - First Property & Lead creation shortcuts                     │  │
│  │  - Part 29 AI Lead ↔ Property Match showcase                     │  │
│  │  - Team invitation with RBAC role dropdown                       │  │
│  │  - Command Center launch trigger                                 │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │  OnboardingChecklist.tsx (Live Dashboard card)                   │  │
│  │  - Real-time progress bar synced with DB milestones (no fakes)   │  │
│  │  - Compact activation status banner upon completion              │  │
│  ├──────────────────────────────────────────────────────────────────┤  │
│  │  DemoBanner.tsx (Simulated Playground safety banner)             │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTPS REST (/api/v1/onboarding)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                   BACKEND: FastAPI + Async SQLAlchemy                  │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │  onboarding_router (/api/v1/onboarding)                          │  │
│  │    GET  /status                POST /step                        │  │
│  │    POST /business-profile      GET  /activation                  │  │
│  │    POST /demo/start            POST /demo/reset                  │  │
│  │    POST /import/preview        POST /import/commit               │  │
│  │    POST /invite-team                                             │  │
│  └────────────────────────────────┬─────────────────────────────────┘  │
│                                   │                                    │
│  ┌────────────────────────────────┴─────────────────────────────────┐  │
│  │                     Core Module Services                         │  │
│  │  - OnboardingService: Progressive state machine & checklist      │  │
│  │  - TenantActivationService: Deterministic 0-100 milestone scorer │  │
│  │  - DemoModeService: Isolated synthetic playground & TTL teardown │  │
│  │  - OnboardingCsvImportService: Formula neutralization & dup check│  │
│  │  - InvitationService: Single-use SHA-256 team invitations       │  │
│  └───────┬────────────────────────┬──────────────────────┬──────────┘  │
│          │                        │                      │             │
│          ▼                        ▼                      ▼             │
│   PostgreSQL DB              Upstash Redis         Celery Worker       │
│   (onboarding_states,       (Sliding-window       (demo cleanup &      │
│    tenant_activations,       rate limiter)         snapshots)          │
│    demo_sessions)                                                      │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Onboarding State Machine

The tenant progression is managed through `OnboardingState` with sequential ordered steps:

| Step Code | Purpose | Skippable | Auto-Complete Condition |
|---|---|---|---|
| `ORGANIZATION_SETUP` | Legal name, city, timezone, currency, team size | No | Business profile updated |
| `DATA_SOURCE` | Choice between sample playground, manual, or CSV | Yes | Step action submitted |
| `PROPERTY_SETUP` | Add first inventory listing | Yes | $\ge 1$ PropertyListing exists in DB |
| `LEAD_SETUP` | Capture first buyer inquiry | Yes | $\ge 1$ Lead exists in DB |
| `MATCH_SHOWCASE` | Experience explainable AI matching | Yes | $\ge 1$ Recommendation exists in DB |
| `FOLLOWUP_SETUP` | Schedule site visit or follow-up call | Yes | $\ge 1$ Task or FollowUp exists in DB |
| `TEAM_INVITE` | Invite assistant or co-broker via RBAC | Yes | Invitation created |
| `CALENDAR_CONNECT` | Connect Google Calendar (optional) | Yes | OAuth token present or skipped |
| `COPILOT_INTRO` | Explore AI Copilot suggestions | Yes | Copilot query executed |
| `ACTIVATED` | Final workspace activation celebration | No | Activation score $\ge 80$ |

### Dynamic Synchronization
If a user skips `PROPERTY_SETUP` during the wizard but subsequently adds a property from the inventory page, `OnboardingService.get_status()` automatically detects the live entity in the database, marks `PROPERTY_SETUP` as completed, and increments the progress percentage.

---

## 4. Deterministic Tenant Activation Engine

Activation is evaluated centrally by `TenantActivationService` against live database counts. Each milestone contributes an authoritative weight toward the 100-point activation score:

$$\text{Activation Score} = \sum_{m \in \text{Achieved}} \text{Weight}(m)$$

| Milestone Code | Label | Weight | Required for Activation? |
|---|---|---|---|
| `ORGANIZATION_CREATED` | Workspace Profile Setup | 20 | **Yes** |
| `FIRST_PROPERTY_CREATED` | First Property Added | 20 | **Yes** |
| `FIRST_LEAD_CREATED` | First Lead Added | 20 | **Yes** |
| `FIRST_MATCH_GENERATED` | Lead ↔ Property AI Match | 20 | Yes (or Follow-Up) |
| `FIRST_FOLLOWUP_CREATED` | First Follow-Up / Task Scheduled | 20 | Yes (or Match) |

A workspace is marked `is_activated = True` when:
1. $\text{Activation Score} \ge 80$
2. Organization created, at least one property exists, and at least one lead exists.

### Existing Tenant Protection
For organizations existing prior to Part 31, `TenantActivationService` queries live entity tables on the first request. Organizations with pre-existing leads and properties immediately receive `is_activated = True` and score `100`, preserving full backward compatibility.

---

## 5. Ephemeral Isolated Demo Mode

### Architecture & Isolation Guarantees
1. **Dedicated Tenant Boundary**: Every demo session creates a dedicated `Organization` with `is_demo=True` and a dedicated `Broker` with `is_demo=True`.
2. **Zero Shared Records**: Every demo lead, property, recommendation, and task is bound strictly to `demo_broker.id` and `demo_organization.id`.
3. **No Cross-Tenant Queries**: Standard tenant filters ensure production tenants never see demo inventory, and demo tenants never see production records.
4. **Suppression of Outbound Side-Effects**:
   - Outbound Brevo SMTP emails are suppressed for demo tenants.
   - WhatsApp dispatch remains globally disabled.
   - Razorpay payment orders reject demo tenants.
   - External Google Calendar mutations are simulated.
5. **Seeded Synthetic Inventory**:
   - 10 Realistic properties across Bengaluru, Mumbai, and Gurugram (Indiranagar, Whitefield, Bandra West, Powai, DLF Phase 5).
   - 8 Realistic buyer inquiries with synthetic phone numbers (`+91-98200-XXXXX`), budgets, and preferences.
   - 3 Pre-computed explainable AI property matches (Part 29).
   - 3 Prioritized site visit tasks (Part 27).
6. **Idempotent TTL Cleanup**: Demo sessions have an automatic 48-hour expiration. Both the scheduled Celery task (`cleanup_expired_demo_sessions_task`) and the `/demo/reset` endpoint cascade-purge demo organizations and brokers safely. The reset service explicitly verifies `org.is_demo is True` before executing any deletion, guarding production data from accidental deletion.

---

## 6. Team Member Invitations

Reuses the production `InvitationService` (`app/modules/auth/invitation_service.py`):
- **Token Security**: Cryptographically secure 32-byte urlsafe tokens; SHA-256 hashes stored at rest.
- **Single-Use Enforcement**: Tokens are invalidated immediately upon acceptance.
- **Expiration Window**: 7-day TTL (`expires_at = now + 7 days`).
- **RBAC Validation**: Restricted to allowed roles (`admin`, `manager`, `agent`). Role escalation attempts raise validation errors.
- **Audit Logging**: Every invitation dispatched is logged to `AuditLog`.

---

## 7. Sanitized CSV Ingestion

`OnboardingCsvImportService` provides preview and batch commit capabilities for leads and properties:
- **Formula Injection Defense (CWE-1236)**: `sanitize_csv_cell()` prepends a single quote `'` to any cell starting with dangerous calculation symbols (`=`, `+`, `-`, `@`, `\t`, `\r`), neutralizing DDE/Excel macro exploits.
- **Phone Number Normalization**: Validates and normalizes phone numbers (`re.sub(r"[^\d+]", "", phone)`), preserving international format while preventing quote bypasses.
- **Intra-File & Database Duplicate Detection**: Checks incoming rows against existing phone numbers for leads and existing titles for properties. Duplicates are counted and reported in the preview.
- **Strict Batch Limits**: Maximum 250 rows per batch to prevent memory exhaustion and DoS.
- **Transactional Atomicity**: All valid items are committed in a single database transaction with automatic rollback on failure.

---

## 8. Celery Background Tasks

Integrated into `apps/api/app/tasks/onboarding_tasks.py`:
1. `cleanup_expired_demo_sessions_task`:
   - Runs periodically to purge expired demo workspaces (`expires_at < now`).
   - Strictly verifies `is_demo=True`.
2. `calculate_activation_snapshot_task`:
   - Asynchronously calculates and caches milestone activation scores for reporting.

---

## 9. Copilot Tools Integration

Registered in `apps/api/app/modules/copilot/tools/tool_registry.py`:
1. `get_onboarding_status`: Returns current step, progress percentage, completed steps, and checklist items. (`ToolRiskLevel.READ`)
2. `get_activation_status`: Returns activation score, completed milestones, and missing requirements. (`ToolRiskLevel.READ`)
3. `create_demo_workspace`: Spawns an ephemeral demo playground with synthetic inventory. (`ToolRiskLevel.LOW_RISK_WRITE`)

---

## 10. Database Migrations (Alembic)

Migration revision `0024_onboarding_activation_demo.py` branches cleanly from `0023_agent_command_center`:
- Tables created:
  - `onboarding_states` (id, organization_id, broker_id, current_step, completed_steps, skipped_steps, is_completed, step_data)
  - `tenant_activations` (id, organization_id, is_activated, activation_score, completed_milestones, activated_at, first_property_at, first_lead_at, first_match_at, first_followup_at)
  - `demo_sessions` (id, demo_organization_id, demo_broker_id, session_token, status, expires_at, created_by_ip, metadata_json)
- Organization columns added:
  - `business_type`, `currency_code`, `team_size`, `is_demo`
- Broker column added:
  - `is_demo`
- Single head verified: `0024_onboarding_activation_demo (head)`.

---

## 11. Test Coverage & Verification

| Test Suite | Target | Executed | Status |
|---|---|---|---|
| **Unit Tests** (`test_part31_unit.py`) | $\ge 25$ | 25 | **PASS (100%)** |
| **Integration Tests** (`test_part31_integration.py`) | $\ge 20$ | 21 | **PASS (100%)** |
| **Security Tests** (`test_part31_security.py`) | $\ge 15$ | 15 | **PASS (100%)** |
| **API Tests** (`test_part31_api.py`) | $\ge 15$ | 16 | **PASS (100%)** |
| **Copilot Tests** (`test_part31_copilot.py`) | $\ge 10$ | 12 | **PASS (100%)** |
| **True DB-Backed E2E** (`test_part31_real_e2e.py`) | 1 | 1 | **PASS (100%)** |
| **Frontend TypeScript** (`npx tsc --noEmit`) | 0 errors | 0 errors | **PASS (100%)** |
| **Alembic Single Head Check** | 1 head | 1 head | **PASS (100%)** |

---

## 12. Security Audit & Invariant Enforcement

1. **IDOR & Multi-Tenancy**: Every onboarding and activation mutation enforces `organization_id` resolved from the authenticated broker's membership.
2. **Demo Containment**: Demo records contain `is_demo=True`. Reset operations refuse deletion of any organization without `is_demo=True`.
3. **Formula Sanitization**: Prepends `'` to dangerous formula characters, neutralizing Excel/LibreOffice CSV exploits.
4. **Rate Limiting**: Sliding-window Redis limiter protects demo initialization (`rl:demo_start`, 10 req/min) and general onboarding endpoints.
5. **No Secrets Leakage**: DTOs omit sensitive tokens, passwords, and private keys.
