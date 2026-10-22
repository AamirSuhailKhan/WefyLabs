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
        res = await session.execute(text("SELECT id, email, password_hash, onboarding_status FROM brokers WHERE email = 'aamir.fresh@bmu.edu.in'"))
        r = res.fetchone()
        print("Broker info:")
        print("  id:", r[0])
        print("  email:", r[1])
        print("  has_password_hash:", bool(r[2]))
        print("  onboarding_status:", r[3])

if __name__ == "__main__":
    asyncio.run(check())
