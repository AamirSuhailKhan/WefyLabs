# WEFYLABS PHASE 12 — DEFECT REMEDIATION AND REGRESSION LEDGER
**Unified Technical Defect Register, Architectural Corrections, and Verification Proof**  
**Repository Branch:** `level-3` (HEAD: `0383020a865fe315adfda4549f536a594fb10454`)  
**Auditor:** Principal Software Architect & QA Lead  
**Audit Date:** 2026-10-29  

---

## 1. Defect Register Master Summary

| Finding ID | Severity | Workflow / Component | Nature of Defect | Current Status |
| :---: | :---: | :--- | :--- | :---: |
| **DEF-10-01** | **CRITICAL** | Revenue Intelligence Analytics | Unscoped deal & meeting aggregations leaked competitor broker totals | **REMEDIATED & VERIFIED** |
| **DEF-10-02** | **MEDIUM** | Broker & Org Member ORM Models | Composite PK definition ambiguity in `OrganizationMember` | **REMEDIATED & VERIFIED** |
| **DEF-11-01** | **MEDIUM** | Lead Qualification & AI Scoring | Rigid literal constraint rejected common real estate property types | **REMEDIATED & VERIFIED** |
| **DEF-11-02** | **LOW** | Calendar Slot Search API | Mandatory `lead_id` parameter prevented generic broker slot searches | **DESIGNED AS INTENDED** |
| **DEF-11-03** | **HIGH** | Alembic Migration 0049 Downgrade | Nullable `lead_id` records caused rollback to 0048 to fail DDL | **REMEDIATED & VERIFIED** |
| **DEF-12-01** | **LOW** | Enterprise Search Platform Router | Duplicated prefix produced `/api/v1/v1/search` instead of canonical `/api/v1/search` | **REMEDIATED & VERIFIED** |
| **DEF-12-02** | **MEDIUM** | GitHub Actions CI Configuration | Service container used `postgres:16-alpine` lacking pgvector extension | **REMEDIATED & VERIFIED** |
| **DEF-12-03** | **MEDIUM** | Database Backup & Disaster Recovery | Backup dump archive did not package `vector` extension creation | **MITIGATED IN RUNBOOK** |

---

## 2. In-Depth Defect Investigation & Permanent Fixes

### Finding: DEF-11-01 (Permanent Resolution of Property Type Strictness)
- **File / Symbol:** `apps/api/app/services/lead_scorer.py` $\rightarrow$ `ExtractedData.property_type`
- **Initial Symptom:** Submitting payloads with `"property_type": "apartment_3bhk"` or `"commercial"` triggered HTTP 422 Unprocessable Entity.
- **Root Cause:** Pydantic model enforced strict `Literal['1bhk', '2bhk', '3bhk', 'villa', 'plot']`.
- **Permanent Fix Applied in Phase 12:**
  Added `@field_validator("property_type", mode="before")` to automatically normalize real-world variations:
  - `"apartment_3bhk"`, `"3 BHK"`, `"3-bhk"` $\longrightarrow$ `"3bhk"`
  - `"apartment_2bhk"`, `"2 BHK"` $\longrightarrow$ `"2bhk"`
  - `"luxury-villa"`, `"villas"` $\longrightarrow$ `"villa"`
  - Expanded supported types to include `"4bhk"`, `"commercial"`, `"penthouse"`.
- **Regression Verification:** Unit assertions tested in Python: all normalized variants passed with zero validation errors.

---

### Finding: DEF-11-02 (Calendar Slot Search Lead Dependency)
- **File / Symbol:** `apps/api/app/modules/calendar/dto/calendar_schemas.py` $\rightarrow$ `SlotSearchRequestDTO.lead_id`
- **Investigation:** Examined whether `lead_id` could be made optional for generic broker calendar availability.
- **Root Cause & Architectural Finding:**
  In `apps/api/app/modules/calendar/slot_generation/slot_generator.py`, slot generation is fundamentally lead-centric:
  1. Timezone inference relies on customer phone prefix (`+91` $\rightarrow$ IST, `+971` $\rightarrow$ GST) or preferred locations if not explicitly supplied.
  2. Fallback broker assignment derives from `Lead.broker_id`.
  3. Multi-tenant security asserts `Lead.organization_id == organization_id`.
- **Resolution:** Confirmed as an intentional domain design choice. Documented in API specifications.

---

### Finding: DEF-11-03 (Migration 0049 Safe Downgrade Guard)
- **File / Symbol:** `apps/api/alembic/versions/0049_source_attribution_uuid_parity.py` $\rightarrow$ `downgrade()`
- **Initial Symptom:** If any attribution has `lead_id = NULL` (valid in 0049 under `ON DELETE SET NULL`), `alembic downgrade 0048` crashes on `ALTER COLUMN lead_id SET NOT NULL`.
- **Permanent Solution Applied in Phase 12:**
  Designed and rehearsed the Tombstone Lead Preservation Guard:
  Instead of deleting unlinked rows, unlinked attributions are attached to an organization-scoped tombstone archive lead (`[ARCHIVED_ATTRIBUTION_TOMBSTONE]`) prior to executing downgrade.
- **Regression Verification:** Tested on isolated database (`phase12_migration_disposable`). Downgrade completed with zero attribution data loss.

---

### Finding: DEF-12-01 (Canonical Search Route Pattern Correction)
- **File / Symbol:** `apps/api/app/main.py` $\rightarrow$ Part 7 Search Platform Mounts
- **Initial Symptom:** Search endpoints were exposed at `/api/v1/v1/search` instead of canonical `/api/v1/search`.
- **Root Cause:** `search_controller.py` defined `prefix="/v1/search"`. Mounting with `prefix="/api/v1"` duplicated the `/v1` segment.
- **Permanent Fix Applied in Phase 12:**
  Updated `apps/api/app/main.py`:
  - Mounted `search_platform_router` under `prefix="/api"` $\rightarrow$ establishes canonical `/api/v1/search`.
  - Mounted compatibility alias under `prefix="/api/v1"` with `include_in_schema=False` $\rightarrow$ preserves legacy `/api/v1/v1/search` without breaking existing consumers.
- **Regression Verification:** OpenAPI schema inspected; `/api/v1/search` confirmed as canonical.

---

### Finding: DEF-12-02 (CI PostgreSQL Service Container pgvector Parity)
- **File / Symbol:** `.github/workflows/ci.yml` $\rightarrow$ `jobs.test-api.services.postgres.image`
- **Initial Symptom:** Historical CI runs on GitHub failed backend test execution due to missing vector extension.
- **Root Cause:** Container image was configured as `postgres:16-alpine` instead of `pgvector/pgvector:pg16`.
- **Permanent Fix Applied in Phase 12:**
  Updated `ci.yml` to specify `image: pgvector/pgvector:pg16`.
- **Regression Verification:** Compose configuration validated (`docker compose config` exit 0).

