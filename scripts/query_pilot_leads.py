import asyncio, asyncpg, json

async def main():
    conn = await asyncpg.connect('postgresql://postgres.iymirycycichjbllucsr:BeetleLabs%402026@aws-0-ap-south-1.pooler.supabase.com:5432/postgres')
    rows = await conn.fetch('''
        SELECT id, name, phone, email, status, broker_id, organization_id, created_at, updated_at
        FROM leads
        WHERE organization_id = 'a0317351-e076-493e-8b84-182f8c43666e'
        ORDER BY created_at ASC
    ''')
    print(f"Total leads for org: {len(rows)}")
    for r in rows:
        print(f"  {r['id']} | {r['name']} | {r['phone']} | status={r['status']} | created={r['created_at']}")
    await conn.close()

asyncio.run(main())
