import asyncio
import os
import sys

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from sqlalchemy import text
from app.database import engine

async def check():
    async with engine.begin() as conn:
        res = await conn.execute(text("SELECT table_schema, table_name FROM information_schema.tables WHERE table_name = 'alembic_version'"))
        print("alembic_version found in:", res.fetchall())
        res2 = await conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'phase7_test_disposable' AND table_type = 'BASE TABLE'"))
        print("Total BASE TABLES in phase7_test_disposable:", res2.scalar())
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
