import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def main():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_pilot")
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'brokers'"))
        cols = res.fetchall()
        print("Columns in brokers:")
        for col, dt in cols:
            print(f"  {col}: {dt}")
        
        res = await conn.execute(text("SELECT id, email, name, auth_version FROM brokers LIMIT 5"))
        print("\nBrokers:")
        for r in res.fetchall():
            print(" ", r)
            
        res = await conn.execute(text("SELECT id, name FROM organizations LIMIT 5"))
        print("\nOrganizations:")
        for r in res.fetchall():
            print(" ", r)

        res = await conn.execute(text("SELECT broker_id, organization_id, role FROM organization_members LIMIT 5"))
        print("\nOrganization Members:")
        for r in res.fetchall():
            print(" ", r)
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
