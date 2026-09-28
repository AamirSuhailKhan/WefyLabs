# ENVIRONMENT CONTRACT SPECIFICATION

**Execution Date:** 2026-09-28T18:02:00+05:30  
**Phase:** Phase 0 Production Foundation Hardening  
**Target Environments:** `LOCAL`, `TESTING`, `STAGING`, `PRODUCTION`  

---

## 1. ENVIRONMENT TIERS & POLICIES

| Environment | Mode (`ENV`) | Database Policy | Redis Policy | Payment Policy | Storage Policy | Auth Policy |
|---|---|---|---|---|---|---|
| **LOCAL** | `development` / `dev` | Local Postgres or SQLite | Optional; memory fallback | Razorpay `test` mode | Local directory (`storage_data`) | Google OAuth + local dev login |
| **TESTING** | `testing` / `test` | In-memory SQLite or test Postgres | In-memory bounded store | Mock / test mode signature bypass | Local temp dir / test adapter | Isolated test-only fixture endpoint |
| **STAGING** | `staging` | Managed PostgreSQL with pgvector | Real Redis instance | Razorpay `test` mode (`rzp_test_*`) | S3-compatible cloud bucket | Real Google OAuth + verified state |
| **PRODUCTION** | `production` / `prod` | Dedicated PostgreSQL with pgvector | Dedicated Redis instance | Razorpay `live` mode (`rzp_live_*`) | S3-compatible durable bucket | Real Google OAuth + verified state |

---

## 2. CANONICAL ENVIRONMENT VARIABLES MATRIX

| Variable Name | Type | Required? | Secret? | Default Value | Allowed Values | Enforced In | Description & Validation |
|---|---|---|---|---|---|---|---|
| `ENV` | String | Yes | No | `development` | `development`, `testing`, `staging`, `production` | All | Defines runtime security policy and fail-fast rules |
| `PROJECT_NAME` | String | No | No | `WefyLabs` | String | All | Platform brand and OpenAPI title |
| `API_V1_STR` | String | No | No | `/api/v1` | String | All | API root route prefix |
| `DATABASE_URL` | String | Yes | Yes | None | URI string | All | Async PostgreSQL connection string (`postgresql+asyncpg://...`). SQLite strictly forbidden in production. |
| `REDIS_URL` | String | Yes in Prod | Yes | `redis://localhost:6379/0` | URI string | Prod/Staging | Redis connection for cache, rate limiter, and OAuth replay state |
| `SECRET_KEY` | String | Yes | Yes | None | 32+ char random string | All | Cryptographic key for JWT issuance and OAuth state session HMAC |
| `SUPABASE_JWT_SECRET` | String | Yes in Prod | Yes | None | 32+ char string | Prod/Staging | Supabase JWT secret. Default placeholders rejected in production. |
| `GOOGLE_CLIENT_ID` | String | Yes in Prod | No | None | `*.apps.googleusercontent.com` | Prod/Staging | Google OAuth Client ID for SSO |
| `GOOGLE_CLIENT_SECRET` | String | Yes in Prod | Yes | None | String | Prod/Staging | Google OAuth Client Secret for code exchange |
| `GOOGLE_OAUTH_REDIRECT_URI` | String | Yes in Prod | No | `http://localhost:3000/auth/callback` | Valid URL | All | Authorized Google OAuth callback URL |
| `GEMINI_API_KEY` | String | Yes in Prod | Yes | None | Valid AIzaSy... key | Prod/Staging | Google Gemini API key. Placeholders rejected in production. |
| `GEMINI_MODEL` | String | No | No | `gemini-3.5-flash` | Valid Gemini model | All | Resolved to active production model alias (`gemini-3.8-flash`) |
| `STORAGE_BACKEND` | String | Yes | No | `local` | `local`, `s3`, `test` | All | `local` strictly forbidden in production without `ALLOW_LOCAL_STORAGE_IN_PROD=true` |
| `STORAGE_BUCKET_NAME` | String | Yes if S3 | No | None | Bucket identifier | Prod/Staging | Target durable cloud object storage bucket |
| `STORAGE_ENDPOINT_URL` | String | Optional | No | None | URL string | All | S3-compatible endpoint (Cloudflare R2, MinIO, Backblaze B2) |
| `STORAGE_ACCESS_KEY_ID` | String | Yes if S3 | Yes | None | String | Prod/Staging | S3 access key ID |
| `STORAGE_SECRET_ACCESS_KEY` | String | Yes if S3 | Yes | None | String | Prod/Staging | S3 secret access key |
| `RAZORPAY_ENVIRONMENT` | String | Yes in Prod | No | `test` | `test`, `live` | Prod/Staging | Must be `live` in production. Must be `test` in staging. |
| `RAZORPAY_KEY_ID` | String | Yes in Prod | No | None | `rzp_live_*` in prod, `rzp_test_*` in staging | All | Razorpay Public Key ID |
| `RAZORPAY_KEY_SECRET` | String | Yes in Prod | Yes | None | String | All | Razorpay Secret Key |
| `RAZORPAY_WEBHOOK_SECRET` | String | Yes in Prod | Yes | None | 32+ char string | Prod/Staging | Razorpay Webhook HMAC secret |
| `WHATSAPP_ENABLED` | Boolean | No | No | `False` | `True`, `False` | All | Single kill-switch for WhatsApp outbound dispatch |
| `WHATSAPP_VERIFY_TOKEN` | String | Optional | Yes | None | 32+ char string | All | Meta webhook handshake verification token |
| `CORS_ORIGINS` | List | No | No | `["http://localhost:3000"]` | JSON / CSV list | All | Allowed frontend web origins for CORS headers |
| `ALLOW_LOCAL_STORAGE_IN_PROD` | Boolean | No | No | `False` | `True`, `False` | Prod | Emergency override flag to allow persistent local volume in prod |
