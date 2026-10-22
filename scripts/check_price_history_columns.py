import asyncio
import os
import sys
from pathlib import Path

api_dir = Path("apps/api").resolve()
sys.path.insert(0, str(api_dir))

from dotenv import load_dotenv
load_dotenv('apps/api/.env')

from sqlalchemy import text
from app.database import async_session_maker

async def check():
    async with async_session_maker() as session:
        res = await session.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'property_price_history'
            ORDER BY ordinal_position
        """))
        rows = res.fetchall()
        print("property_price_history columns:")
        for r in rows:
            print(f"  {r[0]}: {r[1]}")

if __name__ == "__main__":
    asyncio.run(check())
