import asyncio
import asyncpg
import uuid

LEADSCORE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/leadscore"
PILOT_URL = "postgresql://postgres:postgres@127.0.0.1:5432/leadscore_pilot"

async def test_selects():
    org_id_str = "35c904e8-1d5a-41d9-a54e-2dc2e93f4a9d"
    org_id_uuid = uuid.UUID(org_id_str)

    # 1. Test 0048 (VARCHAR)
    conn_0048 = await asyncpg.connect(LEADSCORE_URL)
    print("=== 0048 SELECT TESTS ===")
    try:
        r = await conn_0048.fetch("SELECT * FROM source_attributions WHERE organization_id = $1;", org_id_uuid)
        print("0048 SELECT with UUID object: SUCCESS, count =", len(r))
    except Exception as e:
        print(f"0048 SELECT with UUID object: FAILED -> {type(e).__name__}: {e}")

    try:
        r = await conn_0048.fetch("SELECT * FROM source_attributions WHERE organization_id = $1;", org_id_str)
        print("0048 SELECT with str object: SUCCESS, count =", len(r))
    except Exception as e:
        print(f"0048 SELECT with str object: FAILED -> {type(e).__name__}: {e}")
    await conn_0048.close()

    # 2. Test 0049 (UUID)
    conn_0049 = await asyncpg.connect(PILOT_URL)
    print("\n=== 0049 SELECT TESTS ===")
    try:
        r = await conn_0049.fetch("SELECT * FROM source_attributions WHERE organization_id = $1;", org_id_uuid)
        print("0049 SELECT with UUID object: SUCCESS, count =", len(r))
    except Exception as e:
        print(f"0049 SELECT with UUID object: FAILED -> {type(e).__name__}: {e}")

    try:
        r = await conn_0049.fetch("SELECT * FROM source_attributions WHERE organization_id = $1;", org_id_str)
        print("0049 SELECT with str object: SUCCESS, count =", len(r))
    except Exception as e:
        print(f"0049 SELECT with str object: FAILED -> {type(e).__name__}: {e}")
    await conn_0049.close()

if __name__ == "__main__":
    asyncio.run(test_selects())

