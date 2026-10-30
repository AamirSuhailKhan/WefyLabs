import asyncio
import asyncpg
import subprocess
import os

async def build_pilot():
    sys_conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/postgres')
    await sys_conn.execute('DROP DATABASE IF EXISTS leadscore_pilot;')
    await sys_conn.execute('CREATE DATABASE leadscore_pilot;')
    print('1. Created fresh leadscore_pilot database.')
    await sys_conn.close()
    
    # Restore baseline from backups/leadscore_backup_20261028.dump
    dump_path = 'backups/leadscore_backup_20261028.dump'
    assert os.path.exists(dump_path), 'Backup dump missing!'
    
    cmd = [
        'docker', 'exec', '-i', 'leadscore_postgres',
        'pg_restore', '-U', 'postgres', '-d', 'leadscore_pilot',
        '--clean', '--if-exists', '--no-owner', '--no-privileges', '--single-transaction'
    ]
    with open(dump_path, 'rb') as f:
        res = subprocess.run(cmd, stdin=f, capture_output=True, text=True)
    print(f'2. pg_restore completed with returncode: {res.returncode}')
    
    # Verify restored state
    pilot_conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/leadscore_pilot')
    rev_before = await pilot_conn.fetchval('SELECT version_num FROM alembic_version;')
    tables_before = await pilot_conn.fetchval("SELECT count(table_name) FROM information_schema.tables WHERE table_schema = 'public';")
    print(f'3. Baseline Restored: Revision={rev_before}, Tables={tables_before}')
    await pilot_conn.close()
    
    # Upgrade to 0049
    upgrade_cmd = 'python -m alembic -x db_url=postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_pilot upgrade 0049_source_attribution_uuid_parity'
    up_res = subprocess.run(upgrade_cmd, shell=True, cwd='apps/api', capture_output=True, text=True)
    print(f'4. Upgrade to 0049 completed with returncode: {up_res.returncode}')
    
    # Verify post-upgrade state
    pilot_conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/leadscore_pilot')
    rev_after = await pilot_conn.fetchval('SELECT version_num FROM alembic_version;')
    tables_after = await pilot_conn.fetchval("SELECT count(table_name) FROM information_schema.tables WHERE table_schema = 'public';")
    cols = await pilot_conn.fetch("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'source_attributions' AND column_name IN ('lead_id', 'organization_id');
    """)
    col_map = {r['column_name']: r['data_type'] for r in cols}
    print(f'5. leadscore_pilot Final State: Revision={rev_after}, Tables={tables_after}, Columns={col_map}')
    
    # Enable pgvector if not installed
    await pilot_conn.execute('CREATE EXTENSION IF NOT EXISTS vector;')
    vec_ver = await pilot_conn.fetchval("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
    print(f'6. pgvector extension verified: version={vec_ver}')
    await pilot_conn.close()

if __name__ == '__main__':
    asyncio.run(build_pilot())

