import os
import sys
import asyncio
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.config import settings
from app.database import Base
import app.models

async def setup_test_schema(schema_name="test_canonical_p7"):
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE"))
        await conn.execute(text(f"CREATE SCHEMA {schema_name}"))
        # Ensure extensions are available in search path
        await conn.execute(text(f"SET search_path TO {schema_name}, extensions, public"))
    await engine.dispose()
    print(f"Isolated clean schema '{schema_name}' created.")

if __name__ == "__main__":
    asyncio.run(setup_test_schema())
