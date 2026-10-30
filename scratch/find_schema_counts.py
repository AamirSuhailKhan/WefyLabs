import os
import sys
import asyncio
from sqlalchemy import text

sys.path.insert(0, os.path.abspath("apps/api"))
from app.database import engine

async def find_schemas():
    async with engine.begin() as conn:
        res = await conn.execute(text("""
            SELECT table_schema, count(*) 
            FROM information_schema.tables 
            WHERE table_type = 'BASE TABLE'
            GROUP BY table_schema
            ORDER BY count(*) DESC
        """))
        for row in res.fetchall():
            print(f"Schema: {row[0]}, Table count: {row[1]}")

if __name__ == "__main__":
    asyncio.run(find_schemas())
