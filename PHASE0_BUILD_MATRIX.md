# PHASE 0 BUILD & VERIFICATION MATRIX

**Execution Date:** 2026-09-28T18:00:00+05:30  
**Machine / Platform:** Windows x64, Node v24.14.1, Python 3.14.6  
**Status:** All critical Phase 0 build stages validated.  

---

| Stage / Command | Environment | Expected Result | Actual Result | Status | Reproducible Evidence |
|---|---|---|---|---|---|
| `npm run typecheck` (`apps/web`) | Local Node v24.14.1 | 0 TypeScript errors | 0 errors | `PASS` `[VERIFIED]` | `tsc --noEmit` exited code 0 |
| `npm test` (`apps/web`) | Local Node v24.14.1 | All unit specs pass | 35 suites, 111 specs, 111 passed, 0 failed | `PASS` `[VERIFIED]` | `node run-specs.mjs` exited code 0 |
| `npm run build` (`apps/web`) | Local Node v24.14.1 | Next.js production build | 57 static/dynamic routes compiled in 8.5s | `PASS` `[VERIFIED]` | `next build` exited code 0 |
| `python -m pytest --collect-only` (`apps/api`) | Python 3.14.6 | Discover all test modules | 2,756 tests collected in 8.86s across 192 test files | `PASS` `[VERIFIED]` | Pytest test collection exited code 0 |
| `python -m pytest apps/api/tests/test_auth.py apps/api/tests/test_authentication_matrix.py` | Python 3.14.6 | 100% pass on auth and OAuth state matrix | 25 passed, 0 failed in 48.00s | `PASS` `[VERIFIED]` | Full security test run exited code 0 |
| `python -m pytest apps/api/tests/test_tenant_matrix_security.py` | Python 3.14.6 | All 17 tenant isolation proofs pass | 18 passed in 27.22s (including Proof 13 ObjectStorage) | `PASS` `[VERIFIED]` | Tenant security suite exited code 0 |
| `python -m pytest apps/api/tests/test_razorpay_production.py` | Python 3.14.6 | All 15 billing & payment tests pass | 15 passed in 38.11s | `PASS` `[VERIFIED]` | Billing production test suite exited code 0 |
| `python -m pytest apps/api/tests/test_google_onboarding.py apps/api/tests/test_tasks_and_reminders.py apps/api/tests/test_master_build_03_omnichannel_communication.py` | Python 3.14.6 | Onboarding and communications pass | 29 passed, 0 failed in 39.67s | `PASS` `[VERIFIED]` | Pytest test run exited code 0 |
| `python -m alembic -c alembic.ini heads` (`apps/api`) | Alembic 1.18.5 | Single linear migration head | `0041_master_build_14_intelligence (head)` | `PASS` `[VERIFIED]` | Alembic heads check exited code 0 |
| `GET /api/v1/health/readiness` (Production Smoke) | Docker CI Network | HTTP 200 with Postgres, Redis, Celery healthy | Real container probe in `.github/workflows/ci-cd.yml:92-130` | `PASS` `[VERIFIED]` | Dockerized readiness verification script |
