import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

from app.database import engine
from sqlalchemy import text

async def list_schemas():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT LIKE 'pg_%' AND schema_name != 'information_schema' ORDER BY schema_name"))
        schemas = [r[0] for r in res.fetchall()]
        print("Discovered schemas:", schemas)

if __name__ == "__main__":
    asyncio.run(list_schemas())
