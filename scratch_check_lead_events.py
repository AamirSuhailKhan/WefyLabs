import sys, asyncio
sys.path.insert(0, 'apps/api')
from dotenv import load_dotenv; load_dotenv('apps/api/.env')
from sqlalchemy import text
from app.database import async_session_maker

async def main():
    async with async_session_maker() as db:
        for lead_id in [
            '2434cac9-3b94-49fb-a377-789f4ad785f6',
            '47d1dc97-2458-4dec-980f-a0d3afa24601',
            '1d3d636e-1460-4507-bc3c-2ac0f19f7250'
        ]:
            r_sle = await db.execute(text("SELECT count(*) FROM sales_loop_events WHERE lead_id = :lid"), {"lid": lead_id})
            r_eh = await db.execute(text("SELECT count(*) FROM event_history WHERE payload->>'lead_id' = :lid OR payload->>'id' = :lid"), {"lid": lead_id})
            r_obs = await db.execute(text("SELECT count(*) FROM pilot_observations WHERE lead_id = :lid"), {"lid": lead_id})
            print(f"Lead {lead_id}: sales_loop_events={r_sle.scalar()}, event_history={r_eh.scalar()}, pilot_obs={r_obs.scalar()}")

asyncio.run(main())
