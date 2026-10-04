import asyncio
import asyncpg

async def run():
    conn = await asyncpg.connect('postgresql://postgres.iymirycycichjbllucsr:BeetleLabs%402026@aws-0-ap-south-1.pooler.supabase.com:5432/postgres')
    tabs = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name")
    names = [r['table_name'] for r in tabs]
    print(f"Total public tables: {len(names)}")
    for n in names:
        cnt = await conn.fetchval(f'SELECT count(*) FROM "{n}"')
        print(f"  {n:<45}: {cnt}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(run())
