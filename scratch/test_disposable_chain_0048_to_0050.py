import asyncio
import asyncpg
import subprocess
import sys
import os
import json

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISP_DB = "test_disposable_chain_0050"
DISP_URL = f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}"

async def setup():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.execute(f"CREATE DATABASE {DISP_DB} WITH TEMPLATE leadscore;")
    await admin.close()
    print(f"[SETUP] Created disposable database '{DISP_DB}' from 'leadscore' (revision 0048).")

async def tear_down():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.close()
    print(f"[TEARDOWN] Dropped disposable database '{DISP_DB}'.")

def run_alembic_upgrade():
    api_dir = os.path.abspath("apps/api")
    cmd = [
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL}",
        "upgrade", "head"
    ]
    res = subprocess.run(cmd, cwd=api_dir, capture_output=True, text=True)
    assert res.returncode == 0, f"Alembic upgrade failed: {res.stderr}\n{res.stdout}"
    print(f"[UPGRADE] Alembic upgraded to head successfully. Output:\n{res.stdout.strip()}")

async def verify_chain():
    conn = await asyncpg.connect(DISP_URL)
    report = {}

    # 1. Revision
    rev = await conn.fetchval("SELECT version_num FROM alembic_version;")
    assert rev == "0050_broker_subscription_constraint_parity", f"Unexpected rev: {rev}"
    report["current_revision"] = rev

    # 2. Check updated constraints
    cons = await conn.fetch("""
        SELECT conname, pg_get_constraintdef(oid) as def
        FROM pg_constraint
        WHERE conname IN (
            'ck_brokers_subscription_status',
            'ck_brokers_subscription_plan',
            'ck_brokers_onboarding_status',
            'ck_subscriptions_status',
            'fk_source_attributions_organization_id',
            'fk_source_attributions_lead_id'
        )
        ORDER BY conname;
    """)
    cons_map = {r["conname"]: r["def"] for r in cons}
    report["verified_constraints"] = cons_map
    assert "ck_brokers_subscription_status" in cons_map
    assert "ck_brokers_subscription_plan" in cons_map
    assert "ck_brokers_onboarding_status" in cons_map
    assert "ck_subscriptions_status" in cons_map
    assert "fk_source_attributions_organization_id" in cons_map
    assert "fk_source_attributions_lead_id" in cons_map

    # 3. Test previously failing updates
    broker_id = await conn.fetchval("SELECT id FROM brokers LIMIT 1;")
    
    # Test update subscription_plan to 'pro_monthly' (was failing on 0048 and 0049)
    await conn.execute("UPDATE brokers SET subscription_plan = 'pro_monthly' WHERE id = $1;", broker_id)
    plan_val = await conn.fetchval("SELECT subscription_plan FROM brokers WHERE id = $1;", broker_id)
    assert plan_val == "pro_monthly"
    report["test_update_plan_pro_monthly"] = "SUCCESS"

    # Test update subscription_status to 'paused' (was failing on 0048 and 0049)
    await conn.execute("UPDATE brokers SET subscription_status = 'paused' WHERE id = $1;", broker_id)
    status_val = await conn.fetchval("SELECT subscription_status FROM brokers WHERE id = $1;", broker_id)
    assert status_val == "paused"
    report["test_update_status_paused"] = "SUCCESS"

    # Test update subscription_status to 'past_due' (was failing on 0048 and 0049)
    await conn.execute("UPDATE brokers SET subscription_status = 'past_due' WHERE id = $1;", broker_id)
    status_val_2 = await conn.fetchval("SELECT subscription_status FROM brokers WHERE id = $1;", broker_id)
    assert status_val_2 == "past_due"
    report["test_update_status_past_due"] = "SUCCESS"

    # 4. Invariant preservation
    preserved_counts = {}
    for tbl in ["leads", "organizations", "brokers", "organization_members", "source_attributions", "tasks"]:
        cnt = await conn.fetchval(f"SELECT count(*) FROM {tbl};")
        preserved_counts[tbl] = cnt
    report["preserved_counts"] = preserved_counts
    assert preserved_counts["leads"] == 4
    assert preserved_counts["organizations"] == 7
    assert preserved_counts["brokers"] == 8
    assert preserved_counts["source_attributions"] == 3

    await conn.close()
    return report

async def main():
    await setup()
    try:
        run_alembic_upgrade()
        rep = await verify_chain()
        print("\n=== MIGRATION CHAIN VERIFICATION RESULTS ===")
        print(json.dumps(rep, indent=2))
        with open("scratch/migration_chain_0050_results.json", "w") as f:
            json.dump(rep, f, indent=2)
    finally:
        await tear_down()

if __name__ == "__main__":
    asyncio.run(main())

