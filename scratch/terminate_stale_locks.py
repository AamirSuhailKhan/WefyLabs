import asyncio
import os
import sys

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from sqlalchemy import text
from app.database import engine

async def terminate_stale():
    async with engine.begin() as conn:
        res = await conn.execute(text("""
            SELECT pg_terminate_backend(pid) 
            FROM pg_stat_activity 
            WHERE state = 'idle in transaction' AND pid != pg_backend_pid()
        """))
        print("Terminated stale backends:", res.fetchall())
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(terminate_stale())
