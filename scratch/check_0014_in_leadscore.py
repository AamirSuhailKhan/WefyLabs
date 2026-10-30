import asyncio
import asyncpg

async def check():
    conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/leadscore')
    has_countries = await conn.fetchval("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='countries'")
    has_currencies = await conn.fetchval("SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='currencies'")
    print('leadscore has countries table:', bool(has_countries))
    print('leadscore has currencies table:', bool(has_currencies))
    cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='leads' AND column_name IN ('country_code', 'market_id', 'locale')")
    print('leadscore leads 0014 columns:', [r['column_name'] for r in cols])
    await conn.close()

if __name__ == '__main__':
    asyncio.run(check())

