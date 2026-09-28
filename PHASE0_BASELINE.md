# PHASE 0 BASELINE — IMMUTABLE CODEBASE INVENTORY

**Baseline Established:** 2026-09-28T17:45:00+05:30  
**Repository Identity:** WefyLabs (formerly BeetleLabs / LeadScore)  
**Corpus / Path:** `c:\Users\aamir\OneDrive\Desktop\crm real state`  
**Engineer:** Principal Software Architect + Security Engineer (Phase 0 Hardening Program)  

---

## 1. GIT REPOSITORY STATE

| Field | Value | Classification |
|---|---|---|
| **Commit Hash** | `bfe45596a4fb5dd085adc0d5d5d5912589213f34` | `[VERIFIED]` |
| **Branch** | `level-1` (tracking `origin/level-1`) | `[VERIFIED]` |
| **Tags** | `v1.0.0-rc1` | `[VERIFIED]` |
| **Working Tree State** | Dirty (Phase 0 initial hardening underway: 16 modified files, 2 untracked files in `app/common/auth/`) | `[VERIFIED]` |

### Dirty Working Tree Breakdown:
- `.github/workflows/ci-cd.yml` (CI gate security hardening)
- `.github/workflows/ci.yml` (CI failure enforcement)
- `apps/api/app/modules/auth/router.py` (OAuth state issuance & session binding)
- `apps/api/app/modules/auth/schemas.py` (Removal of caller-controlled email/name)
- `apps/api/app/modules/auth/service.py` (P0.1 removal of caller-controlled OAuth identity & mock paths)
- `apps/api/app/common/auth/oauth_state.py` (Untracked: P0.1 distributed Redis OAuth state & replay protection)
- `apps/api/app/modules/billing/services/razorpay_service.py` (Canonical catalog resolution & test-mode bypass quarantine)
- `apps/api/tests/conftest.py`, `test_auth.py`, `test_authentication_matrix.py`, etc.
- `apps/web/src/app/auth/callback/page.tsx`, `login/page.tsx`, `register/page.tsx`, `lib/api-client.ts`

---

## 2. RUNTIME & TOOLCHAIN VERSIONS

| Tool | Version | Notes | Classification |
|---|---|---|---|
| **Python** | `3.14.6` | System Windows Python | `[VERIFIED]` |
| **Pip** | `26.1.2` | Python package installer | `[VERIFIED]` |
| **Node.js** | `v24.14.1` | Active Node runtime | `[VERIFIED]` |
| **npm** | `11.11.0` | Active Node package manager | `[VERIFIED]` |
| **Docker Client** | `29.6.2` | Engine: desktop-linux (daemon inactive) | `[VERIFIED]` |

---

## 3. ARCHITECTURAL & CODE METRICS

| Metric | Measured Value | Evidence Command | Classification |
|---|---|---|---|
| **Alembic Migrations** | 34 version files | `Get-ChildItem apps/api/alembic/versions` | `[VERIFIED]` |
| **Alembic Migration Head** | `0041_master_build_14_intelligence` | `python -m alembic heads` | `[VERIFIED]` |
| **Backend Modules** | 72 module directories | `apps/api/app/modules/*` | `[VERIFIED]` |
| **Backend Test Files** | 192 files (`test_*.py`) | `apps/api/tests/test_*.py` | `[VERIFIED]` |
| **Total Test Items** | 2,756 collected tests | `pytest --collect-only` | `[VERIFIED]` |
| **OpenAPI Unique Endpoints** | 819 paths | `app.openapi()['paths']` | `[VERIFIED]` |
| **OpenAPI Operations** | 913 path + method operations | `app.openapi()` enumeration | `[VERIFIED]` |
| **Frontend Route Files** | 56 (`page.tsx`) | `apps/web/src/app/**/page.tsx` | `[VERIFIED]` |
| **Frontend Built Routes** | 57 routes | `next build` static page generation | `[VERIFIED]` |
| **Frontend Test Specs** | 35 suites, 111 specs | `node run-specs.mjs` | `[VERIFIED]` |

---

## 4. CURRENT BUILD & VERIFICATION RESULTS

