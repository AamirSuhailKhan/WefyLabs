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
# =============================================================================
set -euo pipefail

echo "[BeetleLabs] Starting production deployment..."
echo "[BeetleLabs] ENV=${ENV:-unset}"

# ─── Validate critical env vars before proceeding ─────────────────────────────
REQUIRED_VARS=("DATABASE_URL" "SECRET_KEY" "SUPABASE_JWT_SECRET")
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var:-}" ]; then
        echo "[ERROR] Required environment variable '${var}' is not set. Aborting."
        exit 1
    fi
done

# ─── Run Alembic migrations ───────────────────────────────────────────────────
echo "[BeetleLabs] Running Alembic migrations..."
python -m alembic upgrade head

if [ $? -ne 0 ]; then
    echo "[ERROR] Alembic migration failed. Aborting startup to prevent schema mismatch."
    exit 1
fi

echo "[BeetleLabs] Migrations complete. Starting API server..."

# ─── Start Uvicorn ────────────────────────────────────────────────────────────
# 4 workers for production (tune based on CPU count: 2 * CPU + 1)
exec uvicorn app.main:app \
    --host 0.0.0.0 \
    --port "${PORT:-8000}" \
    --workers "${WORKERS:-4}" \
    --loop uvloop \
    --access-log \
    --log-level "${LOG_LEVEL:-info}" \
    --proxy-headers \
    --forwarded-allow-ips "*"
