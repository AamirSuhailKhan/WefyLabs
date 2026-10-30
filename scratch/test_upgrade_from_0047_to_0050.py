import asyncio
import asyncpg
import subprocess
import sys
import os

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISP_DB = "test_upgrade_0047_to_0050"
DISP_URL = f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}"

async def run_test():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.execute(f"CREATE DATABASE {DISP_DB} WITH TEMPLATE leadscore;")
    await admin.close()
    print(f"[SETUP] Created disposable database '{DISP_DB}' from 'leadscore' (revision 0048).")

    api_dir = os.path.abspath("apps/api")

    # Step 1: Downgrade from 0048 to 0047
    res_down = subprocess.run([
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL}",
        "downgrade", "0047_webhook_event_claims"
    ], cwd=api_dir, capture_output=True, text=True)
    assert res_down.returncode == 0, f"Downgrade to 0047 failed: {res_down.stderr}"
    print("[DOWNGRADE] Successfully downgraded disposable DB to 0047_webhook_event_claims.")

    conn = await asyncpg.connect(DISP_URL)
    rev_47 = await conn.fetchval("SELECT version_num FROM alembic_version")
    assert rev_47 == "0047_webhook_event_claims", f"Expected 0047, got {rev_47}"
    print(f"[VERIFIED] Current revision is confirmed at: {rev_47}")
    await conn.close()

    # Step 2: Upgrade to head (should execute 0048 -> 0049 -> 0050)
    res_up = subprocess.run([
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL}",
        "upgrade", "head"
    ], cwd=api_dir, capture_output=True, text=True)
    assert res_up.returncode == 0, f"Upgrade to head failed: {res_up.stderr}"
    print(f"[UPGRADE] Alembic upgraded 0047 -> head successfully. Output:\n{res_up.stderr.strip()}")

    # Step 3: Verify final state
    conn = await asyncpg.connect(DISP_URL)
    rev_final = await conn.fetchval("SELECT version_num FROM alembic_version")
    assert rev_final == "0050_broker_subscription_constraint_parity", f"Expected 0050, got {rev_final}"
    
    # Check 0048 additions
    idx_market = await conn.fetchval("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_leads_country_market'")
    idx_deleted = await conn.fetchval("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_leads_deleted_at'")
    idx_org_status = await conn.fetchval("SELECT 1 FROM pg_indexes WHERE indexname = 'ix_leads_org_status'")
    assert idx_market and idx_deleted and idx_org_status, "Missing 0048 indexes"

    # Check 0049 additions
    attr_lead_type = await conn.fetchval("SELECT data_type FROM information_schema.columns WHERE table_name = 'source_attributions' AND column_name = 'lead_id'")
    attr_org_type = await conn.fetchval("SELECT data_type FROM information_schema.columns WHERE table_name = 'source_attributions' AND column_name = 'organization_id'")
    assert attr_lead_type == "uuid" and attr_org_type == "uuid", "0049 UUID columns not native UUID"

    # Check 0050 check constraints
    cons = await conn.fetch("SELECT conname FROM pg_constraint WHERE conname IN ('ck_brokers_subscription_status', 'ck_brokers_subscription_plan', 'ck_brokers_onboarding_status', 'ck_subscriptions_status')")
    assert len(cons) == 4, f"Expected 4 constraints, found {len(cons)}"

    print("[SUCCESS] All 0047 -> 0048 -> 0049 -> 0050 upgrade verifications passed with 100% fidelity!")
    await conn.close()

    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.close()
    print(f"[TEARDOWN] Dropped disposable database '{DISP_DB}'.")

if __name__ == "__main__":
    asyncio.run(run_test())

