import asyncio, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')
from sqlalchemy import text
from app.database import async_session_maker

TABLES = [
    'pilot_tenants',
    'pilot_observations',
    'pilot_human_decisions',
    'sales_loop_events',
    'pilot_metric_snapshots',
    'pilot_audit_events',
    'leads',
    'lead_integrations',
    'organizations',
]

async def main():
    async with async_session_maker() as db:
        for tbl in TABLES:
            sql = f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = '{tbl}' ORDER BY ordinal_position"
            r = await db.execute(text(sql))
            cols = r.fetchall()
            print(f'=== {tbl} ({len(cols)} cols) ===')
            for c in cols:
                print(f'  {c[0]}: {c[1]}')

asyncio.run(main())
