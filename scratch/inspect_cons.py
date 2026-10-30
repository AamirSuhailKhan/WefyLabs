import asyncio
import asyncpg
import json

async def inspect_constraint_diffs():
    # Inspect on leadscore (templated 0048) and leadscore_pilot
    conn_pilot = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/leadscore_pilot")
    cons = await conn_pilot.fetch("""
        SELECT conname, contype, pg_get_constraintdef(oid) as def
        FROM pg_constraint
        WHERE connamespace = 'public'::regnamespace
        ORDER BY conname;
    """)
    await conn_pilot.close()
    print("Total constraints in pilot:", len(cons))

if __name__ == "__main__":
    asyncio.run(inspect_constraint_diffs())

