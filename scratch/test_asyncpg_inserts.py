import asyncio
import asyncpg
import uuid

LEADSCORE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/leadscore"
PILOT_URL = "postgresql://postgres:postgres@127.0.0.1:5432/leadscore_pilot"

async def test_inserts():
    # 1. Test 0048 (VARCHAR columns)
    conn_0048 = await asyncpg.connect(LEADSCORE_URL)
    org_id_str = "35c904e8-1d5a-41d9-a54e-2dc2e93f4a9d"
    lead_id_str = "dac1a157-657b-4e48-8e76-f5469ee2af6b"
    org_id_uuid = uuid.UUID(org_id_str)
    lead_id_uuid = uuid.UUID(lead_id_str)

    print("--- 0048: INSERT with UUID object ---")
    tr = conn_0048.transaction()
    await tr.start()
    try:
        await conn_0048.execute("""
            INSERT INTO source_attributions (id, organization_id, lead_id, created_at)
            VALUES ($1, $2, $3, NOW());
        """, "test-0048-uuid", org_id_uuid, lead_id_uuid)
        print("0048 with UUID: SUCCESS")
    except Exception as e:
        print(f"0048 with UUID: FAILED -> {type(e).__name__}: {e}")
    await tr.rollback()

    print("\n--- 0048: INSERT with str object ---")
    tr = conn_0048.transaction()
    await tr.start()
    try:
        await conn_0048.execute("""
            INSERT INTO source_attributions (id, organization_id, lead_id, created_at)
            VALUES ($1, $2, $3, NOW());
        """, "test-0048-str", org_id_str, lead_id_str)
        print("0048 with str: SUCCESS")
    except Exception as e:
        print(f"0048 with str: FAILED -> {type(e).__name__}: {e}")
    await tr.rollback()
    await conn_0048.close()

    # 2. Test 0049 (UUID columns)
    conn_0049 = await asyncpg.connect(PILOT_URL)
    print("\n--- 0049: INSERT with UUID object ---")
    tr = conn_0049.transaction()
    await tr.start()
    try:
        await conn_0049.execute("""
            INSERT INTO source_attributions (id, organization_id, lead_id, created_at)
            VALUES ($1, $2, $3, NOW());
        """, "test-0049-uuid", org_id_uuid, lead_id_uuid)
        print("0049 with UUID: SUCCESS")
    except Exception as e:
        print(f"0049 with UUID: FAILED -> {type(e).__name__}: {e}")
    await tr.rollback()

    print("\n--- 0049: INSERT with str object ---")
    tr = conn_0049.transaction()
    await tr.start()
    try:
        await conn_0049.execute("""
            INSERT INTO source_attributions (id, organization_id, lead_id, created_at)
            VALUES ($1, $2, $3, NOW());
        """, "test-0049-str", org_id_str, lead_id_str)
        print("0049 with str: SUCCESS")
    except Exception as e:
        print(f"0049 with str: FAILED -> {type(e).__name__}: {e}")
    await tr.rollback()
    await conn_0049.close()

if __name__ == "__main__":
    asyncio.run(test_inserts())

