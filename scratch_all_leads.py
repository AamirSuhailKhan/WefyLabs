import sys, asyncio
sys.path.insert(0, 'apps/api')
from dotenv import load_dotenv; load_dotenv('apps/api/.env')
from sqlalchemy import text
from app.database import async_session_maker

async def main():
    async with async_session_maker() as db:
        r = await db.execute(text("SELECT id, name, organization_id, created_at FROM leads ORDER BY created_at DESC"))
        rows = r.fetchall()
        print(f"Total leads in system: {len(rows)}")
        for row in rows:
            print(dict(row._mapping))

asyncio.run(main())
