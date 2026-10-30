import asyncio
import asyncpg
import subprocess
import sys
import os
import json

async def setup_comparison_databases():
    admin_conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    
    # 1. Path A: Fresh DB initialized via init_db.py
    await admin_conn.execute("DROP DATABASE IF EXISTS test_schema_full_a;")
    await admin_conn.execute("CREATE DATABASE test_schema_full_a;")
    
    # 2. Path B: Existing 0048 DB upgraded to 0049 via Alembic
    await admin_conn.execute("DROP DATABASE IF EXISTS test_schema_full_b;")
    await admin_conn.execute("CREATE DATABASE test_schema_full_b WITH TEMPLATE leadscore;")
    
    await admin_conn.close()
    print("[1] Databases test_schema_full_a and test_schema_full_b prepared.")

def run_init_db():
    print("[2] Running Path A: init_db.py on test_schema_full_a...")
    env = os.environ.copy()
    env["PYTHONPATH"] = "apps/api"
    env["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/test_schema_full_a"
    env["ENV"] = "test"
    cmd = [sys.executable, "apps/api/scripts/init_db.py", "--env", "test"]
    res = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if res.returncode != 0:
        print("  init_db stdout:", res.stdout[-600:])
        print("  init_db stderr:", res.stderr[-600:])
    return res.returncode

def run_upgrade_path_b():
    print("[3] Running Path B: alembic upgrade head on test_schema_full_b...")
    api_dir = os.path.abspath("apps/api")
    cmd = [
        sys.executable, "-m", "alembic",
        "-c", "alembic.ini",
        "-x", "db_url=postgresql://postgres:postgres@127.0.0.1:5432/test_schema_full_b",
        "upgrade", "head"
    ]
    res = subprocess.run(cmd, cwd=api_dir, capture_output=True, text=True)
    if res.returncode != 0:
        print("  alembic stdout:", res.stdout[-600:])
        print("  alembic stderr:", res.stderr[-600:])
    return res.returncode

async def deep_introspect(db_name: str):
    conn = await asyncpg.connect(f"postgresql://postgres:postgres@127.0.0.1:5432/{db_name}")
    
    # 1. Revision
    rev = await conn.fetchval("SELECT version_num FROM alembic_version")
    
    # 2. Tables
    tables = [r['table_name'] for r in await conn.fetch("""
        SELECT table_name FROM information_schema.tables 
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)]
    
    # 3. Columns, Types, Nullability, Defaults
    cols = await conn.fetch("""
        SELECT table_name, column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, column_name
    """)
    cols_map = {}
    for c in cols:
        cols_map.setdefault(c['table_name'], {})[c['column_name']] = {
            "type": c['data_type'],
            "nullable": c['is_nullable'],
            "default": c['column_default']
        }
        
    # 4. Primary Keys
    pks = await conn.fetch("""
        SELECT tc.table_name, kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_schema = 'public'
        ORDER BY tc.table_name, kcu.column_name
    """)
    pk_map = {}
    for r in pks:
        pk_map.setdefault(r['table_name'], []).append(r['column_name'])
        
    # 5. Foreign Keys
    fks = await conn.fetch("""
        SELECT
            tc.table_name, kcu.column_name,
            ccu.table_name AS foreign_table_name,
            ccu.column_name AS foreign_column_name,
            rc.delete_rule
        FROM information_schema.table_constraints AS tc
        JOIN information_schema.key_column_usage AS kcu
          ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
        JOIN information_schema.constraint_column_usage AS ccu
          ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
        JOIN information_schema.referential_constraints AS rc
          ON rc.constraint_name = tc.constraint_name
        WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public'
        ORDER BY tc.table_name, kcu.column_name
    """)
    fk_list = [(r['table_name'], r['column_name'], r['foreign_table_name'], r['foreign_column_name'], r['delete_rule']) for r in fks]

    # 6. Constraints (Unique, Check)
    constraints = await conn.fetch("""
        SELECT table_name, constraint_name, constraint_type
        FROM information_schema.table_constraints
        WHERE table_schema = 'public' AND constraint_type IN ('UNIQUE', 'CHECK')
        ORDER BY table_name, constraint_name
    """)
    constraint_list = [(r['table_name'], r['constraint_name'], r['constraint_type']) for r in constraints]

    # 7. Indexes
    indexes = await conn.fetch("""
        SELECT tablename, indexname
        FROM pg_indexes
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname
    """)
    idx_list = [(r['tablename'], r['indexname']) for r in indexes]

    # 8. Sequences
    sequences = await conn.fetch("""
        SELECT sequence_name FROM information_schema.sequences
        WHERE sequence_schema = 'public'
        ORDER BY sequence_name
    """)
    seq_list = [r['sequence_name'] for r in sequences]

    # 9. Extensions
    extensions = await conn.fetch("""
        SELECT extname, extversion FROM pg_extension ORDER BY extname
    """)
    ext_list = [(r['extname'], r['extversion']) for r in extensions]

    # 10. Triggers
    triggers = await conn.fetch("""
        SELECT trigger_name, event_manipulation, event_object_table
        FROM information_schema.triggers
        WHERE trigger_schema = 'public'
        ORDER BY event_object_table, trigger_name
    """)
    trig_list = [(r['trigger_name'], r['event_manipulation'], r['event_object_table']) for r in triggers]

    await conn.close()
    return {
        "revision": rev,
        "table_count": len(tables),
        "tables": set(tables),
        "columns": cols_map,
        "pks": pk_map,
        "fks": set(fk_list),
        "constraints": set(constraint_list),
        "indexes": set(idx_list),
        "sequences": set(seq_list),
        "extensions": ext_list,
        "triggers": set(trig_list)
    }

async def compare_all():
    print("[4] Introspecting databases...")
    data_a = await deep_introspect("test_schema_full_a")
    data_b = await deep_introspect("test_schema_full_b")
    data_pilot = await deep_introspect("leadscore_pilot")
    
    print("\n" + "=" * 80)
    print("COMPREHENSIVE SCHEMA AUDIT: PATH A (bootstrap) vs PATH B (sequential 0049) vs PILOT")
    print("=" * 80)
    
    report = {
        "Path_A_Bootstrap": {
            "revision": data_a["revision"],
            "table_count": data_a["table_count"],
            "fk_count": len(data_a["fks"]),
            "index_count": len(data_a["indexes"]),
            "sequence_count": len(data_a["sequences"]),
            "trigger_count": len(data_a["triggers"]),
            "extensions": [e[0] for e in data_a["extensions"]]
        },
        "Path_B_Sequentially_Upgraded": {
            "revision": data_b["revision"],
            "table_count": data_b["table_count"],
            "fk_count": len(data_b["fks"]),
            "index_count": len(data_b["indexes"]),
            "sequence_count": len(data_b["sequences"]),
            "trigger_count": len(data_b["triggers"]),
            "extensions": [e[0] for e in data_b["extensions"]]
        },
        "Pilot_Leadscore": {
            "revision": data_pilot["revision"],
            "table_count": data_pilot["table_count"],
            "fk_count": len(data_pilot["fks"]),
            "index_count": len(data_pilot["indexes"]),
            "sequence_count": len(data_pilot["sequences"]),
            "trigger_count": len(data_pilot["triggers"]),
            "extensions": [e[0] for e in data_pilot["extensions"]]
        }
    }
    print(json.dumps(report, indent=2))
    
    # Check Table Parity
    print("\n[Table Parity]")
    diff_tables = data_a["tables"] ^ data_b["tables"]
    if not diff_tables:
        print("  PERFECT TABLE MATCH: Exactly 411 tables in both Path A and Path B.")
    else:
        print("  Table differences:", diff_tables)
        
    # Check SourceAttribution specifically across all 3
    print("\n[SourceAttribution Parity across all 3]")
    for label, d in [("Path A", data_a), ("Path B", data_b), ("Pilot", data_pilot)]:
        sa = d["columns"].get("source_attributions", {})
        print(f"  {label}:")
        print(f"    organization_id: type={sa.get('organization_id', {}).get('type')}, nullable={sa.get('organization_id', {}).get('nullable')}")
        print(f"    lead_id:         type={sa.get('lead_id', {}).get('type')}, nullable={sa.get('lead_id', {}).get('nullable')}")
        sa_fks = [f for f in d["fks"] if f[0] == "source_attributions"]
        print(f"    FKs: {sa_fks}")
        
    # Clean up test databases
    admin_conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    await admin_conn.execute("DROP DATABASE IF EXISTS test_schema_full_a;")
    await admin_conn.execute("DROP DATABASE IF EXISTS test_schema_full_b;")
    await admin_conn.close()
    print("\nTest databases cleaned up successfully.")

if __name__ == "__main__":
    asyncio.run(setup_comparison_databases())
    rc_a = run_init_db()
    rc_b = run_upgrade_path_b()
    if rc_a == 0 and rc_b == 0:
        asyncio.run(compare_all())
    else:
        print("Setup failed, cannot proceed with comparison.")

