# WefyLabs Production Configuration Guide

**Document Version**: 1.0  
**Status**: PRODUCTION ENFORCEMENT GUIDE  
**Mandate**: Production configurations must be typed, validated, environment-driven, secret-safe, and fail-fast. No test mode settings (e.g. Razorpay test keys, mock providers, synthetic fallbacks) are permitted in production runtimes.

---

## 1. Production Health Probes (Prompt §33)

Container orchestration platforms (Docker Compose, Kubernetes, ECS) must probe the following canonical health routes:

| Route | Purpose | Probe Type | SLA / Timeout | Expected Response |
| :--- | :--- | :--- | :--- | :--- |
| `GET /health/live` | Process liveness probe | Kubernetes Liveness | 2000ms | HTTP 200 `{"status": "alive"}` |
| `GET /health/ready` | Critical dependency check (DB + Redis) | Kubernetes Readiness | 3000ms | HTTP 200 `{"status": "ready"}` or HTTP 503 if DB/Redis down |
| `GET /health/deep` | Internal diagnostics, migration head, outbox queue metrics | Operator Diagnostics | 5000ms | HTTP 200 with component latencies & metrics |
| `GET /health/capabilities` | Public feature availability flags | Frontend App Boot | 2000ms | HTTP 200 (booleans indicating configured providers) |

---

## 2. Core Environment Variables Specification

### 2.1 Database & Cache
```ini
# PostgreSQL with asyncpg driver (REQUIRED in production)
DATABASE_URL=postgresql+asyncpg://app_user:STRONG_PASSWORD@postgres.internal:5432/wefylabs_db

# Redis connection for Celery brokers and caching (REQUIRED)
REDIS_URL=redis://:REDIS_STRONG_PASSWORD@redis.internal:6379/0

# Database Pool Settings
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=10
DB_POOL_TIMEOUT=30
```

### 2.2 Security & Authentication
```ini
# Production Environment Mode
ENV=production
DEBUG=False

# Cryptographic Secrets (Minimum 32 characters)
SECRET_KEY=REPLACE_WITH_HIGH_ENTROPY_RANDOM_SECRET_HEX_64_CHARS
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=30

# CORS Whitelist (Never use '*' in production)
CORS_ORIGINS=["https://app.wefylabs.com","https://api.wefylabs.com"]
```

### 2.3 AI Subsystem (Google GenAI SDK)
```ini
# Google Gemini API Key (Required for AI Gateway)
GEMINI_API_KEY=AIzaSy...REAL_PRODUCTION_KEY

# Canonical Model Selection
GEMINI_MODEL=gemini-2.5-flash
GEMINI_REASONING_MODEL=gemini-2.5-pro

# Gateway Limits
AI_MONTHLY_TOKEN_BUDGET=50000000
```

### 2.4 Object Storage Service
```ini
# Storage Backend: local | s3
STORAGE_BACKEND=local
STORAGE_LOCAL_DIR=/var/data/wefylabs/storage
STORAGE_SIGNING_SECRET=REPLACE_WITH_STORAGE_SIGNING_SECRET_KEY

# S3 Configuration (when STORAGE_BACKEND=s3)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=ap-south-1
S3_BUCKET_NAME=wefylabs-customer-documents
```

### 2.5 External Communication Providers
```ini
# WhatsApp Cloud / 360dialog (Must NOT be 'd360_key_placeholder')
WHATSAPP_PROVIDER=360dialog
WHATSAPP_API_KEY=REAL_PRODUCTION_KEY
WHATSAPP_PHONE_NUMBER_ID=REAL_PHONE_NUMBER_ID

# SMTP Mail Dispatch
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=REAL_SENDGRID_KEY
SMTP_FROM_EMAIL=notifications@wefylabs.com
```

### 2.6 Billing Provider (Razorpay)
```ini
# Production Razorpay Keys (MUST NOT begin with 'rzp_test_')
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

---

## 3. Production Deployment Gates

The build pipeline enforces the following validation checks prior to deploying to staging or production:

1. **Test Mode Prohibition**:
   - If `ENV=production` and `RAZORPAY_KEY_ID` begins with `rzp_test_`, deployment halts.
   - If `GEMINI_API_KEY` or `WHATSAPP_API_KEY` contains `placeholder`, startup logs critical warnings and degrades gracefully.
2. **Schema Verification**:
   - Alembic runs `alembic upgrade head` before process start.
   - Database startup probe checks that `alembic_version` matches the repository head (`0035_canonical_tenant_foundation`).
3. **Frontend Typecheck & Build**:
   - `npm run typecheck` and `npm run build` must exit with code 0 before container packaging.
