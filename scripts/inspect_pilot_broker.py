import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv('apps/api/.env')
import asyncpg

def js(obj):
    import datetime, uuid
    return obj.isoformat() if isinstance(obj, (datetime.datetime, datetime.date)) else str(obj)

async def check():
    conn = await asyncpg.connect(os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://'))
    broker = await conn.fetchrow("SELECT * FROM brokers WHERE id = 'c193be18-4a6a-4030-9089-f94c42119189'")
    print('PILOT_BROKER:', json.dumps({k: js(v) for k, v in dict(broker).items()}))
    members = await conn.fetch("SELECT * FROM organization_members WHERE organization_id = 'a0317351-e076-493e-8b84-182f8c43666e'")
    for m in members:
        print('MEMBER:', json.dumps({k: js(v) for k, v in dict(m).items()}))
    org = await conn.fetchrow("SELECT * FROM organizations WHERE id = 'a0317351-e076-493e-8b84-182f8c43666e'")
    print('PILOT_ORG:', json.dumps({k: js(v) for k, v in dict(org).items()}))
    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())
