import os
import sys
import json
import asyncio
import subprocess
import asyncpg

PG_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
CONTAINER_PG_HOST = "postgres"
NETWORK = "crmrealstate_default"
IMAGE_TAG = "wefylabs-api:rc-0050"

RESULTS = {}

def record(scenario, passed, details):
    RESULTS[scenario] = {
        "scenario": scenario,
        "status": "PASSED" if passed else "FAILED",
        "details": details
    }
    status_str = "[PASSED]" if passed else "[FAILED]"
    print(f"{status_str} {scenario}")
    if not passed:
        print(f"   Details: {details}")

async def setup_disposable_dbs():
    print("--- Setting up disposable test databases ---")
    conn = await asyncpg.connect(PG_URL)
    for db in ["rc_disposable_0047", "rc_disposable_0048", "rc_disposable_0050"]:
        await conn.execute(f"DROP DATABASE IF EXISTS {db};")
        await conn.execute(f"CREATE DATABASE {db} TEMPLATE leadscore;")
        print(f"Created {db} from leadscore")
    await conn.close()

    # Revert rc_disposable_0047 to genuine 0047 schema
    c47 = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/rc_disposable_0047")
    await c47.execute("UPDATE alembic_version SET version_num = '0047_webhook_event_claims';")
    await c47.execute("ALTER TABLE source_attributions DROP CONSTRAINT IF EXISTS fk_source_attributions_lead_id;")
    await c47.execute("ALTER TABLE source_attributions DROP CONSTRAINT IF EXISTS fk_source_attributions_organization_id;")
    await c47.execute("ALTER TABLE source_attributions ALTER COLUMN organization_id TYPE character varying(36) USING organization_id::text;")
    await c47.execute("ALTER TABLE source_attributions ALTER COLUMN lead_id TYPE character varying(36) USING lead_id::text;")
    await c47.execute("ALTER TABLE source_attributions ALTER COLUMN lead_id SET NOT NULL;")
    v47 = await c47.fetchval("SELECT version_num FROM alembic_version;")
    await c47.close()
    print(f"rc_disposable_0047 set to: {v47}")

    # Set rc_disposable_0048 to genuine 0048 schema
    c48 = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/rc_disposable_0048")
    await c48.execute("UPDATE alembic_version SET version_num = '0048_schema_reconciliation_parity';")
    await c48.execute("ALTER TABLE source_attributions DROP CONSTRAINT IF EXISTS fk_source_attributions_lead_id;")
    await c48.execute("ALTER TABLE source_attributions DROP CONSTRAINT IF EXISTS fk_source_attributions_organization_id;")
    await c48.execute("ALTER TABLE source_attributions ALTER COLUMN organization_id TYPE character varying(36) USING organization_id::text;")
    await c48.execute("ALTER TABLE source_attributions ALTER COLUMN lead_id TYPE character varying(36) USING lead_id::text;")
    await c48.execute("ALTER TABLE source_attributions ALTER COLUMN lead_id SET NOT NULL;")
    v48 = await c48.fetchval("SELECT version_num FROM alembic_version;")
    await c48.close()
    print(f"rc_disposable_0048 set to: {v48}")

    # Upgrade rc_disposable_0050 to 0050 using release_migration.py locally
    res = subprocess.run([
        sys.executable, "apps/api/scripts/release_migration.py",
        "--db-url", "postgresql://postgres:postgres@127.0.0.1:5432/rc_disposable_0050"
    ], capture_output=True, text=True)
    assert res.returncode == 0, f"Setup upgrade failed: {res.stderr}"
    c50 = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/rc_disposable_0050")
    v50 = await c50.fetchval("SELECT version_num FROM alembic_version;")
    await c50.close()
    print(f"rc_disposable_0050 set to: {v50}")