| Pipeline Stage | Result | Notes / Details | Classification |
|---|---|---|---|
| **Frontend Typecheck** | `PASS` | `tsc --noEmit` 0 errors | `[VERIFIED]` |
| **Frontend Specs** | `PASS` | 35 suites, 111 specs, 111 passed, 0 failed | `[VERIFIED]` |
| **Frontend Next.js Build** | `PASS` | 57 static/dynamic pages compiled in 8.5s | `[VERIFIED]` |
| **Backend Test Collection** | `PASS` | 2,756 tests collected in 8.86s | `[VERIFIED]` |
| **Backend Auth Suite** | `PARTIAL` | `test_auth.py`: 7/7 passed. `test_authentication_matrix.py`: 14/18 passed, 4 failed due to in-memory code-replay bug in `oauth_state.py` | `[VERIFIED]` |
| **Docker Build** | `SKIPPED` | Docker desktop daemon stopped | `[VERIFIED]` |

---

## 5. DEPENDENCY INVENTORY

### Backend Primary Dependencies (`apps/api/requirements.txt` / `pyproject.toml`)
- `fastapi` 0.139.2 (in pyproject: `^0.115.0`)
- `uvicorn` 0.51.0
- `sqlalchemy` 2.0.51
- `asyncpg` 0.31.0
- `alembic` 1.18.5
- `pydantic` 2.13.4
- `pydantic-settings` 2.14.2
- `pyjwt` 2.13.0
- `redis` 8.0.1
- `celery` 5.6.3
- `google-generativeai` 0.8.6 (DEPRECATED SDK)
- `google-genai` 2.24.0 (NEW SDK installed)
- `razorpay` 2.0.1
- `pytesseract` 0.3.13
- `pillow` 12.3.0
- `httpx` 0.28.1

### Frontend Primary Dependencies (`apps/web/package.json`)
- `next` 15.5.24
- `react` 19.0.0
- `react-dom` 19.0.0
- `tailwindcss` 3.4.15
- `typescript` 5.6.3
- `lucide-react` 0.454.0
- `framer-motion` 12.42.2
- `recharts` 2.13.3
- `gsap` 3.15.0

---

## 6. EXTERNAL PROVIDERS & LIVE STATE

| Provider | Purpose | Declared Status | Runtime Reality | Classification |
|---|---|---|---|---|
| **Google Gemini** | LLM inference, embedding | Active | Both `google-generativeai` and `google-genai` present; uses alias resolution to `gemini-3.8-flash` | `[VERIFIED]` |
| **Google OAuth** | Identity & SSO | Active | Legacy caller-controlled fallback quarantined; state validation in progress | `[VERIFIED]` |
| **Razorpay** | Subscriptions & payments | Configured | `render.yaml` sets `RAZORPAY_ENVIRONMENT: test`. Live payments not enabled. | `[VERIFIED]` |
| **WhatsApp Cloud API** | Omnichannel messaging | Marketed | `POLICY_DISABLED_CHANNELS = frozenset({Channel.WHATSAPP})` in code. Mismatch with marketing claims. | `[VERIFIED]` |
| **Brevo / SMTP** | Email notifications | Active | SMTP email adapter registered as default email channel | `[VERIFIED]` |
| **PostgreSQL / pgvector** | Primary DB & Vector store | Active | Async SQLAlchemy + asyncpg; Alembic head `0041` | `[VERIFIED]` |
| **Upstash Redis** | Cache & Rate Limiting | Active | Sync/async client; fallback memory store exists in dev/test | `[VERIFIED]` |
| **Object Storage** | Uploads & attachments | Ephemeral | Default local filesystem (`storage_data`). Data loss risk across redeploys. | `[VERIFIED]` |

---

## 7. CRITICAL SECURITY WARNINGS & PRODUCTION CONFIGURATION GAPS

1. **P0.1 — Auth Mock Identity & In-Memory Replay:** Quarantined in working tree, but unit test logic for in-memory code store needs one bug fix to achieve 100% pass rate.
2. **P0.2 — PropertyListing Tenancy:** `PropertyListing.organization_id` was identified as a computed alias to `broker_id` in prior audits. Needs database-level verification and true foreign key constraint.
3. **P0.3 — Local Filesystem Storage:** Files stored on local disk under `storage_data/`, which is erased upon Render container redeployment.
4. **P0.4 — Billing Split Authority:** Dual price definition between static constants and canonical database catalog. Razorpay set to `test` environment in `render.yaml`.
5. **P0.5 — WhatsApp Truth:** WhatsApp is marketed as active on the landing page, but policy-disabled in `app/modules/communication/channels/enums.py`.
6. **P0.6 — CI Failure Enforcement:** Previous workflows used `|| true` on security scanners and health checks. Hardened workflows currently uncommitted.
7. **P0.7 — Onboarding Redirection Failure:** Legacy flow caught activation failures and redirected to `/dashboard` instead of showing error state.
8. **CSP `unsafe-inline`:** Present in `SecurityHeadersMiddleware`. Needs nonce or strict CSP evaluation.
