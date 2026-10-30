"""
Scratch script: test_release_invariant_hardening.py
Validates every invariant required by WEFYLABS — FINAL RELEASE INVARIANT HARDENING:
1. Environment classification & fail-closed gate (entrypoint.sh logic).
2. Dedicated release migration runner safety (release_migration.py invariants).
3. Backup, catalog, and isolated restore rehearsal using libpq env injection.
4. Health check contract (/health/live, /health/ready, /health/deep with migration_head).
5. Celery Worker and Beat isolation.
"""
import sys
import os
import json
import asyncio
import subprocess
from urllib.parse import urlparse

# Set working dir & sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_ROOT = os.path.join(REPO_ROOT, "apps", "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

import asyncpg
from dotenv import load_dotenv
load_dotenv(os.path.join(REPO_ROOT, ".env"), override=False)
load_dotenv(os.path.join(API_ROOT, ".env"), override=False)

# Use local Docker PostgreSQL for all disposable test databases
PG_HOST = "127.0.0.1"
PG_PORT = 5432
PG_USER = "postgres"
PG_PASSWORD = "postgres"
BASE_PG_URL = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/postgres"

RESULTS = {}


GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
if not os.path.exists(GIT_BASH):
    GIT_BASH = "bash"


def log_test(name, passed, details=None):
    status = "PASSED" if passed else "FAILED"
    print(f"[{status}] {name}")
    if details:
        print(f"   -> {details}")
    RESULTS[name] = {"status": status, "details": details or {}}


async def recreate_disposable_db(dbname: str, template: str = None):
    admin_conn = await asyncpg.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, database="postgres")
    try:
        await admin_conn.execute(f"""
            SELECT pg_terminate_backend(pid) 
            FROM pg_stat_activity 
            WHERE datname = '{dbname}' AND pid <> pg_backend_pid()
        """)
        await admin_conn.execute(f"DROP DATABASE IF EXISTS {dbname}")
        if template:
            await admin_conn.execute(f"CREATE DATABASE {dbname} WITH TEMPLATE {template}")
        else:
            await admin_conn.execute(f"CREATE DATABASE {dbname}")
    finally:
        await admin_conn.close()


async def set_db_revision(dbname: str, revision: str, multi_rows: list = None):
    conn = await asyncpg.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, database=dbname)
    try:
        await conn.execute("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(128) NOT NULL)")
        await conn.execute("DELETE FROM alembic_version")
        if multi_rows:
            for r in multi_rows:
                await conn.execute("INSERT INTO alembic_version (version_num) VALUES ($1)", r)
        else:
            await conn.execute("INSERT INTO alembic_version (version_num) VALUES ($1)", revision)
    finally:
        await conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# 1. Environment Classification & Fail-Closed Gate Tests
# ─────────────────────────────────────────────────────────────────────────────

def simulate_entrypoint(env_val=None, run_mig_val=None, db_url=None):
    """
    Executes entrypoint.sh directly using bash with custom environment variables.
    """
    env = os.environ.copy()
    if env_val is not None:
        env["ENV"] = env_val
    else:
        env.pop("ENV", None)

    if run_mig_val is not None:
        env["RUN_MIGRATIONS_ON_STARTUP"] = run_mig_val
    else:
        env.pop("RUN_MIGRATIONS_ON_STARTUP", None)

    if db_url is not None:
        env["DATABASE_URL"] = db_url

    env["SECRET_KEY"] = "test_secret_key_at_least_32_bytes_long_123456"
    env["SUPABASE_JWT_SECRET"] = "test_supabase_jwt_secret_32_bytes_len"
    env["PORT"] = "9999"
    env["DRY_RUN_VALIDATION_ONLY"] = "true"

    entrypoint_path = os.path.join(API_ROOT, "entrypoint.sh").replace("\\", "/")
    cmd = [GIT_BASH, entrypoint_path]

    res = subprocess.run(cmd, cwd=API_ROOT, env=env, capture_output=True, text=True, timeout=15)
    output = (res.stdout + "\n" + res.stderr).strip()
    return res.returncode, output, res.stderr.strip()


