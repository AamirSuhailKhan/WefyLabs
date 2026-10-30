# WEFYLABS AUTONOMOUS REVENUE OS — PHASE 4 RELEASE CANDIDATE PROVENANCE

**Audit Date**: 2026-10-28T13:25:00+05:30  
**Target Branch**: `level-3`  
**Current HEAD Commit**: `0383020a865fe315adfda4549f536a594fb10454`  
**Auditor**: Principal Release Engineer & Infrastructure Architect  
**Evaluation Standard**: Phase E — Source-to-Image and Runtime Consistency

---

## 1. Executive Summary

This report establishes the verified provenance linking the local Git working tree, dependency lockfiles, Docker build contexts, built container images, and running processes for the WefyLabs release candidate.

Byte-for-byte SHA-256 comparisons prove that core modified source files on the host are identical to the code executing inside the Docker containers. The persistent database volume `crmrealstate_postgres_data` is strictly isolated from application image lifecycles, guaranteeing that code rebuilds or container restarts cannot reset customer database records.

---

## 2. Source-to-Image Provenance Audit

### 2.1 Git Repository Baseline
- **Branch**: `level-3`
- **HEAD Commit**: `0383020a865fe315adfda4549f536a594fb10454`
- **Working Tree**: Contains uncommitted remediation edits preserved for operator review per safety constraints.
- **Diff Hygiene**: `git diff --check` exited code `0` (clean line endings, zero trailing whitespace errors).

### 2.2 Docker Image Identifiers & Creation Timestamps
- **`leadscore_api`**:
  - Image ID: `sha256:aee327ea299f216ee664ca4c8400a91a0c487c7ef6109ccba56630d742f8f654`
  - Container Creation Time: `2026-10-27T08:48:51.394305241Z`
  - Process Command: `uvicorn app.main:app --host 0.0.0.0 --port 8000`
  - Uptime: > 23 hours continuous
- **`leadscore_celery_worker`**:
  - Image ID: `sha256:187442fb1546698d908934d30283c9ac842af292dada203c2c52a56ba5e38b99`
  - Container Creation Time: `2026-10-27T08:48:51.393685222Z`
  - Process Command: `celery -A app.celery_app.celery_app worker --loglevel=info`
  - Uptime: > 23 hours continuous
- **`leadscore_celery_beat`**:
  - Image ID: `sha256:187442fb1546698d908934d30283c9ac842af292dada203c2c52a56ba5e38b99`
  - Process Command: `celery -A app.celery_app.celery_app beat --loglevel=info`
  - Uptime: > 23 hours continuous

---

## 3. Byte-Level Source Code Parity

Because `docker-compose.yml` does not use bind mounts for `/app` in `api` and `celery_worker`, source files were inspected directly across the host filesystem and container filesystem using cryptographic hashing:

| Source File | Host SHA-256 Checksum | Container SHA-256 Checksum | Parity Status |
|---|---|---|---|
| `app/core/async_runner.py` | `71BCA589813144D57F5D...` | `71bca589813144d57f5d...` | **100% BYTE MATCH** |
| `alembic/versions/0048_schema_reconciliation_parity.py` | `FF91F5EFCA5A6743F1ED...` | `ff91f5efca5a6743f1ed...` | **100% BYTE MATCH** |
| `app/tasks/celery_worker.py` | `852A21F9C405E809B460...` | `852a21f9c405e809b460...` | **100% BYTE MATCH** |

The code executing inside the running containers is identical to the current working-tree source files.

---

## 4. Container Test Environment Nuances

During testing and audit verification, the following runtime modifications were observed:
1. **Test Runner Installation**: `pytest`, `pytest-asyncio`, and `aiosqlite` were installed in the container environment. These are declared under `tool.poetry.group.dev.dependencies` in `pyproject.toml`.
2. **Scripts Directory**: The repository folder `apps/api/scripts/` is not included in the standard `Dockerfile` `COPY` instructions. It was provisioned dynamically into `/app/scripts/` for script inspection.
3. **CI/CD Recommendation**: The `Dockerfile` should remain focused on lean production deployments (`uvicorn`). A multi-stage Docker build with a dedicated `testing` target should be added to the build pipeline for future automated releases.

---

## 5. Volume Decoupling & Data Safety Guarantee

1. **Volume Topography**:
   - `postgres_data` is mounted to `crmrealstate_postgres_data` on the host.
   - `redis_data` is mounted to `crmrealstate_redis_data` on the host.
2. **Rebuild Safety**:
   - Rebuilding application images (`docker compose build api celery_worker celery_beat`) modifies only the code layers of the application containers.
   - It does NOT touch, reset, or recreate `leadscore_postgres` or its volume.
3. **Prohibited Destructive Actions**:
   - Running `docker compose down -v` or `docker volume rm` is strictly prohibited, as it destroys the persistent PostgreSQL volume containing live customer data.
