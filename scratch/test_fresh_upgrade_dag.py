import asyncio
import asyncpg
import subprocess
import sys
import os

async def setup_test_db():
    conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    await conn.execute("DROP DATABASE IF EXISTS test_fresh_upgrade_dag;")
    await conn.execute("CREATE DATABASE test_fresh_upgrade_dag;")
    # Ensure pgvector extension is created
    db_conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/test_fresh_upgrade_dag")
    await db_conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    await db_conn.close()
    await conn.close()
    print("Created test_fresh_upgrade_dag database with vector extension.")

def run_upgrade():
    api_dir = os.path.abspath("apps/api")
    cmd = [
        sys.executable, "-m", "alembic",
        "-c", "alembic.ini",
        "-x", "db_url=postgresql://postgres:postgres@127.0.0.1:5432/test_fresh_upgrade_dag",
        "upgrade", "head"
    ]
    print("Running in", api_dir, ":", " ".join(cmd))
    res = subprocess.run(cmd, cwd=api_dir, capture_output=True, text=True)
    print("Exit code:", res.returncode)
    if res.stdout:
        print("STDOUT tail:\n", res.stdout[-1500:] if len(res.stdout) > 1500 else res.stdout)
    if res.stderr:
        print("STDERR tail:\n", res.stderr[-1500:] if len(res.stderr) > 1500 else res.stderr)
    return res.returncode

async def check_result():
    conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/test_fresh_upgrade_dag")
    rev = await conn.fetchval("SELECT version_num FROM alembic_version")
    tbl_cnt = await conn.fetchval("SELECT count(table_name) FROM information_schema.tables WHERE table_schema='public'")
    print(f"Final Alembic Version: {rev}, Table Count: {tbl_cnt}")
    await conn.close()

    # Drop test db
    admin_conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/postgres")
    await admin_conn.execute("DROP DATABASE IF EXISTS test_fresh_upgrade_dag;")
    await admin_conn.close()
    print("Cleaned up test_fresh_upgrade_dag.")

if __name__ == "__main__":
    asyncio.run(setup_test_db())
    rc = run_upgrade()
    if rc == 0:
        asyncio.run(check_result())
    else:
        print("FAILED to upgrade fresh database!")
