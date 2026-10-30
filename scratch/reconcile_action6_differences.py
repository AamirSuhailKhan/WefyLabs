import asyncio
import asyncpg
import subprocess
import sys
import os
import json

async def setup_dbs():
    admin = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    await admin.execute("DROP DATABASE IF EXISTS test_diff_a;")
    await admin.execute("DROP DATABASE IF EXISTS test_diff_b;")
    await admin.execute("CREATE DATABASE test_diff_a;")
    await admin.execute("CREATE DATABASE test_diff_b WITH TEMPLATE leadscore;")
    await admin.close()

def run_init_a():
    env = os.environ.copy()
    env["PYTHONPATH"] = "apps/api"
    env["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/test_diff_a"
    env["ENV"] = "test"
    cmd = [sys.executable, "apps/api/scripts/init_db.py", "--env", "test"]
    subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)

def run_upgrade_b():
    api_dir = os.path.abspath("apps/api")
    cmd = [
        sys.executable, "-m", "alembic",
        "-c", "alembic.ini",
        "-x", "db_url=postgresql://postgres:postgres@127.0.0.1:5432/test_diff_b",
        "upgrade", "head"
    ]
    subprocess.run(cmd, cwd=api_dir, capture_output=True, text=True, check=True)

async def inspect_indexes_and_extensions():
    conn_a = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/test_diff_a")
    conn_b = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/test_diff_b")
    conn_pilot = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/leadscore_pilot")

    # 1. Inspect Indexes
    indexes_a = await conn_a.fetch("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname;")
    indexes_b = await conn_b.fetch("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname;")
    indexes_pilot = await conn_pilot.fetch("SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname;")

    idx_set_a = {(r['tablename'], r['indexname']) for r in indexes_a}
    idx_set_b = {(r['tablename'], r['indexname']) for r in indexes_b}
    idx_set_pilot = {(r['tablename'], r['indexname']) for r in indexes_pilot}

    diff_a_minus_b = idx_set_a - idx_set_b
    diff_b_minus_a = idx_set_b - idx_set_a
    diff_pilot_minus_b = idx_set_pilot - idx_set_b

    # 2. Inspect Extensions
    exts_a = await conn_a.fetch("SELECT extname, extversion FROM pg_extension ORDER BY extname;")
    exts_b = await conn_b.fetch("SELECT extname, extversion FROM pg_extension ORDER BY extname;")
    exts_pilot = await conn_pilot.fetch("SELECT extname, extversion FROM pg_extension ORDER BY extname;")

    # 3. Inspect Constraints
    cons_a = await conn_a.fetch("SELECT conname, contype, pg_get_constraintdef(oid) as def FROM pg_constraint WHERE connamespace = 'public'::regnamespace ORDER BY conname;")
    cons_b = await conn_b.fetch("SELECT conname, contype, pg_get_constraintdef(oid) as def FROM pg_constraint WHERE connamespace = 'public'::regnamespace ORDER BY conname;")
    cons_pilot = await conn_pilot.fetch("SELECT conname, contype, pg_get_constraintdef(oid) as def FROM pg_constraint WHERE connamespace = 'public'::regnamespace ORDER BY conname;")

    con_set_a = {(r['conname'], r['def']) for r in cons_a}
    con_set_b = {(r['conname'], r['def']) for r in cons_b}
    con_set_pilot = {(r['conname'], r['def']) for r in cons_pilot}

    diff_con_ab = con_set_a ^ con_set_b

    await conn_a.close()
    await conn_b.close()
    await conn_pilot.close()

    # Clean up test dbs
    admin = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    await admin.execute("DROP DATABASE IF EXISTS test_diff_a;")
    await admin.execute("DROP DATABASE IF EXISTS test_diff_b;")
    await admin.close()

    result = {
        "indexes": {
            "count_a": len(indexes_a),
            "count_b": len(indexes_b),
            "count_pilot": len(indexes_pilot),
            "in_a_not_in_b": list(diff_a_minus_b),
            "in_b_not_in_a": list(diff_b_minus_a),
            "in_pilot_not_in_b": list(diff_pilot_minus_b),
        },
        "extensions": {
            "path_a": [(r['extname'], r['extversion']) for r in exts_a],
            "path_b": [(r['extname'], r['extversion']) for r in exts_b],
            "pilot": [(r['extname'], r['extversion']) for r in exts_pilot],
        },
        "constraints": {
            "count_a": len(cons_a),
            "count_b": len(cons_b),
            "count_pilot": len(cons_pilot),
            "diff_count_ab": len(diff_con_ab)
        }
    }
    return result

async def main():
    await setup_dbs()
    run_init_a()
    run_upgrade_b()
    res = await inspect_indexes_and_extensions()
    with open("scratch/schema_reconciliation_action6.json", "w") as f:
        json.dump(res, f, indent=2)
    print("Action 6 Reconciliation Complete. Output written to scratch/schema_reconciliation_action6.json")

if __name__ == "__main__":
    asyncio.run(main())