async def run_environment_gate_tests():
    dbname = "test_disposable_env_gate"
    await recreate_disposable_db(dbname)
    test_db_url = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{dbname}"

    # 1A: Absent ENV
    rc, out, _ = simulate_entrypoint(env_val=None, db_url=test_db_url)
    log_test("ENV_Gate_1A_Absent_ENV", rc == 1 and "environment variable 'ENV' is" in out, {"rc": rc, "out": out})

    # 1B: Empty ENV
    rc, out, _ = simulate_entrypoint(env_val="", db_url=test_db_url)
    log_test("ENV_Gate_1B_Empty_ENV", rc == 1 and "environment variable 'ENV' is" in out, {"rc": rc, "out": out})

    # 1C: Malformed / Unrecognized ENV
    rc, out, _ = simulate_entrypoint(env_val="staging_custom_123", db_url=test_db_url)
    log_test("ENV_Gate_1C_Malformed_ENV", rc == 1 and "[FATAL] Invalid or unrecognized environment" in out, {"rc": rc, "out": out})

    # 1D: RUN_MIGRATIONS_ON_STARTUP=true rejected
    rc, out, _ = simulate_entrypoint(env_val="production", run_mig_val="true", db_url=test_db_url)
    log_test("ENV_Gate_1D_Reject_Startup_Migrations", rc == 1 and "[FATAL] RUN_MIGRATIONS_ON_STARTUP=true is rejected" in out, {"rc": rc, "out": out})

    # 1E: Production on 0047 fails closed
    await set_db_revision(dbname, "0047_webhook_event_claims")
    rc, out, _ = simulate_entrypoint(env_val="production", db_url=test_db_url)
    log_test("ENV_Gate_1E_Prod_At_0047_Fails_Closed", rc == 1 and "Deployed database revision mismatch" in out, {"rc": rc, "out": out})

    # 1F: Production on 0048 fails closed
    await set_db_revision(dbname, "0048_schema_reconciliation_parity")
    rc, out, _ = simulate_entrypoint(env_val="production", db_url=test_db_url)
    log_test("ENV_Gate_1F_Prod_At_0048_Fails_Closed", rc == 1 and "Deployed database revision mismatch" in out, {"rc": rc, "out": out})

    # 1G: Production on 0050 succeeds
    await set_db_revision(dbname, "0050_broker_subscription_constraint_parity")
    rc, out, _ = simulate_entrypoint(env_val="production", db_url=test_db_url)
    log_test("ENV_Gate_1G_Prod_At_0050_Succeeds", rc == 0 and "Schema verified" in out, {"rc": rc, "out": out})

    # 1H: Development succeeds
    await set_db_revision(dbname, "0047_webhook_event_claims")
    rc, out, _ = simulate_entrypoint(env_val="development", db_url=test_db_url)
    log_test("ENV_Gate_1H_Dev_Permissive", rc == 0 and "Non-production environment" in out, {"rc": rc, "out": out})


# ─────────────────────────────────────────────────────────────────────────────
# 2. Dedicated Single Migration Runner Invariant Tests
# ─────────────────────────────────────────────────────────────────────────────

