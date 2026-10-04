import asyncio
import os
from dotenv import load_dotenv

load_dotenv('apps/api/.env')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text

async def inspect():
    url = os.environ.get('DATABASE_URL')
    engine = create_async_engine(url, poolclass=NullPool)
    async with engine.connect() as conn:
        res = await conn.execute(text("""
            SELECT table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name LIKE 'pilot_%'
            ORDER BY table_name, ordinal_position
        """))
        curr = None
        for r in res.fetchall():
            if r[0] != curr:
                curr = r[0]
                print(f"\n--- Table: {curr} ---")
            print(f"  {r[1]} ({r[2]}, nullable={r[3]})")

if __name__ == '__main__':
    asyncio.run(inspect())
