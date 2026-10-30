import os
import sys
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from alembic.config import Config
from alembic import command

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.config import settings

SCHEMA = "test_canonical_p7"

async def reset_schema():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        await conn.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        await conn.execute(text(f"SET search_path TO {SCHEMA}, extensions"))
    await engine.dispose()
    print(f"Clean schema '{SCHEMA}' created.")

def run_alembic():
    ini_path = os.path.join(API_DIR, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(API_DIR, "alembic"))
    os.environ["ALEMBIC_SCHEMA"] = SCHEMA
    print(f"Running alembic upgrade head against {SCHEMA}...")
    command.upgrade(cfg, "head")
    print("Alembic upgrade head completed successfully.")

async def verify_schema():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text(f"SET search_path TO {SCHEMA}, extensions"))
        
        # 1. Check version in alembic_version
        res = await conn.execute(text(f"SELECT version_num FROM {SCHEMA}.alembic_version"))
        version = res.scalar()
        print(f"Recorded alembic_version: {version}")
        assert version == "0047_webhook_event_claims", f"Unexpected version: {version}"

        # 2. Count tables
        res = await conn.execute(text(f"""
            SELECT count(*) FROM information_schema.tables 
            WHERE table_schema = '{SCHEMA}' AND table_type = 'BASE TABLE'
        """))
        total_tables = res.scalar()
        print(f"Total BASE TABLES in {SCHEMA}: {total_tables}")
        # 401 application tables + alembic_version = 402
        assert total_tables >= 401, f"Expected at least 401 tables, found {total_tables}"

        # 3. Check critical tables
        for t in ["organizations", "leads", "sales_loop_events", "webhook_event_claims", "token_blacklist"]:
            res = await conn.execute(text(f"""
                SELECT count(*) FROM information_schema.tables 
                WHERE table_schema = '{SCHEMA}' AND table_name = '{t}'
            """))
            assert res.scalar() == 1, f"Missing critical table {t}"
        print("All critical tables verified present.")

        # 4. Check webhook_event_claims unique constraint
        res = await conn.execute(text(f"""
            SELECT count(*) FROM information_schema.table_constraints
            WHERE table_schema = '{SCHEMA}' AND table_name = 'webhook_event_claims'
              AND constraint_name = 'uq_webhook_event_claim_provider_org_event'
        """))
        assert res.scalar() == 1, "Missing webhook unique constraint"
        print("Webhook idempotency unique constraint verified.")

    await engine.dispose()
    print("ALL VERIFICATIONS PASSED!")

def main():
    asyncio.run(reset_schema())
    run_alembic()
    asyncio.run(verify_schema())

if __name__ == "__main__":
    main()
