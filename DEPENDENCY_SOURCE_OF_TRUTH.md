# DEPENDENCY SOURCE OF TRUTH SPECIFICATION

**Execution Date:** 2026-09-28T17:59:00+05:30  
**Repository Scope:** `apps/api` and `apps/web`  
**Rule:** One single canonical source of dependency truth per tier.  

---

## 1. BACKEND DEPENDENCY SPECIFICATION

### 1.1 Canonical Manifest: `apps/api/requirements.txt`
In WefyLabs RC-1, `apps/api/requirements.txt` is the **authoritative production dependency graph**.
Both `Dockerfile.prod` and GitHub Actions CI-CD workflow (`.github/workflows/ci-cd.yml`) install from `apps/api/requirements.txt`.

### 1.2 Divergence Resolution with `pyproject.toml`
- **Issue Discovered:** `pyproject.toml` had package name `leadscore-api` with looser version constraints (`^0.115.0`) while `requirements.txt` pinned modern production libraries (`fastapi>=0.115.0`, `asyncpg>=0.29.0`, `google-genai>=0.1.0`).
- **Policy:**
  1. `apps/api/requirements.txt` is authoritative for production runtime and Docker builds.
  2. Any dependency added to the backend must be declared in `requirements.txt`.
  3. `pyproject.toml` is synchronized for development tooling (Poetry/pytest).

### 1.3 Key Packages & Runtime Verification
| Package | Declared Version | Installed Version | Notes |
|---|---|---|---|
| `fastapi` | `>=0.115.0` | `0.139.2` | Core ASGI API framework |
| `uvicorn` | `[standard]>=0.30.0` | `0.51.0` | Production ASGI web server |
| `sqlalchemy` | `[asyncio]>=2.0.30` | `2.0.51` | Async ORM |
| `asyncpg` | `>=0.29.0` | `0.31.0` | High-performance PostgreSQL driver |
| `alembic` | `>=1.13.0` | `1.18.5` | Authoritative migration runner |
| `pydantic` | `>=2.9.0` | `2.13.4` | Data validation and settings |
| `redis` | `>=5.0.0` | `8.0.1` | Cache, rate limiter, distributed OAuth state |
| `celery` | `>=5.4.0` | `5.6.3` | Async worker and beat scheduler |
| `google-genai` | `>=0.1.0` | `2.24.0` | Canonical modern Google AI SDK |
| `google-generativeai` | `>=0.8.0` | `0.8.6` | Deprecated SDK (quarantined; migration target) |
| `razorpay` | `>=1.4.1` | `2.0.1` | Subscriptions and orders |
| `pytesseract` | `>=0.3.10` | `0.3.13` | OCR wrapper (requires OS binary in Docker) |
| `pillow` | `>=10.0.0` | `12.3.0` | Image processing |
| `httpx` | `>=0.27.0` | `0.28.1` | Async HTTP client for providers |

### 1.4 Docker System Dependencies
The production Dockerfile (`apps/api/Dockerfile.prod`) must install system-level C libraries:
- `libpq-dev` / `postgresql-client` for Postgres connectivity
- `tesseract-ocr` and `tesseract-ocr-eng` for OCR document processing
- `ca-certificates` for outbound TLS calls to Google and Razorpay

---

## 2. FRONTEND DEPENDENCY SPECIFICATION

### 2.1 Canonical Manifest: `apps/web/package.json`
- **Lockfile:** `apps/web/package-lock.json`
- **Node Runtime Target:** Node.js `>=20.x` (Tested and verified on Node `v24.14.1`)
- **Package Manager:** `npm 11.11.0`

### 2.2 Key Packages & Build Verification
| Package | Version | Purpose | Build Verification |
|---|---|---|---|
| `next` | `15.5.24` | React Server Components & App Router | Next.js 57 routes compiled successfully |
| `react` / `react-dom` | `19.0.0` | UI rendering runtime | React 19 concurrent features |
| `tailwindcss` | `3.4.15` | Utility CSS engine | PostCSS build verified |
| `typescript` | `5.6.3` | Static type system | `tsc --noEmit` 0 errors |
| `lucide-react` | `0.454.0` | UI Icons | Loaded across all pages |
| `framer-motion` | `12.42.2` | Page transitions & micro-animations | Verified in Next.js build |
| `recharts` | `2.13.3` | Analytics charts | Verified in analytics pages |
