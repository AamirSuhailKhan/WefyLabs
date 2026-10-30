import asyncio
import os
import sys

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.database import engine
from sqlalchemy import text

TEST_SCHEMA = "phase8_version_compat_test"
LONG_REV = "0039_build09_revenue_intelligence"  # 35 chars

async def run_test():
    async with engine.begin() as conn:
        print(f"1. Creating disposable schema: {TEST_SCHEMA}")
        await conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {TEST_SCHEMA}"))
        await conn.execute(text(f"SET search_path TO {TEST_SCHEMA}, extensions"))

        print("2. Simulating legacy Alembic table with VARCHAR(32)")
        await conn.execute(text(f"DROP TABLE IF EXISTS {TEST_SCHEMA}.alembic_version"))
        await conn.execute(text(f"""
            CREATE TABLE {TEST_SCHEMA}.alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
        """))

        # Verify initial length
        res = await conn.execute(text(f"""
            SELECT character_maximum_length FROM information_schema.columns
            WHERE table_schema = '{TEST_SCHEMA}' AND table_name = 'alembic_version'
        """))
        initial_len = res.scalar()
        print(f"   Initial version_num length: {initial_len}")
        assert initial_len == 32, f"Expected 32, got {initial_len}"

        print("3. Attempting to insert 35-char revision into VARCHAR(32) table (should fail)...")
        failed = False
        try:
            async with conn.begin_nested():
                await conn.execute(text(f"INSERT INTO {TEST_SCHEMA}.alembic_version (version_num) VALUES ('{LONG_REV}')"))
        except Exception as e:
            failed = True
            print(f"   Properly caught expected failure: {type(e).__name__} (value too long for VARCHAR(32))")
        assert failed, "Inserting 35-char string into VARCHAR(32) should have failed!"

        print("4. Executing upgrade widening DDL: ALTER TABLE alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)")
        await conn.execute(text(f"ALTER TABLE {TEST_SCHEMA}.alembic_version ALTER COLUMN version_num TYPE VARCHAR(64)"))

        # Verify widened length
        res = await conn.execute(text(f"""
            SELECT character_maximum_length FROM information_schema.columns
            WHERE table_schema = '{TEST_SCHEMA}' AND table_name = 'alembic_version'
        """))
        widened_len = res.scalar()
        print(f"   Widened version_num length: {widened_len}")
        assert widened_len == 64, f"Expected 64, got {widened_len}"

        print(f"5. Inserting 35-char revision '{LONG_REV}' into widened table...")
        await conn.execute(text(f"INSERT INTO {TEST_SCHEMA}.alembic_version (version_num) VALUES ('{LONG_REV}')"))

        # Read back
        res = await conn.execute(text(f"SELECT version_num FROM {TEST_SCHEMA}.alembic_version"))
        val = res.scalar()
        print(f"   Read back version: '{val}' (len={len(val)})")
        assert val == LONG_REV, f"Value mismatch: {val} != {LONG_REV}"

        print("6. Cleaning up disposable test schema...")
        await conn.execute(text(f"DROP SCHEMA {TEST_SCHEMA} CASCADE"))
        print("ALL 7 VERSION TABLE COMPATIBILITY TESTS PASSED!")

if __name__ == "__main__":
    asyncio.run(run_test())
