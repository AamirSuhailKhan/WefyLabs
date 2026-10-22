import asyncio
import os
from dotenv import load_dotenv
load_dotenv('apps/api/.env')
import asyncpg

async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://'))
    cols = await conn.fetch("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'omnichannel_conversations' ORDER BY ordinal_position")
    print('OMNICHANNEL_COLS:', [r['column_name'] for r in cols])
    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