async def run_tests():
    await setup_disposable_dbs()
    print("\n--- Running Container Runtime Contract Tests ---")

    # Test 1: Container deployed startup on revision 0047 must fail closed without DDL
    print("\n[Scenario 1] Container deployed startup on revision 0047 fails closed")
    cmd1 = [
        "docker", "run", "--rm",
        "--network", NETWORK,
        "-e", "ENV=production",
        "-e", f"DATABASE_URL=postgresql://postgres:postgres@{CONTAINER_PG_HOST}:5432/rc_disposable_0047",
        "-e", "SECRET_KEY=test_production_secret_key_12345",
        "-e", "SUPABASE_JWT_SECRET=test_jwt_secret_12345",
        "-e", "DRY_RUN_VALIDATION_ONLY=true",
        IMAGE_TAG
    ]
    res1 = subprocess.run(cmd1, capture_output=True, text=True)
    c47 = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/rc_disposable_0047")
    rev47_after = await c47.fetchval("SELECT version_num FROM alembic_version")
    await c47.close()

    p1 = (res1.returncode == 1 and 
          "Deployed database revision mismatch" in res1.stdout and 
          "Found database revision:     0047_webhook_event_claims" in res1.stdout and
          rev47_after == "0047_webhook_event_claims")
    record("Container_Runtime_1A_Prod_At_0047_Fails_Closed", p1, {
        "rc": res1.returncode, "rev_after": rev47_after, "stdout": res1.stdout
    })

    # Test 2: Container deployed startup on revision 0048 must fail closed without DDL
    print("\n[Scenario 2] Container deployed startup on revision 0048 fails closed")
    cmd2 = [
        "docker", "run", "--rm",
        "--network", NETWORK,
        "-e", "ENV=production",
        "-e", f"DATABASE_URL=postgresql://postgres:postgres@{CONTAINER_PG_HOST}:5432/rc_disposable_0048",
        "-e", "SECRET_KEY=test_production_secret_key_12345",
        "-e", "SUPABASE_JWT_SECRET=test_jwt_secret_12345",
        "-e", "DRY_RUN_VALIDATION_ONLY=true",
        IMAGE_TAG
    ]
    res2 = subprocess.run(cmd2, capture_output=True, text=True)
    c48 = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/rc_disposable_0048")
    rev48_after = await c48.fetchval("SELECT version_num FROM alembic_version")
    await c48.close()

    p2 = (res2.returncode == 1 and 
          "Deployed database revision mismatch" in res2.stdout and 
          "Found database revision:     0048_schema_reconciliation_parity" in res2.stdout and
          rev48_after == "0048_schema_reconciliation_parity")
    record("Container_Runtime_1B_Prod_At_0048_Fails_Closed", p2, {
        "rc": res2.returncode, "rev_after": rev48_after, "stdout": res2.stdout
    })

    # Test 3: Normal startup must never execute migrations even if RUN_MIGRATIONS_ON_STARTUP=true
    print("\n[Scenario 3] Container rejects RUN_MIGRATIONS_ON_STARTUP=true")
    cmd3 = [
        "docker", "run", "--rm",
        "--network", NETWORK,
        "-e", "ENV=production",
        "-e", f"DATABASE_URL=postgresql://postgres:postgres@{CONTAINER_PG_HOST}:5432/rc_disposable_0050",
        "-e", "SECRET_KEY=test_production_secret_key_12345",
        "-e", "SUPABASE_JWT_SECRET=test_jwt_secret_12345",
        "-e", "RUN_MIGRATIONS_ON_STARTUP=true",
        IMAGE_TAG
    ]
    res3 = subprocess.run(cmd3, capture_output=True, text=True)
    p3 = (res3.returncode == 1 and "RUN_MIGRATIONS_ON_STARTUP=true is rejected" in res3.stdout)
    record("Container_Runtime_1C_Reject_Startup_Migrations", p3, {
        "rc": res3.returncode, "stdout": res3.stdout
    })

    # Test 4: Container deployed startup on revision 0050 succeeds
    print("\n[Scenario 4] Container deployed startup on revision 0050 succeeds")
    cmd4 = [
        "docker", "run", "--rm",
        "--network", NETWORK,
        "-e", "ENV=production",
        "-e", f"DATABASE_URL=postgresql://postgres:postgres@{CONTAINER_PG_HOST}:5432/rc_disposable_0050",
        "-e", "SECRET_KEY=test_production_secret_key_12345",
        "-e", "SUPABASE_JWT_SECRET=test_jwt_secret_12345",
        "-e", "DRY_RUN_VALIDATION_ONLY=true",
        IMAGE_TAG
    ]
    res4 = subprocess.run(cmd4, capture_output=True, text=True)
    p4 = (res4.returncode == 0 and 
          "Schema verified at required head '0050_broker_subscription_constraint_parity'" in res4.stdout)
    record("Container_Runtime_1D_Prod_At_0050_Succeeds", p4, {
        "rc": res4.returncode, "stdout": res4.stdout
    })

    # Test 5: Dedicated migration runner inside container upgrades 0047 -> 0050 via secure TARGET_DATABASE_URL
    print("\n[Scenario 5] Dedicated migration runner inside container upgrades rc_disposable_0047 to 0050 via TARGET_DATABASE_URL")
    cmd5 = [
        "docker", "run", "--rm",
        "--network", NETWORK,
        "-e", f"TARGET_DATABASE_URL=postgresql://postgres:postgres@{CONTAINER_PG_HOST}:5432/rc_disposable_0047",
        IMAGE_TAG,
        "python", "/app/scripts/release_migration.py"
    ]
    res5 = subprocess.run(cmd5, capture_output=True, text=True)
    c47_mig = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/rc_disposable_0047")
    rev47_final = await c47_mig.fetchval("SELECT version_num FROM alembic_version")
    await c47_mig.close()

    p5 = (res5.returncode == 0 and 
          rev47_final == "0050_broker_subscription_constraint_parity" and
          ("MIGRATION_SUCCESSFUL" in res5.stdout or "RELEASE MIGRATION SUCCESSFUL" in res5.stderr))
    record("Container_Runtime_1E_Dedicated_Runner_Upgrades_0047_To_0050", p5, {
        "rc": res5.returncode, "final_rev": rev47_final, "stdout": res5.stdout
    })

    # Test 6: Dedicated migration runner inside container returns safe NO-OP on 0050 via TARGET_DATABASE_URL
    print("\n[Scenario 6] Dedicated migration runner inside container returns safe NO-OP on 0050 via TARGET_DATABASE_URL")
    cmd6 = [
        "docker", "run", "--rm",
        "--network", NETWORK,
        "-e", f"TARGET_DATABASE_URL=postgresql://postgres:postgres@{CONTAINER_PG_HOST}:5432/rc_disposable_0047",
        IMAGE_TAG,
        "python", "/app/scripts/release_migration.py"
    ]
    res6 = subprocess.run(cmd6, capture_output=True, text=True)
    p6 = (res6.returncode == 0 and "ALREADY_AT_HEAD" in res6.stdout)
    record("Container_Runtime_1F_Dedicated_Runner_Safe_NoOp_At_0050", p6, {
        "rc": res6.returncode, "stdout": res6.stdout
    })

    # Test 7: Dedicated migration runner inside container rejects port 6543 via TARGET_DATABASE_URL
    print("\n[Scenario 7] Dedicated migration runner inside container rejects port 6543 via TARGET_DATABASE_URL")
    cmd7 = [
        "docker", "run", "--rm",
        "--network", NETWORK,
        "-e", f"TARGET_DATABASE_URL=postgresql://postgres:postgres@{CONTAINER_PG_HOST}:6543/rc_disposable_0047",
        IMAGE_TAG,
        "python", "/app/scripts/release_migration.py"
    ]
    res7 = subprocess.run(cmd7, capture_output=True, text=True)
    p7 = (res7.returncode == 1 and "port 6543 detected" in res7.stderr)
    record("Container_Runtime_1G_Reject_Port_6543_Via_Target_Env", p7, {
        "rc": res7.returncode, "stderr": res7.stderr
    })

    # Summary
    all_passed = all(r["status"] == "PASSED" for r in RESULTS.values())
    print("\n==================================================================")
    print(f"CONTAINER RUNTIME VERIFICATION SUMMARY: {'ALL PASSED' if all_passed else 'FAILURES OCCURRED'}")
    print(f"Total scenarios: {len(RESULTS)}, Passed: {sum(1 for r in RESULTS.values() if r['status'] == 'PASSED')}")
    print("==================================================================")

    ledger_path = os.path.abspath("scratch/release_candidate_container_runtime_ledger.json")
    with open(ledger_path, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"Results written to: {ledger_path}")

    # Clean up disposable dbs
    conn_clean = await asyncpg.connect(PG_URL)
    for db in ["rc_disposable_0047", "rc_disposable_0048", "rc_disposable_0050"]:
        await conn_clean.execute(f"DROP DATABASE IF EXISTS {db};")
    await conn_clean.close()

    if not all_passed:
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(run_tests())

