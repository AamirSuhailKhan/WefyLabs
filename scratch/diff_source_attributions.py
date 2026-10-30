import asyncio
import asyncpg

async def check():
    c1 = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/leadscore")
    c2 = await asyncpg.connect("postgresql://postgres:postgres@localhost:5432/leadscore_verify_phase6")

    r1 = await c1.fetch("SELECT * FROM source_attributions ORDER BY id;")
    r2 = await c2.fetch("SELECT * FROM source_attributions ORDER BY id;")

    print(f"leadscore count: {len(r1)}")
    print(f"leadscore_verify_phase6 count: {len(r2)}")

    if [dict(x) for x in r1] == [dict(x) for x in r2]:
        print("[SUCCESS] source_attributions rows are 100% IDENTICAL across all columns!")
    else:
        print("[DIFF DETECTED]:")
        for x, y in zip(r1, r2):
            if dict(x) != dict(y):
                print(f"  Live: {dict(x)}\n  Backup: {dict(y)}")
    await c1.close()
    await c2.close()

asyncio.run(check())
