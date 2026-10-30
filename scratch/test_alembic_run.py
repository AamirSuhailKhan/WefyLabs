import os
import sys
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.config import settings

async def run_test():
    engine = create_async_engine(settings.DATABASE_URL)
    schema_name = "test_empty_upgrade_p7"
    
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        await conn.execute(text(f"CREATE SCHEMA {schema_name}"))
        await conn.execute(text(f"SET search_path TO {schema_name}, extensions, public"))
    
    print(f"Clean schema {schema_name} created.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(run_test())
