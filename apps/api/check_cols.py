import asyncio
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine

async def check():
    async with AsyncSessionLocal() as s:
        tables = [
            'pilot_tenants', 
            'pilot_observations', 
            'pilot_human_decisions', 
            'pilot_metric_snapshots', 
            'pilot_audit_events',
            'deals', 
            'site_visits',
            'deal_bookings', 
            'deal_commissions'
        ]
        for t in tables:
            res = await s.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns WHERE table_name = :t ORDER BY ordinal_position"
            ), {'t': t})
            cols = [f"{r[0]} ({r[1]})" for r in res.fetchall()]
            print(f"\nTABLE {t}:")
            print("  " + ", ".join(cols))
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(check())
