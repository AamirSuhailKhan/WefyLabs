import asyncio
import json
from decimal import Decimal
from datetime import datetime
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return str(obj)
        if isinstance(obj, datetime):
            return obj.isoformat()
        return str(obj)

async def inspect():
    async with AsyncSessionLocal() as s:
        tables = [
            'pilot_tenants', 
            'pilot_observations', 
            'pilot_human_decisions', 
            'pilot_metric_snapshots', 
            'pilot_audit_events',
            'pilot_stage_transitions',
            'leads',
            'deals', 
            'site_visits',
            'deal_bookings', 
            'deal_commissions'
        ]
        out = {}
        for t in tables:
            res = await s.execute(text(f"SELECT * FROM {t}"))
            rows = [dict(r._mapping) for r in res.fetchall()]
            out[t] = rows
        print(json.dumps(out, indent=2, cls=CustomEncoder))
    await engine.dispose()

if __name__ == '__main__':
    asyncio.run(inspect())
