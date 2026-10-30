import asyncio
import os
import sys

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from sqlalchemy import text
from app.database import engine

async def find_table():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT table_schema, table_name FROM information_schema.tables WHERE table_name = 'campaign_property_links'"))
        print("campaign_property_links in schemas:", res.fetchall())
        res2 = await conn.execute(text("SELECT table_schema, count(*) FROM information_schema.tables WHERE table_type='BASE TABLE' GROUP BY table_schema"))
        print("All schemas with table counts:")
        for r in res2.fetchall():
            print(f"  {r[0]}: {r[1]}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(find_table())
