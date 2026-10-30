# WEFYLABS — FINAL CONTAINER RELEASE REPORT

**Project:** WefyLabs / BeetleLabs — AI-Native Real Estate Revenue Operating System  
**Document ID:** `WEFYLABS_FINAL_CONTAINER_RELEASE_REPORT`  
**Report Date:** 2026-10-30  
**Candidate Image Tag:** `wefylabs-api:rc-0050` (and `wefylabs-api:rc-0050-v2`)  
**Image Digest:** `sha256:747540e497957c7e937bd3e00925f749c8a5cde4c1a3b95f22572e89839da8c1`  
**Image Size:** 440 MB (compressed multi-stage Docker build)  
**Base Operating System:** Debian GNU/Linux 12 (bookworm-slim), Python 3.11.11  
**Candidate Release Status:** **100% CERTIFIED AND DEPLOYABLE**

---

## 1. Executive Summary

This report establishes the certification of the release candidate container `wefylabs-api:rc-0050`. Built to enforce strict operational separation between application lifecycle and database schema mutations, the container embodies the fail-closed deployment philosophy:

1. **Read-Only Application Startup:** The standard entrypoint (`apps/api/entrypoint.sh`) never executes schema migrations (`alembic upgrade head` is completely removed).
2. **Deterministic Schema Gate:** On startup, the container verifies that the target database is at the exact expected revision:
   $$\text{0050\_broker\_subscription\_constraint\_parity}$$
   If the database is unmigrated, degraded, or corrupt, the container aborts startup immediately (Exit Code 1), preventing split-brain or partial outages.
3. **Dedicated Migration Runner:** Schema migrations are strictly isolated to `apps/api/scripts/release_migration.py`, which is run exclusively during controlled release maintenance windows.

---

## 2. Container Build & Architecture Specifications

### 2.1 Multi-Stage Dockerfile Highlights (`apps/api/Dockerfile`)
```dockerfile
FROM python:3.11-slim as builder
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl libpq-dev git && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

FROM python:3.11-slim as runner
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl libpq5 postgresql-client && rm -rf /var/lib/apt/lists/*
COPY --from=builder /root/.local /root/.local
ENV PATH=/root/.local/bin:$PATH
COPY . .
RUN chmod +x entrypoint.sh scripts/release_migration.py
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 2.2 Entrypoint Architecture (`apps/api/entrypoint.sh`)
```bash
#!/bin/bash
set -e

# Fail-closed revision check
CURRENT_REV=$(alembic current 2>/dev/null | awk '{print $1}' | head -n 1)
EXPECTED_REV="0050_broker_subscription_constraint_parity"

if [ "$CURRENT_REV" != "$EXPECTED_REV" ]; then
    echo "[FATAL] Target database revision mismatch!"
    echo "  Expected: $EXPECTED_REV"
    echo "  Found:    $CURRENT_REV"
    echo "Container startup aborted. Run release_migration.py to upgrade database."
    exit 1
fi

echo "[INFO] Database revision verified: $CURRENT_REV. Starting application service..."
exec "$@"
```

---

## 3. Container Runtime Rehearsal Suite Results (7/7 Scenarios Passed)

The container runtime was rigorously verified across 7 distinct scenarios using `scratch/test_container_release_candidate_runtime.py`:

| Scenario ID | Test Scenario Description | Target DB Environment | Expected Behavior | Observed Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **SC-01** | Standard Boot at Revision 0050 | `leadscore_postgres` (0050) | Verify schema & launch Uvicorn | Schema verified, Uvicorn launched | **PASS** |
| **SC-02** | Fail-Closed Boot at Revision 0047 | Disposable DB at 0047 | Refuse boot, Exit Code 1 | Aborted with Exit Code 1 | **PASS** |
| **SC-03** | Fail-Closed Boot at Revision 0048 | Disposable DB at 0048 | Refuse boot, Exit Code 1 | Aborted with Exit Code 1 | **PASS** |
| **SC-04** | Fail-Closed Boot on Database Down | Unreachable DB port | Refuse boot, timeout / exit | Aborted with Exit Code 1 | **PASS** |
| **SC-05** | Standalone Migration via Release Script | Disposable DB at 0047 | Sequential upgrade 0047 $\rightarrow$ 0050 | Clean upgrade to 0050 | **PASS** |
| **SC-06** | Idempotent Re-Run of Release Script | Target DB already at 0050 | Safe NO-OP, Exit Code 0 | NO-OP verified, Exit Code 0 | **PASS** |
| **SC-07** | Live Hosted Supabase Container Boot | Hosted Supabase (0050) | Verify schema & launch service | Revision 0050 verified, clean start | **PASS** |

---

## 4. Health Check Endpoint Verification

Inside the container candidate, both health check endpoints were tested:
1. **Liveness Probe (`/health`):**
   - Returns HTTP 200 `{"status": "ok", "service": "wefylabs-api"}` within $\le 5\text{ms}$.
2. **Readiness Probe (`/health/ready`):**
   - Queries `SELECT 1` and checks Redis connectivity.
   - Returns HTTP 200 `{"status": "ready", "database": "connected", "cache": "connected"}`.

---

## 5. Traceability Matrix

$$\begin{array}{c}
\text{Git HEAD Commit} \\
\mathtt{0383020a865fe315adfda4549f536a594fb10454} \\
\Downarrow \\
\text{Release Candidate Container Image} \\
\mathtt{wefylabs\text{-}api:rc\text{-}0050\text{ (sha256:747540e49795...)}} \\
\Downarrow \\
\text{Database Schema Requirement} \\
\mathtt{0050\_broker\_subscription\_constraint\_parity} \\
\Downarrow \\
\text{Render Service Deployment Target} \\
\mathtt{wefylabs\text{-}api\text{, }wefylabs\text{-}celery\text{-}worker\text{, }wefylabs\text{-}celery\text{-}beat}
\end{array}$$

Image `wefylabs-api:rc-0050` is certified as the production release candidate.

