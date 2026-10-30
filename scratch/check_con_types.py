import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath("apps/api"))
from app.database import engine
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        res = await conn.execute(text("""
            SELECT c.conname, c.contype, cl.relname
            FROM pg_constraint c
            JOIN pg_namespace n ON n.oid = c.connamespace
            JOIN pg_class cl ON cl.oid = c.conrelid
            WHERE n.nspname = 'phase7_test_disposable'
            LIMIT 10
        """))
        for r in res.fetchall():
            print(repr(r[0]), repr(r[1]), type(r[1]), repr(r[2]))

if __name__ == "__main__":
    asyncio.run(check())
