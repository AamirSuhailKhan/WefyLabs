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
        res = await conn.execute(text("""
            SELECT pid, state, wait_event_type, wait_event, query 
            FROM pg_stat_activity 
            WHERE state != 'idle' AND pid != pg_backend_pid()
        """))
        rows = res.fetchall()
        print(f"Non-idle activities ({len(rows)}):")
        for r in rows:
            print(f"PID {r[0]}: state={r[1]}, wait={r[2]}:{r[3]}, query={r[4][:60]}")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
