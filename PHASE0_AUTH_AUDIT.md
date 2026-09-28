# PHASE 0 AUTHENTICATION & OAUTH HARDENING AUDIT (P0.1)

**Audit Target:** `apps/api/app/modules/auth/`  
**Execution Date:** 2026-09-28T17:53:00+05:30  
**Status:** `REMEDIATED & VERIFIED` `[VERIFIED]`  

---

## 1. VULNERABILITY VERIFICATION & BEFORE/AFTER

### Finding AUTH-01: Caller-Controlled OAuth Identity
- **Pre-Hardening Reality:** `apps/api/app/modules/auth/service.py` accepted `req.email` or `req.name` or `req.code.startswith("test_code_")` directly from the client and minted a JWT session for that email address without contacting Google OAuth servers. An attacker could mint a session for any registered broker account in the system simply by submitting their email address.
- **Remediation:**
  1. Removed `email` and `name` from `GoogleExchangeRequest` in `schemas.py`.
  2. Implemented strict rejection in `service.py`:
     ```python
     if getattr(req, "email", None) or getattr(req, "name", None) or req.code.startswith("test_code_"):
         raise HTTPException(
             status_code=status.HTTP_400_BAD_REQUEST,
             detail="Caller-supplied OAuth identity is not accepted. Use the verified Google OAuth flow."
         )
     ```
  3. Quarantined mock authentication to an explicitly isolated, environment-gated test router (`/api/v1/auth/testing/mock-login`) that is completely disabled in production/staging environments.
- **Verification Evidence:**
  - `apps/api/tests/test_authentication_matrix.py::test_9b_caller_supplied_identity_rejected` -> `PASSED`
  - `apps/api/tests/test_authentication_matrix.py::test_4_google_existing_onboarded_user` -> `PASSED`
  - `apps/api/tests/test_authentication_matrix.py::test_10_existing_email_signs_in_with_google_no_duplicate` -> `PASSED`

---

## 2. OAUTH CSRF STATE SECURITY & SESSION BINDING

### Finding AUTH-02 / AUTH-03: State CSRF & Cross-Worker Replay
- **Pre-Hardening Reality:** OAuth state was unverified or accepted arbitrary caller-supplied strings. Used authorization codes were stored in a process-local `_used_oauth_codes: set[str] = set()`, which failed to protect against code replay across multiple Uvicorn workers (Render runs 4 workers).
- **Remediation:**
  1. Created `apps/api/app/common/auth/oauth_state.py` providing distributed, Redis-backed state management:
     - **Cryptographically Random:** Generated via `secrets.token_urlsafe(32)`.
     - **Session-Bound:** Fingerprinted using HMAC-SHA256 with server `SECRET_KEY` and client session ID:
       ```python
       def _session_digest(session_id: str) -> str:
           secret = (settings.SECRET_KEY or "wefylabs-oauth-state").encode("utf-8")
           return hmac.new(secret, session_id.encode("utf-8"), hashlib.sha256).hexdigest()
       ```
     - **Atomic Consumption:** Redis pipeline `GET` + `DELETE` ensures that concurrent validation by two workers cannot both succeed:
       ```python
       pipe = redis.pipeline()
       pipe.get(key)
       pipe.delete(key)
       result = pipe.execute()
       ```
     - **Tombstone Replay Tracking:** Consumed states write a tombstone key with TTL to distinguish between missing and replayed state.
     - **Distributed Code Replay:** `consume_authorization_code` uses Redis `SET key 1 NX EX 900` ensuring authorization codes are single-use across all workers.
     - **Fail-Closed Production Safety:** Production environments fail closed if Redis is unreachable; test environments use a bounded in-memory store.
- **Verification Evidence:**
  - `apps/api/tests/test_authentication_matrix.py::test_9_google_callback_replay_rejected` -> `PASSED`
  - `apps/api/tests/test_authentication_matrix.py::test_9c_oauth_state_full_security_matrix` -> `PASSED`
  - Valid state + session -> PASS
  - Wrong session -> FAIL (`OAuthStateSessionMismatch`)
  - Missing state -> FAIL (`OAuthStateMissing`)
  - Expired state -> FAIL (`OAuthStateExpired`)
  - Replayed state -> FAIL (`OAuthStateReplayed`)
  - Replayed authorization code -> FAIL (`OAuthStateReplayed`)

---

## 3. SESSION TRANSPORT & CLIENT HARDENING

### Session Architecture
- **Web App (`apps/web`):**
  - Updated `apps/web/src/app/auth/callback/page.tsx` to read server-issued `state` parameter from sessionStorage and forward both `code` and `state` to `/api/v1/auth/google/exchange`.
  - Added session ID cookie generation in callback flow.
  - Sanitized query parameter extraction and added clear error states for state mismatch or expired OAuth sessions.
- **Security Headers Middleware (`apps/api/app/infrastructure/security/security_headers.py`):**
  - Enforces `Strict-Transport-Security` (HSTS).
  - Enforces `X-Content-Type-Options: nosniff`.
  - Enforces `X-Frame-Options: DENY`.
  - Enforces `Referrer-Policy: strict-origin-when-cross-origin`.

---

## 4. TEST SUITE REPRODUCTION RESULTS

```text
======================= 25 passed, 5 warnings in 48.00s =======================
apps/api/tests/test_auth.py: 7/7 PASSED
apps/api/tests/test_authentication_matrix.py: 18/18 PASSED
```
