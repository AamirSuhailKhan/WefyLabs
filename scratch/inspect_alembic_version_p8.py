import asyncio
import os
import sys

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.database import engine
from sqlalchemy import text

async def main():
    async with engine.begin() as conn:
        res = await conn.execute(text("""
            SELECT table_schema, table_name, column_name, character_maximum_length, data_type
            FROM information_schema.columns
            WHERE table_name = 'alembic_version'
        """))
        rows = res.fetchall()
        print(f"alembic_version columns found in database ({len(rows)}):")
        for r in rows:
            print(f"  Schema: {r[0]}, Table: {r[1]}, Column: {r[2]}, Length: {r[3]}, Type: {r[4]}")

if __name__ == "__main__":
    asyncio.run(main())
