import asyncio, asyncpg, json
from datetime import datetime, timezone

DB = "postgresql://postgres.iymirycycichjbllucsr:BeetleLabs%402026@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"

async def main():
    conn = await asyncpg.connect(DB)

    rows = await conn.fetch("""
        SELECT table_name, column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name IN ('sales_loop_events', 'pilot_observations', 'pilot_human_decisions', 'leads', 'pilot_tenants')
          AND column_name IN ('id', 'lead_id', 'pilot_id', 'broker_id', 'organization_id', 'tenant_id')
        ORDER BY table_name, column_name
    """)
    for r in rows:
        print(f"{r['table_name']}.{r['column_name']}: {r['data_type']}")
    await conn.close()

asyncio.run(main())
