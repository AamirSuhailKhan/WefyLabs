import asyncio
import asyncpg
import subprocess
import sys
import os

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISP_DB = "test_disposable_downgrade_0050"
DISP_URL = f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}"

async def setup():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.execute(f"CREATE DATABASE {DISP_DB} WITH TEMPLATE leadscore;")
    await admin.close()

async def tear_down():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.close()

def run_downgrade_cmd():
    api_dir = os.path.abspath("apps/api")
    cmd = [
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL}",
        "downgrade", "0049_source_attribution_uuid_parity"
    ]
    return subprocess.run(cmd, cwd=api_dir, capture_output=True, text=True)

async def test_downgrade():
    await setup()
    try:
        # Upgrade to 0050 first
        api_dir = os.path.abspath("apps/api")
        subprocess.run([
            sys.executable, "-m", "alembic", "-c", "alembic.ini",
            "-x", f"db_url={DISP_URL}", "upgrade", "head"
        ], cwd=api_dir, capture_output=True, check=True)

        conn = await asyncpg.connect(DISP_URL)
        broker_id = await conn.fetchval("SELECT id FROM brokers LIMIT 1;")
        
        # Test A: When a broker has 'paused' status -> downgrade MUST abort
        await conn.execute("UPDATE brokers SET subscription_status = 'paused' WHERE id = $1;", broker_id)
        await conn.close()
        
        res = run_downgrade_cmd()
        assert res.returncode != 0, "Downgrade should fail when modern status exists!"
        assert "DOWNGRADE ABORTED" in res.stderr or "DOWNGRADE ABORTED" in res.stdout
        print("Downgrade Safeguard A PASSED: Aborted when modern subscription_status present.")

        # Test B: Clean data -> downgrade succeeds
        conn = await asyncpg.connect(DISP_URL)
        await conn.execute("UPDATE brokers SET subscription_status = 'trial' WHERE id = $1;", broker_id)
        await conn.close()

        res_clean = run_downgrade_cmd()
        assert res_clean.returncode == 0, f"Clean downgrade failed: {res_clean.stderr}"
        
        conn = await asyncpg.connect(DISP_URL)
        rev = await conn.fetchval("SELECT version_num FROM alembic_version;")
        assert rev == "0049_source_attribution_uuid_parity"
        print("Downgrade Safeguard B PASSED: Clean downgrade reverted to 0049 successfully.")
        await conn.close()

    finally:
        await tear_down()

if __name__ == "__main__":
    asyncio.run(test_downgrade())

