import asyncio
import asyncpg
import subprocess
import sys
import os

async def inspect_exact_diffs():
    admin = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    await admin.execute("DROP DATABASE IF EXISTS test_diff_a;")
    await admin.execute("DROP DATABASE IF EXISTS test_diff_b;")
    await admin.execute("CREATE DATABASE test_diff_a;")
    await admin.execute("CREATE DATABASE test_diff_b WITH TEMPLATE leadscore;")
    await admin.close()

    env = os.environ.copy()
    env["PYTHONPATH"] = "apps/api"
    env["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/test_diff_a"
    env["ENV"] = "test"
    subprocess.run([sys.executable, "apps/api/scripts/init_db.py", "--env", "test"], env=env, capture_output=True, check=True)

    subprocess.run([
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", "db_url=postgresql://postgres:postgres@127.0.0.1:5432/test_diff_b",
        "upgrade", "head"
    ], cwd=os.path.abspath("apps/api"), capture_output=True, check=True)

    conn_a = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/test_diff_a")
    conn_b = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/test_diff_b")

    cons_a = {r['conname']: r['def'] for r in await conn_a.fetch("SELECT conname, pg_get_constraintdef(oid) as def FROM pg_constraint WHERE connamespace = 'public'::regnamespace;")}
    cons_b = {r['conname']: r['def'] for r in await conn_b.fetch("SELECT conname, pg_get_constraintdef(oid) as def FROM pg_constraint WHERE connamespace = 'public'::regnamespace;")}

    only_in_a = set(cons_a.keys()) - set(cons_b.keys())
    only_in_b = set(cons_b.keys()) - set(cons_a.keys())
    differing_defs = {k: (cons_a[k], cons_b[k]) for k in (set(cons_a.keys()) & set(cons_b.keys())) if cons_a[k] != cons_b[k]}

    print("Only in Path A (bootstrap):", only_in_a)
    print("Only in Path B (sequential Alembic):", only_in_b)
    print("Differing definitions:", differing_defs)

    await conn_a.close()
    await conn_b.close()
    admin = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    await admin.execute("DROP DATABASE IF EXISTS test_diff_a;")
    await admin.execute("DROP DATABASE IF EXISTS test_diff_b;")
    await admin.close()

if __name__ == "__main__":
    asyncio.run(inspect_exact_diffs())

