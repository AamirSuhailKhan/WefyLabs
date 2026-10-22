import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv('apps/api/.env')
import asyncpg

async def run():
    url = os.getenv('DATABASE_URL')
    dsn = url.replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(dsn)
    
    # Tables in public
    tables = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name")
    table_names = [r['table_name'] for r in tables]
    print(f"Total public tables: {len(table_names)}")
    
    # Brokers columns
    broker_cols = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'brokers' ORDER BY ordinal_position")
    print("Brokers columns:", [r['column_name'] for r in broker_cols])

    # Organizations columns
    org_cols = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'organizations' ORDER BY ordinal_position")
    print("Organizations columns:", [r['column_name'] for r in org_cols])

    # Fetch brokers records
    brokers = await conn.fetch("SELECT * FROM brokers")
    print(f"Brokers count: {len(brokers)}")
    for b in brokers:
        print("Broker:", dict(b))

    # Fetch organizations records
    orgs = await conn.fetch("SELECT * FROM organizations")
    print(f"Organizations count: {len(orgs)}")
    for o in orgs:
        print("Org:", dict(o))

    # Query row count for every public table
    print("\n--- ALL PUBLIC TABLES AND ROW COUNTS ---")
    all_counts = {}
    for t in table_names:
        try:
            c = await conn.fetchval(f'SELECT count(*) FROM "{t}"')
            all_counts[t] = c
            print(f"{t}: {c}")
        except Exception as e:
            all_counts[t] = f"ERROR: {e}"
            print(f"{t}: ERROR {e}")


    await conn.close()

if __name__ == '__main__':
    asyncio.run(run())
