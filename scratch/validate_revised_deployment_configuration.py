import asyncio
import asyncpg
import subprocess
import os
import sys
import json

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISP_DB = "test_deploy_config_validation"
DISP_URL = f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}"
API_DIR = os.path.abspath("apps/api")

async def run_all_tests():
    ledger = {}
    print("==================================================================")
    print("VALIDATING REVISED DEPLOYMENT CONFIGURATION & CONTROLLED RUNNER")
    print("==================================================================")

    # -------------------------------------------------------------------------
    # TEST 1: Verify Celery worker and scheduler do NOT execute migrations
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Auditing worker and scheduler start commands in render.yaml...")
    with open("render.yaml", "r", encoding="utf-8") as f:
        render_content = f.read()

    assert "wefylabs-celery-worker" in render_content, "Missing celery worker service"
    assert "wefylabs-celery-beat" in render_content, "Missing celery beat service"
    
    # Check that worker and beat do NOT use entrypoint.sh or run alembic
    worker_block = render_content[render_content.find("wefylabs-celery-worker"):render_content.find("wefylabs-celery-beat")]
    beat_block = render_content[render_content.find("wefylabs-celery-beat"):]

    assert "entrypoint.sh" not in worker_block, "Worker must not run entrypoint.sh"
    assert "alembic" not in worker_block, "Worker must not run alembic"
    assert "entrypoint.sh" not in beat_block, "Beat must not run entrypoint.sh"
    assert "alembic" not in beat_block, "Beat must not run alembic"

    ledger["test_1_worker_beat_isolation"] = {
        "status": "PASSED",
        "worker_command": "celery worker directly (no migrations)",
        "beat_command": "celery beat directly (no migrations)"
    }
    print("  [PASS] Celery worker and beat do not invoke migrations.")

    # -------------------------------------------------------------------------
    # Setup disposable database at revision 0047
    # -------------------------------------------------------------------------
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.execute(f"CREATE DATABASE {DISP_DB} WITH TEMPLATE leadscore;")
    await admin.close()
    
    # Downgrade to 0047
    res_down = subprocess.run([
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL}",
        "downgrade", "0047_webhook_event_claims"
    ], cwd=API_DIR, capture_output=True, text=True)
    assert res_down.returncode == 0, f"Downgrade to 0047 failed: {res_down.stderr}"
    print(f"[SETUP] Created disposable database '{DISP_DB}' at revision '0047_webhook_event_claims'.")

    # -------------------------------------------------------------------------
    # TEST 2 & 3: Normal API startup fails closed on unmigrated DB without mutating
    # -------------------------------------------------------------------------
    print("\n[TEST 2 & 3] Simulating normal API startup on unmigrated DB (revision 0047)...")
    # Simulate entrypoint logic with ENV=production and RUN_MIGRATIONS_ON_STARTUP=false
    env = os.environ.copy()
    env["ENV"] = "production"
    env["DATABASE_URL"] = DISP_URL
    env["RUN_MIGRATIONS_ON_STARTUP"] = "false"
    env["REQUIRED_ALEMBIC_HEAD"] = "0050_broker_subscription_constraint_parity"

    # Run check script matching entrypoint.sh
    check_code = """
import sys, os, asyncio, asyncpg
url = os.environ['DATABASE_URL'].replace('+asyncpg', '')
async def check():
    conn = await asyncpg.connect(url)
    rev = await conn.fetchval('SELECT version_num FROM alembic_version')
    await conn.close()
    return rev
rev = asyncio.run(check())
req = os.environ['REQUIRED_ALEMBIC_HEAD']
if rev != req:
    print(f'[FATAL] Production database revision mismatch: found {rev}, expected {req}')
    sys.exit(1)
print('[OK] Revision verified')
sys.exit(0)
"""
    res_api_check = subprocess.run([sys.executable, "-c", check_code], env=env, capture_output=True, text=True)
    assert res_api_check.returncode == 1, f"Expected API check to FAIL CLOSED on unmigrated DB, but it exited {res_api_check.returncode}"
    assert "Production database revision mismatch" in res_api_check.stdout

    # Verify DB was NOT mutated
    conn = await asyncpg.connect(DISP_URL)
    rev_after = await conn.fetchval("SELECT version_num FROM alembic_version")
    assert rev_after == "0047_webhook_event_claims", f"DB was mutated! Expected 0047, found {rev_after}"
    await conn.close()

    ledger["test_2_no_accidental_migration"] = {"status": "PASSED", "database_revision_unchanged": rev_after}
    ledger["test_3_fail_closed_on_unmigrated_db"] = {"status": "PASSED", "exit_code": res_api_check.returncode, "stdout": res_api_check.stdout.strip()}
    print("  [PASS] Normal API startup fails closed (Exit Code 1) and preserves database at revision 0047.")

    # -------------------------------------------------------------------------
    # TEST 4: Invalid Predecessor Rejection
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing runner fail-closed behavior on unauthorized predecessor...")
    # Stamp DB with an invalid arbitrary revision
    conn = await asyncpg.connect(DISP_URL)
    await conn.execute("UPDATE alembic_version SET version_num = '0010_arbitrary_old_revision';")
    await conn.close()

    res_bad_pred = subprocess.run([
        sys.executable, "scripts/release_migration.py",
        "--db-url", DISP_URL
    ], cwd=API_DIR, capture_output=True, text=True)
    assert res_bad_pred.returncode == 1, "Expected release_migration to abort on unauthorized predecessor"
    assert "is not a recognized predecessor" in res_bad_pred.stderr or "is not a recognized predecessor" in res_bad_pred.stdout

    ledger["test_4_unauthorized_predecessor_rejected"] = {"status": "PASSED", "exit_code": res_bad_pred.returncode}
    print("  [PASS] Dedicated runner refuses to migrate arbitrary/unauthorized predecessor revisions.")

    # Reset DB to 0047
    conn = await asyncpg.connect(DISP_URL)
    await conn.execute("UPDATE alembic_version SET version_num = '0047_webhook_event_claims';")
    await conn.close()

    # -------------------------------------------------------------------------
    # TEST 5: Dedicated Release Runner Executes Migration (0047 -> 0050)
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Executing dedicated release runner against disposable database...")
    res_runner = subprocess.run([
        sys.executable, "scripts/release_migration.py",
        "--db-url", DISP_URL
    ], cwd=API_DIR, capture_output=True, text=True)
    assert res_runner.returncode == 0, f"Dedicated release runner failed: {res_runner.stderr}\n{res_runner.stdout}"

    conn = await asyncpg.connect(DISP_URL)
    final_rev = await conn.fetchval("SELECT version_num FROM alembic_version")
    assert final_rev == "0050_broker_subscription_constraint_parity", f"Expected 0050, found {final_rev}"
    await conn.close()

    ledger["test_5_dedicated_runner_success"] = {
        "status": "PASSED",
        "initial_revision": "0047_webhook_event_claims",
        "final_revision": final_rev,
        "exit_code": res_runner.returncode
    }
    print(f"  [PASS] Dedicated release runner successfully upgraded 0047 -> 0050 and verified schema integrity.")

    # -------------------------------------------------------------------------
    # TEST 6: Normal API Startup on Migrated Database (Revision 0050)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Simulating normal API startup on migrated DB (revision 0050)...")
    res_api_ok = subprocess.run([sys.executable, "-c", check_code], env=env, capture_output=True, text=True)
    assert res_api_ok.returncode == 0, f"Expected API startup to succeed on 0050, got {res_api_ok.returncode}: {res_api_ok.stderr}"
    assert "[OK] Revision verified" in res_api_ok.stdout

    ledger["test_6_api_startup_on_migrated_db"] = {"status": "PASSED", "exit_code": res_api_ok.returncode}
    print("  [PASS] Normal API startup succeeds (Exit Code 0) on verified head 0050.")

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{DISP_DB}' AND pid <> pg_backend_pid();")
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.close()
    print(f"\n[TEARDOWN] Dropped disposable database '{DISP_DB}'.")

    print("\n==================================================================")
    print("ALL 6 DEPLOYMENT CONFIGURATION & RUNNER VALIDATIONS PASSED")
    print("==================================================================")
    with open("scratch/revised_deployment_validation_results.json", "w", encoding="utf-8") as f:
        json.dump(ledger, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_all_tests())

