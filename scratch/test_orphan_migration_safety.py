import asyncio
import asyncpg
import subprocess
import sys
import os

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISP_DB = "test_orphan_check"
DISP_URL = f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}"

async def run_drill():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.execute(f"CREATE DATABASE {DISP_DB} WITH TEMPLATE leadscore;")
    await admin.close()

    conn = await asyncpg.connect(DISP_URL)
    org_id = await conn.fetchval("SELECT id FROM organizations LIMIT 1")
    # Insert an orphaned attribution record like in hosted Supabase
    await conn.execute("""
        INSERT INTO source_attributions (id, organization_id, lead_id, channel, provider, first_touch_at, last_touch_at, created_at)
        VALUES ('00000000-0000-0000-0000-000000000099', $1, '00000000-0000-0000-0000-000000000088', 'test', 'test', now(), now(), now())
    """, str(org_id))
    print("[SETUP] Inserted orphaned attribution into disposable DB.")
    await conn.close()

    # Now attempt alembic upgrade head
    res = subprocess.run([
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL}",
        "upgrade", "head"
    ], cwd=os.path.abspath("apps/api"), capture_output=True, text=True)

    print("Alembic upgrade exit code:", res.returncode)
    print("Alembic upgrade stdout:\n", res.stdout)
    print("Alembic upgrade stderr:\n", res.stderr)

    # Verify that the orphaned attribution was preserved with lead_id = NULL
    conn = await asyncpg.connect(DISP_URL)
    row = await conn.fetchrow("SELECT id, organization_id, lead_id FROM source_attributions WHERE id = '00000000-0000-0000-0000-000000000099'")
    print("Verified migrated orphaned attribution:", dict(row))
    assert row["lead_id"] is None, f"Expected lead_id to be NULL, got {row['lead_id']}"
    assert str(row["organization_id"]) == str(org_id), "Expected org_id to match"
    print("All orphaned attribution assertions PASSED!")
    await conn.close()

    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.close()

if __name__ == "__main__":
    asyncio.run(run_drill())
