import asyncio
import asyncpg
import subprocess

async def setup_pilot():
    sys_conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/postgres')
    await sys_conn.execute('DROP DATABASE IF EXISTS leadscore_pilot;')
    await sys_conn.execute('CREATE DATABASE leadscore_pilot;')
    print('Created database leadscore_pilot')
    await sys_conn.close()
    
    # Enable vector extension
    pilot_conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/leadscore_pilot')
    await pilot_conn.execute('CREATE EXTENSION IF NOT EXISTS vector;')
    vec_ver = await pilot_conn.fetchval("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
    print(f'pgvector extension enabled in leadscore_pilot: version {vec_ver}')
    await pilot_conn.close()
    
    # Migrate to 0049 via Alembic
    cmd = 'python -m alembic -x db_url=postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_pilot upgrade 0049_source_attribution_uuid_parity'
    res = subprocess.run(cmd, shell=True, cwd='apps/api', capture_output=True, text=True)
    print('Alembic Upgrade STDOUT:\n', res.stdout)
    print('Alembic Upgrade STDERR:\n', res.stderr)
    print('Alembic Upgrade Return Code:', res.returncode)
    
    # Verify tables and revision
    pilot_conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/leadscore_pilot')
    rev = await pilot_conn.fetchval('SELECT version_num FROM alembic_version')
    table_count = await pilot_conn.fetchval("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")
    cols = await pilot_conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'source_attributions' AND column_name IN ('lead_id', 'organization_id')
    """)
    col_map = {r['column_name']: r['data_type'] for r in cols}
    print(f'leadscore_pilot Status: Revision={rev}, Tables={table_count}, Columns={col_map}')
    await pilot_conn.close()

if __name__ == '__main__':
    asyncio.run(setup_pilot())

