import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

from app.database import engine
from sqlalchemy import text

async def check():
    async with engine.begin() as conn:
        r = await conn.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'phase9_fresh_disposable'"))
        print("Current table count in phase9_fresh_disposable:", r.scalar())

if __name__ == "__main__":
    asyncio.run(check())
