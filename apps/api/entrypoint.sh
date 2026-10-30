#!/bin/bash
# =============================================================================
# BeetleLabs Production Entrypoint
# =============================================================================
# Runs Alembic migrations first, then starts the Uvicorn server.
# This ensures the schema is always up to date before the app handles requests.
#
# Used in:
#   - Kubernetes Pod startup (replace CMD in Dockerfile.prod)
#   - Docker Compose production override
#   - Manual production deployment
#
# Environment variables:
#   TRUSTED_PROXY_IPS  Comma-separated list of trusted reverse-proxy IPs.
#                      Defaults to '127.0.0.1' for safety.
#                      On Render.com, set to '10.0.0.0/8' or Render's documented proxy IP range.
#                      Use '*' only if the platform guarantees all traffic passes through its proxy.
# =============================================================================
set -euo pipefail

echo "[BeetleLabs] Starting production deployment..."
echo "[BeetleLabs] ENV=${ENV:-unset}"

# ─── Validate critical env vars before proceeding ─────────────────────────────
REQUIRED_VARS=("ENV" "DATABASE_URL" "SECRET_KEY" "SUPABASE_JWT_SECRET")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "[ERROR] Required environment variable '${var}' is not set. Aborting."
        exit 1
    fi
done

# ─── Environment Classification & Fail-Closed Gate ─────────────────────────
# In deployed environments, ENV must be explicitly defined and classified.
# Unset, empty, or unrecognized environments must fail closed immediately.
if [ -z "${ENV:-}" ]; then
    echo "[FATAL] Required environment variable 'ENV' is unset or empty."
    echo "Startup aborted to prevent unclassified deployment. Allowed: production, staging, development, local, testing."
    exit 1
fi

CURRENT_ENV_LOWER=$(echo "${ENV}" | tr '[:upper:]' '[:lower:]')
case "${CURRENT_ENV_LOWER}" in
    production|prod|staging)
        IS_DEPLOYED_ENV="true"
        ;;
    development|dev|local|test|testing)
        IS_DEPLOYED_ENV="false"
        ;;
    *)
        echo "[FATAL] Invalid or unrecognized environment classification '${ENV}'."
        echo "Startup aborted. Allowed values: production, staging, development, local, testing."
        exit 1
        ;;
esac

# ─── Schema Integrity & Single Migration Runner Policy ───────────────────────
# In-process migrations on container boot are permanently disabled.
# Ordinary pod auto-scaling, health-check reboots, or rolling restarts must NEVER execute DDL.
# Any attempt to enable startup migrations via RUN_MIGRATIONS_ON_STARTUP=true is rejected.
REQUIRED_ALEMBIC_HEAD="0050_broker_subscription_constraint_parity"

if [ "${RUN_MIGRATIONS_ON_STARTUP:-false}" = "true" ]; then
    echo "[FATAL] RUN_MIGRATIONS_ON_STARTUP=true is rejected."
    echo "In-process migrations on container boot are permanently disabled to prevent concurrent DDL races."
    echo "The dedicated release runner 'python scripts/release_migration.py' must be executed during maintenance windows."
    echo "Aborting startup."
    exit 1
fi

echo "[BeetleLabs] Automatic migration on startup is DISABLED (single-runner policy)."
echo "[BeetleLabs] Checking database schema readiness against required head '${REQUIRED_ALEMBIC_HEAD}'..."

CURRENT_REV=$(python -c "
import sys, os
from urllib.parse import urlparse
from dotenv import load_dotenv
load_dotenv('.env', override=False)
try:
    import asyncpg, asyncio
    url = (os.environ.get('DATABASE_URL') or '').replace('+asyncpg', '')
    async def get_rev():
        conn = await asyncio.wait_for(asyncpg.connect(url), timeout=5.0)
        rev = await conn.fetchval('SELECT version_num FROM alembic_version')
        await conn.close()
        return rev
    rev = asyncio.run(get_rev())
    print(rev or 'unknown')
except Exception as e:
    print('error:' + type(e).__name__)
" 2>/dev/null || echo "check_failed")

echo "[BeetleLabs] Database current revision: ${CURRENT_REV}"

if [ "${IS_DEPLOYED_ENV}" = "true" ]; then
    if [ "${CURRENT_REV}" != "${REQUIRED_ALEMBIC_HEAD}" ]; then
        echo "[FATAL] Deployed database revision mismatch!"
        echo "Environment:                ${ENV}"
        echo "Expected authoritative head: ${REQUIRED_ALEMBIC_HEAD}"
        echo "Found database revision:     ${CURRENT_REV}"
        echo "Automatic migrations are disabled on normal container startup to prevent concurrent DDL."
        echo "An authorized operator must execute 'python scripts/release_migration.py' before starting this release."
        exit 1
    fi
    echo "[BeetleLabs] Schema verified at required head '${REQUIRED_ALEMBIC_HEAD}'. Proceeding with API server startup."
else
    echo "[BeetleLabs] Non-production environment '${ENV}' active. Current revision: ${CURRENT_REV}."
fi

if [ "${DRY_RUN_VALIDATION_ONLY:-false}" = "true" ]; then
    echo "[BeetleLabs] DRY_RUN_VALIDATION_ONLY=true. Pre-flight startup validation passed. Exiting cleanly."
    exit 0
fi

echo "[BeetleLabs] Starting API server..."

# ─── Trusted proxy IPs ───────────────────────────────────────────────────────
# Default to loopback only. Set TRUSTED_PROXY_IPS in platform env vars.
PROXY_IPS="${TRUSTED_PROXY_IPS:-127.0.0.1}"

# ─── Start Uvicorn ────────────────────────────────────────────────────────────
# 4 workers for production (tune based on CPU count: 2 * CPU + 1)
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WORKERS:-4}" \
    --loop auto \
    --access-log \
    --log-level "${LOG_LEVEL:-info}" \
    --proxy-headers \
    --forwarded-allow-ips "${PROXY_IPS}"
