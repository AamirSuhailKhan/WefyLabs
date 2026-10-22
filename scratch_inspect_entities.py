import sys, asyncio, json
sys.path.insert(0, 'apps/api')
from dotenv import load_dotenv; load_dotenv('apps/api/.env')
from sqlalchemy import text
from app.database import async_session_maker

CANONICAL_ORG = "a0317351-e076-493e-8b84-182f8c43666e"

async def main():
    async with async_session_maker() as db:
        # 1. Leads
        r_leads = await db.execute(text("SELECT * FROM leads WHERE organization_id = :org ORDER BY created_at DESC"), {"org": CANONICAL_ORG})
        leads = [dict(r._mapping) for r in r_leads.fetchall()]
        for l in leads:
            for k, v in l.items(): l[k] = str(v)

        # 2. SalesLoopEvents
        r_sle = await db.execute(text("SELECT * FROM sales_loop_events WHERE tenant_id = :org ORDER BY created_at DESC"), {"org": CANONICAL_ORG})
        sle = [dict(r._mapping) for r in r_sle.fetchall()]
        for s in sle:
            for k, v in s.items(): s[k] = str(v)

        # 3. PilotObservations
        r_obs = await db.execute(text("SELECT * FROM pilot_observations WHERE organization_id = :org ORDER BY observed_at DESC"), {"org": CANONICAL_ORG})
        obs = [dict(r._mapping) for r in r_obs.fetchall()]
        for o in obs:
            for k, v in o.items(): o[k] = str(v)

        # 4. PilotHumanDecisions
        r_dec = await db.execute(text("SELECT * FROM pilot_human_decisions WHERE organization_id = :org ORDER BY decided_at DESC"), {"org": CANONICAL_ORG})
        dec = [dict(r._mapping) for r in r_dec.fetchall()]
        for d in dec:
            for k, v in d.items(): d[k] = str(v)

        print(json.dumps({
            "leads": leads,
            "sales_loop_events": sle,
            "pilot_observations": obs,
            "pilot_human_decisions": dec,
        }, indent=2))

asyncio.run(main())