async def run_migration_runner_invariants():
    runner_script = os.path.join(API_ROOT, "scripts", "release_migration.py")
    dbname = "test_disposable_runner_invariants"
    await recreate_disposable_db(dbname)
    test_db_url = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{dbname}"

    # 2A: Supabase pooler port 6543 detection
    port_6543_url = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:6543/{dbname}"
    res = subprocess.run([sys.executable, runner_script, "--db-url", port_6543_url, "--dry-run"], capture_output=True, text=True)
    log_test("Runner_2A_Reject_Port_6543_Transaction_Pooler", res.returncode == 1 and "Target port 6543 detected" in res.stderr, {"rc": res.returncode, "err": res.stderr[:200]})

    # 2B: Multiple heads in database alembic_version table
    await set_db_revision(dbname, "0047_webhook_event_claims", multi_rows=["0047_webhook_event_claims", "0048_schema_reconciliation_parity"])
    res = subprocess.run([sys.executable, runner_script, "--db-url", test_db_url, "--dry-run"], capture_output=True, text=True)
    log_test("Runner_2B_Reject_Multiple_Database_Heads", res.returncode == 1 and "Multiple revisions found in database" in res.stderr, {"rc": res.returncode, "err": res.stderr[:200]})

    # 2C: Unauthorized predecessor (e.g. 0030 or unknown)
    await set_db_revision(dbname, "0030_enterprise_runtime")
    res = subprocess.run([sys.executable, runner_script, "--db-url", test_db_url, "--dry-run"], capture_output=True, text=True)
    log_test("Runner_2C_Reject_Unauthorized_Predecessor", res.returncode == 1 and "not a recognized predecessor" in res.stderr, {"rc": res.returncode, "err": res.stderr[:200]})

    # 2D: Dry run on authorized predecessor (0047)
    # Clone from leadscore template and downgrade to 0047
    await recreate_disposable_db(dbname, template="leadscore")
    res_down = subprocess.run([
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={test_db_url}",
        "downgrade", "0047_webhook_event_claims"
    ], cwd=API_ROOT, capture_output=True, text=True)
    assert res_down.returncode == 0, f"Downgrade to 0047 failed: {res_down.stderr}"

    res = subprocess.run([sys.executable, runner_script, "--db-url", test_db_url, "--dry-run"], capture_output=True, text=True)
    log_test("Runner_2D_Dry_Run_Success", res.returncode == 0 and "DRY_RUN_PASSED" in res.stdout, {"rc": res.returncode, "out": res.stdout[:200]})

    # 2E: Migration execution from 0047 -> 0050
    res = subprocess.run([sys.executable, runner_script, "--db-url", test_db_url], capture_output=True, text=True)
    log_test("Runner_2E_Full_Migration_Execution_Success", res.returncode == 0 and "MIGRATION_SUCCESSFUL" in res.stdout, {"rc": res.returncode, "out": res.stdout[:200]})

    # 2F: Re-running runner when already at 0050 is safe NO-OP
    res = subprocess.run([sys.executable, runner_script, "--db-url", test_db_url], capture_output=True, text=True)
    log_test("Runner_2F_Already_At_0050_Safe_NoOp", res.returncode == 0 and "ALREADY_AT_HEAD" in res.stdout, {"rc": res.returncode, "out": res.stdout[:200]})

    # 2G: Wrong database endpoint / invalid credentials
    invalid_url = f"postgresql://{PG_USER}:wrong_password_999@{PG_HOST}:{PG_PORT}/{dbname}"
    res = subprocess.run([sys.executable, runner_script, "--db-url", invalid_url, "--dry-run"], capture_output=True, text=True)
    log_test("Runner_2G_Reject_Wrong_Credentials", res.returncode == 1, {"rc": res.returncode})


# ─────────────────────────────────────────────────────────────────────────────
# 3. Backup, Catalog, and Restore Verification Rehearsal (Libpq Env Injection)
# ─────────────────────────────────────────────────────────────────────────────

