import asyncio, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')
from sqlalchemy import text
from app.database import async_session_maker

async def main():
    async with async_session_maker() as db:
        # integrations columns
        r = await db.execute(text(
            "SELECT column_name, data_type FROM information_schema.columns "
            "WHERE table_name='integrations' ORDER BY ordinal_position"
        ))
        print('=== integrations columns ===')
        for row in r.fetchall():
            print(f'  {row[0]}: {row[1]}')

        # integrations data
        r2 = await db.execute(text('SELECT * FROM integrations LIMIT 20'))
        rows2 = r2.fetchall()
        keys2 = list(r2.keys())
        print(f'=== INTEGRATIONS ({len(rows2)} rows) ===')
        for row in rows2:
            print(dict(zip(keys2, row)))

        # integration_credentials columns
        r3 = await db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name='integration_credentials' ORDER BY ordinal_position"
        ))
        print('=== integration_credentials columns ===')
        for row in r3.fetchall():
            print(f'  {row[0]}')

        # integration_credentials data
        r4 = await db.execute(text('SELECT * FROM integration_credentials LIMIT 20'))
        rows4 = r4.fetchall()
        keys4 = list(r4.keys())
        print(f'=== INTEGRATION CREDENTIALS ({len(rows4)} rows) ===')
        for row in rows4:
            print(dict(zip(keys4, row)))

        # Check for any webhook/incoming-lead related tables
        r5 = await db.execute(text(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema='public' AND (table_name LIKE '%webhook%' OR table_name LIKE '%incoming%' OR table_name LIKE '%source%') "
            "ORDER BY table_name"
        ))
        print('=== WEBHOOK/INCOMING/SOURCE TABLES ===')
        for row in r5.fetchall():
            print(f'  {row[0]}')

        # Check recent leads more fully - look for source that is not 'manual'
        r6 = await db.execute(text(
            "SELECT source, count(*) FROM leads GROUP BY source ORDER BY count(*) DESC"
        ))
        print('=== LEADS BY SOURCE ===')
        for row in r6.fetchall():
            print(f'  source={row[0]}, count={row[1]}')

asyncio.run(main())
