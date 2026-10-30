import asyncio
import asyncpg
import subprocess
import os
import sys

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISP_DB = "test_drill_phase3_downgrade"
DISP_URL = f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}"

async def run_drill():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.execute(f"CREATE DATABASE {DISP_DB} WITH TEMPLATE leadscore;")
    await admin.close()
    print(f"[SETUP] Created disposable database '{DISP_DB}'.")

    conn = await asyncpg.connect(DISP_URL)
    org_id = await conn.fetchval("SELECT id FROM organizations LIMIT 1")
    # Insert orphaned attribution
    await conn.execute("""
        INSERT INTO source_attributions (id, organization_id, lead_id, channel, provider, first_touch_at, last_touch_at, created_at)
        VALUES ('00000000-0000-0000-0000-000000000099', $1, '00000000-0000-0000-0000-000000000088', 'test', 'test', now(), now(), now())
    """, str(org_id))
    print("[SETUP] Inserted orphaned attribution into disposable DB.")
    await conn.close()

    api_dir = os.path.abspath("apps/api")

    # Step 1: Upgrade to head (0050)
    res_up = subprocess.run([
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL}",
        "upgrade", "head"
    ], cwd=api_dir, capture_output=True, text=True)
    print("Alembic upgrade exit code:", res_up.returncode)
    assert res_up.returncode == 0, f"Upgrade failed: {res_up.stderr}"

    # Step 2: Attempt downgrade to 0048
    print("\n--- ATTEMPTING DOWNGRADE FROM 0050 TO 0048 ---")
    res_down_48 = subprocess.run([
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL}",
        "downgrade", "0048_schema_reconciliation_parity"
    ], cwd=api_dir, capture_output=True, text=True)
    print("Downgrade to 0048 exit code:", res_down_48.returncode)
    print("Downgrade to 0048 stdout:\n", res_down_48.stdout)
    print("Downgrade to 0048 stderr:\n", res_down_48.stderr)

    # Step 3: Inspect current database revision
    conn = await asyncpg.connect(DISP_URL)
    current_rev = await conn.fetchval("SELECT version_num FROM alembic_version")
    null_count = await conn.fetchval("SELECT count(*) FROM source_attributions WHERE lead_id IS NULL")
    print(f"[POST-DOWNGRADE INSPECTION] Current revision in DB: {current_rev}")
    print(f"[POST-DOWNGRADE INSPECTION] NULL lead_id records: {null_count}")
    await conn.close()

    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.close()
    print(f"[TEARDOWN] Dropped disposable database '{DISP_DB}'.")

if __name__ == "__main__":
    asyncio.run(run_drill())

