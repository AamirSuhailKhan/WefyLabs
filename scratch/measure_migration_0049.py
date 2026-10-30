import asyncio
import asyncpg
import time

async def measure():
    conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/postgres')
    await conn.execute('DROP DATABASE IF EXISTS phase13_timing_drill;')
    await conn.execute('CREATE DATABASE phase13_timing_drill WITH TEMPLATE leadscore;')
    await conn.close()

    drill_conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/phase13_timing_drill')
    
    t0 = time.perf_counter()
    async with drill_conn.transaction():
        await drill_conn.execute('ALTER TABLE source_attributions ALTER COLUMN lead_id DROP NOT NULL;')
        await drill_conn.execute('''
            ALTER TABLE source_attributions 
            ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid, 
            ALTER COLUMN lead_id TYPE uuid USING lead_id::uuid;
        ''')
        await drill_conn.execute('''
            ALTER TABLE source_attributions 
            ADD CONSTRAINT fk_source_attributions_organization_id 
            FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;
        ''')
        await drill_conn.execute('''
            ALTER TABLE source_attributions 
            ADD CONSTRAINT fk_source_attributions_lead_id 
            FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL;
        ''')
        await drill_conn.execute("UPDATE alembic_version SET version_num = '0049_source_attribution_uuid_parity';")
    t1 = time.perf_counter()
    
    elapsed_ms = (t1 - t0) * 1000
    print(f'Actual DDL Execution Time for Migration 0049: {elapsed_ms:.2f} ms ({elapsed_ms/1000:.4f} s)')
    
    await drill_conn.close()
    conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/postgres')
    await conn.execute('DROP DATABASE IF EXISTS phase13_timing_drill;')
    await conn.close()

if __name__ == '__main__':
    asyncio.run(measure())

