import asyncio
import asyncpg
import subprocess
import sys
import os
import json

async def setup_databases():
    admin_conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    
    # 1. Path A: Fresh DB initialized via init_db.py
    await admin_conn.execute("DROP DATABASE IF EXISTS test_schema_path_a;")
    await admin_conn.execute("CREATE DATABASE test_schema_path_a;")
    
    # 2. Path B: Existing 0048 DB upgraded to 0049 via Alembic
    await admin_conn.execute("DROP DATABASE IF EXISTS test_schema_path_b;")
    await admin_conn.execute("CREATE DATABASE test_schema_path_b WITH TEMPLATE leadscore;")
    
    await admin_conn.close()
    print("[1] Test databases test_schema_path_a and test_schema_path_b created.")

def run_init_db():
    print("[2] Running Path A: init_db.py on test_schema_path_a...")
    env = os.environ.copy()
    env["PYTHONPATH"] = "apps/api"
    env["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/test_schema_path_a"
    env["ENV"] = "test"
    cmd = [sys.executable, "apps/api/scripts/init_db.py", "--env", "test"]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    print("  init_db exit code:", res.returncode)
    if res.returncode != 0:
        print("  init_db stdout tail:", res.stdout[-800:])
        print("  init_db stderr tail:", res.stderr[-800:])
    return res.returncode

def run_upgrade_path_b():
    print("[3] Running Path B: alembic upgrade head on test_schema_path_b (templated from 0048)...")
    api_dir = os.path.abspath("apps/api")
    cmd = [
        sys.executable, "-m", "alembic",
        "-c", "alembic.ini",
        "-x", "db_url=postgresql://postgres:postgres@127.0.0.1:5432/test_schema_path_b",
        "upgrade", "head"
    ]
    res = subprocess.run(cmd, cwd=api_dir, capture_output=True, text=True)
    print("  alembic upgrade exit code:", res.returncode)
    if res.returncode != 0:
        print("  alembic stdout tail:", res.stdout[-800:])
        print("  alembic stderr tail:", res.stderr[-800:])
    return res.returncode

async def introspect_db(db_name: str):
    conn = await asyncpg.connect(f"postgresql://postgres:postgres@127.0.0.1:5432/{db_name}")
    
    # 1. Version
    rev = await conn.fetchval("SELECT version_num FROM alembic_version")
    
    # 2. Tables
    tables = await conn.fetch("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    table_names = [t['table_name'] for t in tables]
    
    # 3. Columns & Data Types
    cols = await conn.fetch("""
        SELECT table_name, column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, column_name
    """)
    columns_map = {}
    for c in cols:
        columns_map.setdefault(c['table_name'], {})[c['column_name']] = {
            "type": c['data_type'],
            "nullable": c['is_nullable'],
            "default": c['column_default']
        }
        
    # 4. Foreign Keys
    fks = await conn.fetch("""
        SELECT
            tc.table_name, kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name
          AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name
          AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints AS rc
          ON rc.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
        ORDER BY tc.table_name, kcu.column_name
    """)
    fk_list = [(r['table_name'], r['column_name'], r['foreign_table_name'], r['foreign_column_name'], r['delete_rule']) for r in fks]

    # 5. Indexes
    indexes = await conn.fetch("""
        SELECT tablename, indexname, indexdef
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    """)
    idx_list = [(r['tablename'], r['indexname']) for r in indexes]

    # 6. Extensions
    exts = await conn.fetch("SELECT extname, extversion FROM pg_extension ORDER BY extname")
    ext_list = [(r['extname'], r['extversion']) for r in exts]

    await conn.close()
    return {
        "revision": rev,
        "table_count": len(table_names),
        "tables": set(table_names),
        "columns": columns_map,
        "fks": set(fk_list),
        "indexes": set(idx_list),
        "extensions": ext_list
    }

async def compare_schemas():
    schema_a = await introspect_db("test_schema_path_a")
    schema_b = await introspect_db("test_schema_path_b")
    schema_pilot = await introspect_db("leadscore_pilot")
    
    print("\n" + "=" * 70)
    print("SCHEMA PARITY COMPARISON RESULTS")
    print("=" * 70)
    
    print(f"Path A (Fresh init_db):     Rev={schema_a['revision']}, Tables={schema_a['table_count']}")
    print(f"Path B (Upgraded 0048->49): Rev={schema_b['revision']}, Tables={schema_b['table_count']}")
    print(f"Pilot DB (leadscore_pilot):  Rev={schema_pilot['revision']}, Tables={schema_pilot['table_count']}")
    
    # 1. Compare tables
    diff_ab_tables = schema_a['tables'] ^ schema_b['tables']
    diff_pilot_tables = schema_a['tables'] ^ schema_pilot['tables']
    print(f"\nTable Differences (Path A vs Path B): {len(diff_ab_tables)}")
    if diff_ab_tables:
        print("  Only in Path A:", schema_a['tables'] - schema_b['tables'])
        print("  Only in Path B:", schema_b['tables'] - schema_a['tables'])
    print(f"Table Differences (Path A vs Pilot):  {len(diff_pilot_tables)}")
    if diff_pilot_tables:
        print("  Only in Path A:", schema_a['tables'] - schema_pilot['tables'])
        print("  Only in Pilot:", schema_pilot['tables'] - schema_a['tables'])

    # 2. Check source_attributions parity specifically
    for name, schema in [("Path A", schema_a), ("Path B", schema_b), ("Pilot", schema_pilot)]:
        attr_cols = schema['columns'].get('source_attributions', {})
        lead_id_type = attr_cols.get('lead_id', {}).get('type')
        org_id_type = attr_cols.get('organization_id', {}).get('type')
        lead_nullable = attr_cols.get('lead_id', {}).get('nullable')
        print(f"\n[{name}] source_attributions: lead_id={lead_id_type} (nullable={lead_nullable}), organization_id={org_id_type}")

    # 3. Check vector extension
    print("\nExtensions in Path A:", [e[0] for e in schema_a['extensions']])
    print("Extensions in Path B:", [e[0] for e in schema_b['extensions']])
    print("Extensions in Pilot:",  [e[0] for e in schema_pilot['extensions']])

    # Clean up test databases
    admin_conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    await admin_conn.execute("DROP DATABASE IF EXISTS test_schema_path_a;")
    await admin_conn.execute("DROP DATABASE IF EXISTS test_schema_path_b;")
    await admin_conn.close()
    print("\nCleaned up test_schema_path_a and test_schema_path_b.")

if __name__ == "__main__":
    asyncio.run(setup_databases())
    rc_a = run_init_db()
    rc_b = run_upgrade_path_b()
    if rc_a == 0 and rc_b == 0:
        asyncio.run(compare_schemas())
    else:
        print("Schema setup FAILED; cannot complete comparison.")

