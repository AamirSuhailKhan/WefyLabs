import asyncio
import subprocess
import asyncpg

async def main():
    conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/postgres')
    await conn.execute('DROP DATABASE IF EXISTS test_disc_0047;')
    await conn.execute('CREATE DATABASE test_disc_0047 TEMPLATE leadscore;')
    c47 = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/test_disc_0047')
    # Notice that leadscore was just upgraded to 0050!
    # If we simply update alembic_version to 0047, the schema already has column types uuid and FKs from 0050!
    # When Alembic tries to run 0048 -> 0049 on a schema that already has UUID columns:
    # 0049 says: ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid
    # and ADD CONSTRAINT fk_source_attributions_organization_id!
    # If the constraint ALREADY exists, PostgreSQL raises: relation "fk_source_attributions_organization_id" already exists!
    print("Investigating schema state...")
    fks = await c47.fetch("SELECT conname FROM pg_constraint WHERE conname LIKE 'fk_source%'")
    print("Existing FKs in template:", [r['conname'] for r in fks])
    await c47.close()
    await conn.close()

if __name__ == "__main__":
    asyncio.run(main())

