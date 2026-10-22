import asyncio, asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres.iymirycycichjbllucsr:BeetleLabs%402026@aws-0-ap-south-1.pooler.supabase.com:5432/postgres')
    rows = await conn.fetch('SELECT id, organization_id, current_stage, pilot_status FROM pilot_tenants')
    print('Pilot Tenants in DB:')
    for r in rows:
        print(f"  id={r['id']}, org_id={r['organization_id']}, stage={r['current_stage']}, status={r['pilot_status']}")
    await conn.close()

asyncio.run(main())
