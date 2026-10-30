import asyncio
import asyncpg
import uuid
import traceback
import sys
sys.path.insert(0, "apps/api")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.acquisition_models import SourceAttribution
from app.models.lead import Lead

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISPOSABLE_DB = "test_disposable_0048"
DISPOSABLE_URL = f"postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/{DISPOSABLE_DB}"

async def setup_disposable_0048():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISPOSABLE_DB};")
    await admin.execute(f"CREATE DATABASE {DISPOSABLE_DB} WITH TEMPLATE leadscore;")
    await admin.close()
    print(f"[SETUP] Created disposable database '{DISPOSABLE_DB}' from template 'leadscore' (0048).")

async def tear_down_disposable_0048():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISPOSABLE_DB};")
    await admin.close()
    print(f"[TEARDOWN] Dropped disposable database '{DISPOSABLE_DB}'.")

async def reproduce_failures():
    engine = create_async_engine(DISPOSABLE_URL, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession)
    
    test_lead_uuid = uuid.UUID("dac1a157-657b-4e48-8e76-f5469ee2af6b")
    test_org_uuid = uuid.UUID("35c904e8-1d5a-41d9-a54e-2dc2e93f4a9d")

    results = {}

    # Test 1: Query by UUID parameter
    print("\n--- Failure 1: Query by UUID parameter on 0048 ---")
    async with sf() as session:
        try:
            stmt = select(SourceAttribution).where(SourceAttribution.lead_id == test_lead_uuid)
            await session.execute(stmt)
            results["query_by_uuid"] = "UNEXPECTED_PASS"
        except Exception as e:
            results["query_by_uuid"] = f"FAILED_AS_EXPECTED: {type(e).__name__}: {e}"
            print("Captured Failure 1:")
            print(f"  Exception: {type(e).__name__}")
            print(f"  Message: {e}")

    # Test 2: Relational JOIN on 0048
    print("\n--- Failure 2: JOIN Lead.id == SourceAttribution.lead_id on 0048 ---")
    async with sf() as session:
        try:
            stmt = select(Lead.id, SourceAttribution.id).join(SourceAttribution, Lead.id == SourceAttribution.lead_id)
            await session.execute(stmt)
            results["relational_join"] = "UNEXPECTED_PASS"
        except Exception as e:
            results["relational_join"] = f"FAILED_AS_EXPECTED: {type(e).__name__}: {e}"
            print("Captured Failure 2:")
            print(f"  Exception: {type(e).__name__}")
            print(f"  Message: {e}")

    # Test 3: Raw asyncpg insert with UUID
    print("\n--- Failure 3: asyncpg execute INSERT with UUID parameter on 0048 ---")
    raw_conn = await asyncpg.connect(f"postgresql://postgres:postgres@127.0.0.1:5432/{DISPOSABLE_DB}")
    try:
        await raw_conn.execute("""
            INSERT INTO source_attributions (id, organization_id, lead_id, created_at)
            VALUES ($1, $2, $3, NOW());
        """, str(uuid.uuid4()), test_org_uuid, test_lead_uuid)
        results["raw_uuid_insert"] = "UNEXPECTED_PASS"
    except Exception as e:
        results["raw_uuid_insert"] = f"FAILED_AS_EXPECTED: {type(e).__name__}: {e}"
        print("Captured Failure 3:")
        print(f"  Exception: {type(e).__name__}")
        print(f"  Message: {e}")
    await raw_conn.close()

    await engine.dispose()
    return results

async def main():
    await setup_disposable_0048()
    try:
        res = await reproduce_failures()
        print("\n=== REPRODUCTION SUMMARY ON DISPOSABLE 0048 ===")
        for k, v in res.items():
            print(f"  {k}: {v}")
    finally:
        await tear_down_disposable_0048()

if __name__ == "__main__":
    asyncio.run(main())

