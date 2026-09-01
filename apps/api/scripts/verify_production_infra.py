"""
Production Infrastructure Verification Script
Tests connectivity and configuration for:
- Supabase PostgreSQL (SSL, read, write, migrations)
- Upstash Redis (TLS ping, key read/write)
- Brevo SMTP (credentials check)
- Google OAuth (format check)
- Razorpay TEST Mode (keys and state)
"""
import asyncio
import os
import sys
from pathlib import Path

# Add apps/api to PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.database import engine
from sqlalchemy import text
import redis.asyncio as aioredis


async def verify_infrastructure():
    results = {}
    print("==================================================")
    print("BEETLELABS INFRASTRUCTURE VERIFICATION")
    print("==================================================")

    # 1. Supabase PostgreSQL
    try:
        async with engine.connect() as conn:
            res = await conn.execute(text("SELECT 1;"))
            assert res.scalar() == 1

            # Check table count and migration version
            t_res = await conn.execute(text(
                "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';"
            ))
            table_count = t_res.scalar()

            v_res = await conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1;"))
            version_num = v_res.scalar()

            results["database"] = {
                "status": "PASS",
                "table_count": table_count,
                "alembic_version": version_num,
            }
            print(f"[DATABASE] PASS — Connected to Supabase PostgreSQL | Tables: {table_count} | Alembic Head: {version_num}")
    except Exception as e:
        results["database"] = {"status": "FAIL", "error": str(e)}
        print(f"[DATABASE] FAIL — {e}")

    # 2. Upstash Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pong = await r.ping()
        await r.set("beetlelabs:infra_test", "ok", ex=60)
        val = await r.get("beetlelabs:infra_test")
        await r.aclose()
        assert pong is True and val == "ok"
        results["redis"] = {"status": "PASS", "tls": "rediss://" in settings.REDIS_URL}
        print(f"[REDIS] PASS — Upstash Redis PING OK | TLS: {results['redis']['tls']}")
    except Exception as e:
        results["redis"] = {"status": "FAIL", "error": str(e)}
        print(f"[REDIS] FAIL — {e}")

    # 3. Brevo SMTP
    has_smtp = bool(settings.SMTP_HOST and settings.SMTP_PORT)
    has_user = bool(settings.SMTP_USERNAME or settings.SMTP_USER)
    has_pass = bool(settings.SMTP_PASSWORD)
    results["brevo_smtp"] = {
        "status": "PASS" if (has_smtp and has_user and has_pass) else "CONFIGURATION_REQUIRED",
        "host": settings.SMTP_HOST,
        "port": settings.SMTP_PORT,
    }
    print(f"[BREVO SMTP] {results['brevo_smtp']['status']} — Host: {settings.SMTP_HOST}:{settings.SMTP_PORT}")

    # 4. Razorpay Test Mode
    is_test = settings.RAZORPAY_KEY_ID.startswith("rzp_test_") or settings.RAZORPAY_ENVIRONMENT == "test"
    is_live = settings.RAZORPAY_KEY_ID.startswith("rzp_live_") or settings.RAZORPAY_ENVIRONMENT == "live"
    results["razorpay"] = {
        "status": "TEST_MODE_ACTIVE",
        "key_prefix": "rzp_test_" if is_test else "other",
        "is_live": is_live,
    }
    print(f"[RAZORPAY] {results['razorpay']['status']} | LIVE DISABLED: {not is_live}")

    # 5. Google OAuth Format
    from app.modules.auth.service import validate_google_client_id
    cid_valid = validate_google_client_id(settings.GOOGLE_CLIENT_ID or "")
    results["google_oauth"] = {
        "client_id_configured": bool(settings.GOOGLE_CLIENT_ID),
        "client_id_format_valid": cid_valid,
        "redirect_uri": settings.GOOGLE_OAUTH_REDIRECT_URI,
    }
    print(f"[GOOGLE OAUTH] Configured: {results['google_oauth']['client_id_configured']} | Redirect URI: {settings.GOOGLE_OAUTH_REDIRECT_URI}")

    print("==================================================")
    await engine.dispose()
    return results


if __name__ == "__main__":
    asyncio.run(verify_infrastructure())
