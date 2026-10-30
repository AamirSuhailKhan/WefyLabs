import asyncio
import asyncpg

LEADSCORE_URL = "postgresql://postgres:postgres@127.0.0.1:5432/leadscore"
PILOT_URL = "postgresql://postgres:postgres@127.0.0.1:5432/leadscore_pilot"

async def test_joins():
    # 1. Test 0048
    conn_0048 = await asyncpg.connect(LEADSCORE_URL)
    print("=== 0048 JOIN TESTS ===")
    # Query 1: Direct join: leads.id = source_attributions.lead_id
    try:
        r = await conn_0048.fetch("SELECT leads.id, source_attributions.id FROM leads JOIN source_attributions ON leads.id = source_attributions.lead_id;")
        print("0048 direct join leads.id = source_attributions.lead_id: SUCCESS, count =", len(r))
    except Exception as e:
        print(f"0048 direct join: FAILED -> {type(e).__name__}: {e}")

    # Query 2: Cast join: leads.id::text = source_attributions.lead_id::text
    try:
        r = await conn_0048.fetch("SELECT leads.id, source_attributions.id FROM leads JOIN source_attributions ON leads.id::text = source_attributions.lead_id::text;")
        print("0048 cast text join: SUCCESS, count =", len(r))
    except Exception as e:
        print(f"0048 cast text join: FAILED -> {type(e).__name__}: {e}")

    # Query 3: Cast uuid join: leads.id = source_attributions.lead_id::uuid
    try:
        r = await conn_0048.fetch("SELECT leads.id, source_attributions.id FROM leads JOIN source_attributions ON leads.id = source_attributions.lead_id::uuid;")
        print("0048 cast uuid join: SUCCESS, count =", len(r))
    except Exception as e:
        print(f"0048 cast uuid join: FAILED -> {type(e).__name__}: {e}")
    await conn_0048.close()

    # 2. Test 0049
    conn_0049 = await asyncpg.connect(PILOT_URL)
    print("\n=== 0049 JOIN TESTS ===")
    try:
        r = await conn_0049.fetch("SELECT leads.id, source_attributions.id FROM leads JOIN source_attributions ON leads.id = source_attributions.lead_id;")
        print("0049 direct join leads.id = source_attributions.lead_id: SUCCESS, count =", len(r))
    except Exception as e:
        print(f"0049 direct join: FAILED -> {type(e).__name__}: {e}")

    try:
        r = await conn_0049.fetch("SELECT leads.id, source_attributions.id FROM leads JOIN source_attributions ON leads.id::text = source_attributions.lead_id::text;")
        print("0049 cast text join: SUCCESS, count =", len(r))
    except Exception as e:
        print(f"0049 cast text join: FAILED -> {type(e).__name__}: {e}")

    try:
        r = await conn_0049.fetch("SELECT leads.id, source_attributions.id FROM leads JOIN source_attributions ON leads.id = source_attributions.lead_id::uuid;")
        print("0049 cast uuid join: SUCCESS, count =", len(r))
    except Exception as e:
        print(f"0049 cast uuid join: FAILED -> {type(e).__name__}: {e}")
    await conn_0049.close()

if __name__ == "__main__":
    asyncio.run(test_joins())

