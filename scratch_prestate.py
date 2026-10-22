import sys, asyncio, json, os
from urllib.parse import urlparse
sys.path.insert(0, 'apps/api')
from dotenv import load_dotenv; load_dotenv('apps/api/.env')
from sqlalchemy import text
from app.database import async_session_maker

async def main():
    db_url = os.environ.get("DATABASE_URL", "")
    parsed = urlparse(db_url)
    sanitized_db = f"{parsed.scheme}://{parsed.username}@{parsed.hostname}:{parsed.port}{parsed.path}"
    
    async with async_session_maker() as db:
        r = await db.execute(text("SELECT id, organization_id, current_stage, pilot_status, configured_autonomy_level, enrolled_by, enrolled_at, stage_entered_at, policy_version, notes, enrolled_agent_ids FROM pilot_tenants"))
        pilots = [dict(row._mapping) for row in r.fetchall()]
        for p in pilots:
            for k, v in p.items():
                p[k] = str(v)
        
        print(json.dumps({
            "database_target": sanitized_db,
            "pilots": pilots
        }, indent=2))

asyncio.run(main())