async def run_backup_and_restore_rehearsal():
    src_db = "test_disposable_backup_src"
    tgt_db = "test_disposable_restore_tgt"
    dump_file = os.path.join(REPO_ROOT, "scratch", "rehearsal_test_backup.dump")

    await recreate_disposable_db(src_db, template="leadscore")
    await recreate_disposable_db(tgt_db)

    # Migrate src_db to 0050
    runner_script = os.path.join(API_ROOT, "scripts", "release_migration.py")
    src_url = f"postgresql://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{src_db}"
    subprocess.run([sys.executable, runner_script, "--db-url", src_url], capture_output=True)

    # Insert sample records into src_db
    conn = await asyncpg.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, database=src_db)
    import uuid
    import datetime
    org_id = uuid.uuid4()
    broker_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    attr_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        await conn.execute("""
            INSERT INTO organizations (id, name, slug, plan, is_demo) 
            VALUES ($1, $2, $3, $4, $5)
        """, org_id, "Rehearsal Org", "rehearsal-org", "starter", False)

        await conn.execute("""
            INSERT INTO brokers (id, name, email, subscription_plan, subscription_status, is_demo) 
            VALUES ($1, $2, $3, $4, $5, $6)
        """, broker_id, "Rehearsal Broker", "broker@example.com", "starter_monthly", "active", False)

        await conn.execute("""
            INSERT INTO leads (id, organization_id, broker_id, email, phone) 
            VALUES ($1, $2, $3, $4, $5)
        """, lead_id, org_id, broker_id, "lead@example.com", "+1234567890")

        await conn.execute("""
            INSERT INTO source_attributions (id, organization_id, lead_id, channel, created_at) 
            VALUES ($1, $2, $3, $4, $5)
        """, attr_id, org_id, lead_id, "google_search", now)
    finally:
        await conn.close()

    # Record expected counts from src_db before dump
    conn_src = await asyncpg.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, database=src_db)
    src_lead_cnt = await conn_src.fetchval("SELECT COUNT(*) FROM leads")
    src_attr_cnt = await conn_src.fetchval("SELECT COUNT(*) FROM source_attributions")
    await conn_src.close()

    # Step 3A: pg_dump using environment injection via Docker container (no credentials in CLI args!)
    container_dump_file = f"/tmp/{src_db}.dump"
    cmd_dump = [
        "docker", "exec",
        "-e", f"PGPASSWORD={PG_PASSWORD}",
        "leadscore_postgres",
        "pg_dump", "-U", PG_USER, "-d", src_db, "-Fc", "--no-owner", "--no-privileges", f"--file={container_dump_file}"
    ]
    res_dump = subprocess.run(cmd_dump, capture_output=True, text=True)
    
    # Check container dump exists and has size
    check_size = subprocess.run(["docker", "exec", "leadscore_postgres", "stat", "-c", "%s", container_dump_file], capture_output=True, text=True)
    dump_size = int(check_size.stdout.strip()) if check_size.returncode == 0 and check_size.stdout.strip().isdigit() else 0
    dump_ok = (res_dump.returncode == 0 and dump_size > 1000)
    log_test("Backup_3A_pg_dump_Env_Injection", dump_ok, {"size_bytes": dump_size})

    # Step 3B: pg_restore -l (verify archive catalog)
    cmd_cat = ["docker", "exec", "leadscore_postgres", "pg_restore", "-l", container_dump_file]
    res_cat = subprocess.run(cmd_cat, capture_output=True, text=True)
    cat_ok = (res_cat.returncode == 0 and "source_attributions" in res_cat.stdout and "leads" in res_cat.stdout)
    log_test("Backup_3B_pg_restore_Catalog_Verification", cat_ok, {"catalog_lines": len(res_cat.stdout.splitlines())})

    # Step 3C: pg_restore to tgt_db using environment injection
    cmd_restore = [
        "docker", "exec",
        "-e", f"PGPASSWORD={PG_PASSWORD}",
        "leadscore_postgres",
        "pg_restore", "-U", PG_USER, "--clean", "--no-owner", "--no-privileges", "-d", tgt_db, container_dump_file
    ]
    res_restore = subprocess.run(cmd_restore, capture_output=True, text=True)
    # pg_restore returns 0 or warnings (e.g. if clean tries to drop non-existent objects)
    restore_ok = (res_restore.returncode in (0, 1))

    # Verify restored data and constraints
    conn_tgt = await asyncpg.connect(user=PG_USER, password=PG_PASSWORD, host=PG_HOST, port=PG_PORT, database=tgt_db)
    try:
        rev = await conn_tgt.fetchval("SELECT version_num FROM alembic_version")
        lead_cnt = await conn_tgt.fetchval("SELECT COUNT(*) FROM leads")
        attr_cnt = await conn_tgt.fetchval("SELECT COUNT(*) FROM source_attributions")
        data_match = (rev == "0050_broker_subscription_constraint_parity" and lead_cnt == src_lead_cnt and attr_cnt == src_attr_cnt)
    finally:
        await conn_tgt.close()

    log_test("Backup_3C_pg_restore_Integrity_Verification", restore_ok and data_match, {
        "restored_rev": rev,
        "leads_src": src_lead_cnt,
        "leads_restored": lead_cnt,
        "attributions_src": src_attr_cnt,
        "attributions_restored": attr_cnt
    })

    # Clean up dump file in container
    subprocess.run(["docker", "exec", "leadscore_postgres", "rm", "-f", container_dump_file], capture_output=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Health Check Contract Verification Tests
# ─────────────────────────────────────────────────────────────────────────────

def run_health_check_contract_tests(db_name: str):
    from fastapi.testclient import TestClient
    from app.config import settings
    import app.database as db_mod

    # Point to the verified local PostgreSQL database at revision 0050
    local_db_url = f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{db_name}"
    settings.DATABASE_URL = local_db_url
    settings.REDIS_URL = f"redis://{PG_HOST}:6379/0"
    
    # Recreate engine and sessionmaker with NullPool to prevent event loop connection bleeding across TestClient calls
    from sqlalchemy.pool import NullPool
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    db_mod.engine = create_async_engine(local_db_url, echo=False, poolclass=NullPool)
    db_mod.AsyncSessionLocal = async_sessionmaker(
        bind=db_mod.engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    from app.main import app
    client = TestClient(app)

    # 4A: /health/live and /health/liveness
    r_live = client.get("/health/live")
    r_liveness = client.get("/health/liveness")
    live_ok = (r_live.status_code == 200 and r_live.json().get("status") == "alive" and
               r_liveness.status_code == 200 and r_liveness.json().get("status") == "alive")
    log_test("Health_4A_Liveness_Endpoints", live_ok, {"live_json": r_live.json(), "liveness_json": r_liveness.json()})

    # 4B: /health/readiness and /health/ready
    r_ready = client.get("/health/readiness")
    r_ready_alias = client.get("/health/ready")
    ready_ok = (r_ready.status_code == 200 and r_ready.json().get("status") == "ready" and
                r_ready.json().get("database") == "ok" and r_ready.json().get("cache") == "ok")
    log_test("Health_4B_Readiness_Endpoints", ready_ok, {"readiness_json": r_ready.json()})

    # 4C: /health/deep contains migration_head and system metrics
    r_deep = client.get("/health/deep")
    deep_json = r_deep.json()
    db_dep = deep_json.get("dependencies", {}).get("database", {})
    deep_ok = (r_deep.status_code == 200 and "status" in deep_json and
               db_dep.get("status") == "ok" and db_dep.get("migration_head") == "0050_broker_subscription_constraint_parity")
    log_test("Health_4C_Deep_Health_Migration_Contract", deep_ok, {
        "status": deep_json.get("status"),
        "db_status": db_dep.get("status"),
        "migration_head": db_dep.get("migration_head")
    })

    # 4D: Intentional Health Failure (unreachable database returns 503)
    db_mod.engine = create_async_engine(f"postgresql+asyncpg://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/nonexistent_db_fail", echo=False, poolclass=NullPool)
    db_mod.AsyncSessionLocal = async_sessionmaker(bind=db_mod.engine, class_=AsyncSession, expire_on_commit=False)
    r_fail = client.get("/health/readiness")
    r_deep_fail = client.get("/health/deep")
    fail_ok = (r_fail.status_code == 503 and r_fail.json().get("status") == "not_ready" and
               r_deep_fail.json().get("dependencies", {}).get("database", {}).get("status") == "error")
    log_test("Health_4D_Readiness_Fails_Closed_On_DB_Error", fail_ok, {
        "status_code": r_fail.status_code,
        "readiness_json": r_fail.json(),
        "deep_db_status": r_deep_fail.json().get("dependencies", {}).get("database", {}).get("status")
    })


# ─────────────────────────────────────────────────────────────────────────────
# 5. Celery Worker and Beat Isolation
# ─────────────────────────────────────────────────────────────────────────────

def run_worker_beat_isolation_test():
    import yaml
    with open(os.path.join(REPO_ROOT, "render.yaml"), "r") as f:
        config = yaml.safe_load(f)

    services = {s["name"]: s for s in config.get("services", [])}
    worker = services.get("wefylabs-celery-worker", {})
    beat = services.get("wefylabs-celery-beat", {})

    worker_cmd = worker.get("startCommand", "")
    beat_cmd = beat.get("startCommand", "")

    worker_pure = ("celery" in worker_cmd and "alembic" not in worker_cmd and "entrypoint" not in worker_cmd)
    beat_pure = ("celery" in beat_cmd and "alembic" not in beat_cmd and "entrypoint" not in beat_cmd)

    log_test("Isolation_5A_Worker_Beat_No_Migrations", worker_pure and beat_pure, {
        "worker_cmd": worker_cmd[:60] + "...",
        "beat_cmd": beat_cmd[:60] + "..."
    })


# ─────────────────────────────────────────────────────────────────────────────
# Main Rehearsal Runner
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("==================================================================")
    print("WEFYLABS FINAL RELEASE INVARIANT REHEARSAL & VERIFICATION")
    print("==================================================================")

    print("\n--- Phase 1: Environment Classification & Fail-Closed Gate ---")
    await run_environment_gate_tests()

    print("\n--- Phase 2: Dedicated Single Migration Runner Invariants ---")
    await run_migration_runner_invariants()

    print("\n--- Phase 3: Backup, Catalog, and Restore Rehearsal ---")
    await run_backup_and_restore_rehearsal()

    print("\n--- Phase 4: Health Check Contract Verification ---")
    run_health_check_contract_tests("test_disposable_restore_tgt")

    print("\n--- Phase 5: Celery Worker & Beat Isolation ---")
    run_worker_beat_isolation_test()

    print("\n==================================================================")
    all_passed = all(v["status"] == "PASSED" for v in RESULTS.values())
    passed_count = sum(1 for v in RESULTS.values() if v["status"] == "PASSED")
    total_count = len(RESULTS)
    print(f"SUMMARY: {passed_count}/{total_count} INVARIANT REHEARSAL TESTS PASSED")
    print("==================================================================")

    out_file = os.path.join(REPO_ROOT, "scratch", "release_invariant_rehearsal_results.json")
    with open(out_file, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"Detailed ledger written to: {out_file}")

    if not all_passed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
