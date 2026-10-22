import sys, asyncio
sys.path.insert(0, 'apps/api')
from dotenv import load_dotenv; load_dotenv('apps/api/.env')
from sqlalchemy import text
from app.database import async_session_maker

async def main():
    async with async_session_maker() as db:
        r = await db.execute(text("SELECT id, name, created_at, status FROM leads WHERE organization_id = 'a0317351-e076-493e-8b84-182f8c43666e' ORDER BY created_at DESC"))
        for row in r.fetchall():
            print(dict(row._mapping))

asyncio.run(main())
