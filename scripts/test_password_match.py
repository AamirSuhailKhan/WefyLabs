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
from app.modules.auth.service import verify_password, hash_password

async def test():
    async with async_session_maker() as session:
        res = await session.execute(text("SELECT password_hash FROM brokers WHERE email = 'aamir.fresh@bmu.edu.in'"))
        h = res.scalar()
        passwords = [
            'Password123!', 'Admin123!', 'Pass1234!', 'password', 'TestPass123!',
            'secret123', 'Aamir123!', 'Aamir@123', 'WefyLabs123!', 'wefylabs'
        ]
        matched = False
        for pwd in passwords:
            if verify_password(pwd, h):
                print('MATCH FOUND:', pwd)
                matched = True
                break
        if not matched:
            print('No match from common list. Hash start:', h[:20])

if __name__ == "__main__":
    asyncio.run(test())
