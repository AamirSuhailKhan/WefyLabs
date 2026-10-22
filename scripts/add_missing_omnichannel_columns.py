import asyncio
import os
from dotenv import load_dotenv
load_dotenv('apps/api/.env')
import asyncpg

async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://'))
    await conn.execute('ALTER TABLE omnichannel_conversations ADD COLUMN IF NOT EXISTS identity_id VARCHAR(36)')
    await conn.execute('ALTER TABLE omnichannel_conversations ADD COLUMN IF NOT EXISTS external_conversation_id VARCHAR(255)')
    cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name = 'omnichannel_conversations' ORDER BY ordinal_position")
    print('UPDATED_COLS:', [r['column_name'] for r in cols])
    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
