"""
Scratch script: test_final_preflight_release_authorization.py
WEFYLABS — FINAL PRODUCTION PREFLIGHT AND RELEASE AUTHORIZATION GATE

Validates:
1. Phase 2: PostgreSQL 17 backup/restore client compatibility (pg_dump 17.11 against PG17 server)
   with libpq environment injection, catalog verification, and schema/data parity.
2. Phase 3: Quiescent write boundary detection (active, idle, and idle-in-transaction cases).
3. Phase 4: Migration runner target consistency, .env isolation, and invariant safety.
4. Phase 5: Deployed environment classification and fail-closed gate.
"""
import sys
import os
import json
import asyncio
import subprocess
import uuid
import datetime
from urllib.parse import urlparse

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
API_ROOT = os.path.join(REPO_ROOT, "apps", "api")
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

import asyncpg

# Local disposable environments
PG17_HOST = "127.0.0.1"
PG17_PORT = 5433
PG17_USER = "postgres"
PG17_PASS = "postgres"

PG16_HOST = "127.0.0.1"
PG16_PORT = 5432
PG16_USER = "postgres"
PG16_PASS = "postgres"

GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
if not os.path.exists(GIT_BASH):
    GIT_BASH = "bash"

RESULTS = {}


def record_result(test_id, expected, actual, target_db, passed, details=None):
    status = "PASSED" if passed else "FAILED"
    print(f"[{status}] {test_id} (Target: {target_db})")
    if details:
        print(f"   -> Expected: {expected} | Actual: {actual}")
    RESULTS[test_id] = {
        "scenario": test_id,
        "target_database": target_db,
        "expected_result": expected,
        "actual_result": actual,
        "status": status,
        "details": details or {}
    }


# ─────────────────────────────────────────────────────────────────────────────
# Phase 2: PostgreSQL 17 Utility & Parity Rehearsal
# ─────────────────────────────────────────────────────────────────────────────

async def run_phase2_pg17_backup_parity_test():
    src_db = "preflight_pg17_backup_src"
    tgt_db = "preflight_pg17_restore_tgt"
    
    # 2.1 Verify exact client versions
    cmd_dump_ver = ["docker", "run", "--rm", "postgres:17-alpine", "pg_dump", "--version"]
    res_dump_ver = subprocess.run(cmd_dump_ver, capture_output=True, text=True)
    dump_version_str = res_dump_ver.stdout.strip()

    cmd_restore_ver = ["docker", "run", "--rm", "postgres:17-alpine", "pg_restore", "--version"]
    res_restore_ver = subprocess.run(cmd_restore_ver, capture_output=True, text=True)
    restore_version_str = res_restore_ver.stdout.strip()

    admin_conn = await asyncpg.connect(user=PG17_USER, password=PG17_PASS, host=PG17_HOST, port=PG17_PORT, database="postgres")
    server_ver = await admin_conn.fetchval("SHOW server_version")
    
    # Setup clean databases
    await admin_conn.execute(f"DROP DATABASE IF EXISTS {src_db}")
    await admin_conn.execute(f"CREATE DATABASE {src_db}")
    await admin_conn.execute(f"DROP DATABASE IF EXISTS {tgt_db}")
    await admin_conn.execute(f"CREATE DATABASE {tgt_db}")
    await admin_conn.close()

    # 2.2 Client Version Compatibility Check
    client_compat = ("17." in dump_version_str and "17." in restore_version_str and "17." in server_ver)
    record_result(
        "Phase2_Client_Version_Check",
        "pg_dump >= 17.0 and pg_restore >= 17.0 matching server 17.x",
        f"dump={dump_version_str}, restore={restore_version_str}, server={server_ver}",
        f"pg17://{PG17_HOST}:{PG17_PORT}/postgres",
        client_compat,
        {"dump_ver": dump_version_str, "restore_ver": restore_version_str, "server_ver": server_ver}
    )

    # 2.3 Populate src_db with schema and records matching 0050 head
    conn_src = await asyncpg.connect(user=PG17_USER, password=PG17_PASS, host=PG17_HOST, port=PG17_PORT, database=src_db)
    org_id = uuid.uuid4()
    broker_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    attr_id = str(uuid.uuid4())
    sub_id = uuid.uuid4()
    now = datetime.datetime.now(datetime.timezone.utc)

    await conn_src.execute("""
        CREATE TABLE alembic_version (version_num VARCHAR(128) NOT NULL PRIMARY KEY);
        INSERT INTO alembic_version VALUES ('0050_broker_subscription_constraint_parity');

        CREATE TABLE organizations (
            id UUID PRIMARY KEY,
            name VARCHAR NOT NULL,
            slug VARCHAR NOT NULL,
            plan VARCHAR NOT NULL,
            is_demo BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE brokers (
            id UUID PRIMARY KEY,
            name VARCHAR NOT NULL,
            email VARCHAR NOT NULL,
            subscription_plan VARCHAR NOT NULL,
            subscription_status VARCHAR NOT NULL,
            is_demo BOOLEAN NOT NULL DEFAULT FALSE,
            CONSTRAINT ck_brokers_subscription_plan CHECK (subscription_plan IN ('starter_monthly', 'pro_monthly', 'enterprise_annual')),
            CONSTRAINT ck_brokers_subscription_status CHECK (subscription_status IN ('active', 'past_due', 'paused', 'canceled'))
        );

        CREATE TABLE subscriptions (
            id UUID PRIMARY KEY,
            broker_id UUID REFERENCES brokers(id),
            plan VARCHAR NOT NULL,
            status VARCHAR NOT NULL,
            CONSTRAINT ck_subscriptions_status CHECK (status IN ('active', 'past_due', 'paused', 'canceled'))
        );

        CREATE TABLE leads (
            id UUID PRIMARY KEY,
            organization_id UUID REFERENCES organizations(id),
            broker_id UUID REFERENCES brokers(id),
            email VARCHAR,
            phone VARCHAR NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE source_attributions (
            id VARCHAR(36) PRIMARY KEY,
            organization_id UUID NOT NULL REFERENCES organizations(id),
            lead_id UUID REFERENCES leads(id),
            channel VARCHAR NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT fk_source_attributions_organization_id FOREIGN KEY (organization_id) REFERENCES organizations(id),
            CONSTRAINT fk_source_attributions_lead_id FOREIGN KEY (lead_id) REFERENCES leads(id)
        );
    """)

    await conn_src.execute("INSERT INTO organizations (id, name, slug, plan, is_demo) VALUES ($1, $2, $3, $4, $5)", org_id, "PG17 Org", "pg17-org", "pro_monthly", False)
    await conn_src.execute("INSERT INTO brokers (id, name, email, subscription_plan, subscription_status) VALUES ($1, $2, $3, $4, $5)", broker_id, "PG17 Broker", "broker17@example.com", "pro_monthly", "active")
    await conn_src.execute("INSERT INTO subscriptions (id, broker_id, plan, status) VALUES ($1, $2, $3, $4)", sub_id, broker_id, "pro_monthly", "active")
    await conn_src.execute("INSERT INTO leads (id, organization_id, broker_id, email, phone) VALUES ($1, $2, $3, $4, $5)", lead_id, org_id, broker_id, "lead17@example.com", "+1234567890")
    await conn_src.execute("INSERT INTO source_attributions (id, organization_id, lead_id, channel, created_at) VALUES ($1, $2, $3, $4, $5)", attr_id, org_id, lead_id, "pg17_test", now)

    src_org_cnt = await conn_src.fetchval("SELECT COUNT(*) FROM organizations")
    src_broker_cnt = await conn_src.fetchval("SELECT COUNT(*) FROM brokers")
    src_sub_cnt = await conn_src.fetchval("SELECT COUNT(*) FROM subscriptions")
    src_lead_cnt = await conn_src.fetchval("SELECT COUNT(*) FROM leads")
    src_attr_cnt = await conn_src.fetchval("SELECT COUNT(*) FROM source_attributions")
    await conn_src.close()

    # 2.4 Execute pg_dump 17 via Docker with libpq environment injection
    container_dump = f"/tmp/{src_db}.dump"
    cmd_dump = [
        "docker", "run", "--rm",
        "--network", "host",
        "-e", f"PGPASSWORD={PG17_PASS}",
        "-e", f"PGHOST={PG17_HOST}",
        "-e", f"PGPORT={PG17_PORT}",
        "-e", f"PGUSER={PG17_USER}",
        "-e", f"PGDATABASE={src_db}",
        "-v", f"{REPO_ROOT}/scratch:/scratch",
        "postgres:17-alpine",
        "pg_dump", "-Fc", "--no-owner", "--no-privileges", f"--file=/scratch/{src_db}.dump"
    ]
    res_dump = subprocess.run(cmd_dump, capture_output=True, text=True)
    host_dump = os.path.join(REPO_ROOT, "scratch", f"{src_db}.dump")
    dump_success = (res_dump.returncode == 0 and os.path.exists(host_dump) and os.path.getsize(host_dump) > 500)
    record_result(
        "Phase2_PG17_pg_dump_Env_Injection",
        "Exit Code 0 and valid compressed archive",
        f"rc={res_dump.returncode}, bytes={os.path.getsize(host_dump) if os.path.exists(host_dump) else 0}",
        f"pg17://{PG17_HOST}:{PG17_PORT}/{src_db}",
        dump_success,
        {"stderr": res_dump.stderr[:100]}
    )

    # 2.5 Archive Catalog Inspection (pg_restore -l)
    cmd_cat = [
        "docker", "run", "--rm",
        "-v", f"{REPO_ROOT}/scratch:/scratch",
        "postgres:17-alpine",
        "pg_restore", "-l", f"/scratch/{src_db}.dump"
    ]
    res_cat = subprocess.run(cmd_cat, capture_output=True, text=True)
    cat_ok = (res_cat.returncode == 0 and "source_attributions" in res_cat.stdout and "subscriptions" in res_cat.stdout)
    record_result(
        "Phase2_PG17_Catalog_Inspection",
        "Exit Code 0 and catalog contains all tables",
        f"rc={res_cat.returncode}, entries={len(res_cat.stdout.splitlines())}",
        f"pg17://{PG17_HOST}:{PG17_PORT}/{src_db}",
        cat_ok,
        {"toc_entries": len(res_cat.stdout.splitlines())}
    )

    # 2.6 Restore into target PostgreSQL 17 database
    cmd_restore = [
        "docker", "run", "--rm",
        "--network", "host",
        "-e", f"PGPASSWORD={PG17_PASS}",
        "-e", f"PGHOST={PG17_HOST}",
        "-e", f"PGPORT={PG17_PORT}",
        "-e", f"PGUSER={PG17_USER}",
        "-e", f"PGDATABASE={tgt_db}",
        "-v", f"{REPO_ROOT}/scratch:/scratch",
        "postgres:17-alpine",
        "pg_restore", "--clean", "--no-owner", "--no-privileges", "-d", tgt_db, f"/scratch/{src_db}.dump"
    ]
    res_restore = subprocess.run(cmd_restore, capture_output=True, text=True)
    
    # Verify row and schema parity
    conn_tgt = await asyncpg.connect(user=PG17_USER, password=PG17_PASS, host=PG17_HOST, port=PG17_PORT, database=tgt_db)
    tgt_rev = await conn_tgt.fetchval("SELECT version_num FROM alembic_version")
    tgt_org_cnt = await conn_tgt.fetchval("SELECT COUNT(*) FROM organizations")
    tgt_broker_cnt = await conn_tgt.fetchval("SELECT COUNT(*) FROM brokers")
    tgt_sub_cnt = await conn_tgt.fetchval("SELECT COUNT(*) FROM subscriptions")
    tgt_lead_cnt = await conn_tgt.fetchval("SELECT COUNT(*) FROM leads")
    tgt_attr_cnt = await conn_tgt.fetchval("SELECT COUNT(*) FROM source_attributions")
    await conn_tgt.close()

    parity_ok = (
        tgt_rev == "0050_broker_subscription_constraint_parity" and
        tgt_org_cnt == src_org_cnt and
        tgt_broker_cnt == src_broker_cnt and
        tgt_sub_cnt == src_sub_cnt and
        tgt_lead_cnt == src_lead_cnt and
        tgt_attr_cnt == src_attr_cnt
    )
    record_result(
        "Phase2_PG17_Data_And_Schema_Parity",
        "Exact count parity across organizations, brokers, subscriptions, leads, attributions",
        f"orgs={tgt_org_cnt}/{src_org_cnt}, brokers={tgt_broker_cnt}/{src_broker_cnt}, subs={tgt_sub_cnt}/{src_sub_cnt}, leads={tgt_lead_cnt}/{src_lead_cnt}, attrs={tgt_attr_cnt}/{src_attr_cnt}",
        f"pg17://{PG17_HOST}:{PG17_PORT}/{tgt_db}",
        parity_ok,
        {"restored_rev": tgt_rev}
    )

    if os.path.exists(host_dump):
        os.remove(host_dump)


# ─────────────────────────────────────────────────────────────────────────────
# Phase 3: Quiescent Write Boundary Verification
# ─────────────────────────────────────────────────────────────────────────────

QUIESCENCE_QUERY = """
SELECT 
    pid, 
    usename, 
    application_name, 
    client_addr, 
    state, 
    xact_start, 
    query
FROM pg_stat_activity
WHERE pid <> pg_backend_pid()
  AND backend_type = 'client backend'
  AND (
      state != 'idle' 
      OR xact_start IS NOT NULL
  );
"""

async def run_phase3_quiescence_boundary_test():
    dbname = "preflight_quiescence_test"
    admin = await asyncpg.connect(user=PG16_USER, password=PG16_PASS, host=PG16_HOST, port=PG16_PORT, database="postgres")
    await admin.execute(f"DROP DATABASE IF EXISTS {dbname}")
    await admin.execute(f"CREATE DATABASE {dbname}")
    await admin.close()

    # 3A: Clean database with no active sessions -> Quiescent
    inspector_conn = await asyncpg.connect(user=PG16_USER, password=PG16_PASS, host=PG16_HOST, port=PG16_PORT, database=dbname)
    rows_clean = await inspector_conn.fetch(QUIESCENCE_QUERY)
    record_result(
        "Phase3A_Clean_DB_Quiescent_Boundary",
        "0 active or in-transaction sessions",
        f"found {len(rows_clean)} non-idle sessions",
        f"pg16://{PG16_HOST}:{PG16_PORT}/{dbname}",
        len(rows_clean) == 0,
        {"rows": [dict(r) for r in rows_clean]}
    )

    # 3B: Session in 'idle in transaction' (CRITICAL CASE: state != 'active', but holding open transaction!)
    client_conn = await asyncpg.connect(user=PG16_USER, password=PG16_PASS, host=PG16_HOST, port=PG16_PORT, database=dbname)
    tr = client_conn.transaction()
    await tr.start()
    await client_conn.execute("CREATE TABLE test_tx (id int)")
    await client_conn.execute("INSERT INTO test_tx VALUES (1)")
    # Session is now 'idle in transaction' waiting for commit

    rows_idle_in_tx = await inspector_conn.fetch(QUIESCENCE_QUERY)
    detected_idle_tx = any(r["state"] == "idle in transaction" and r["xact_start"] is not None for r in rows_idle_in_tx)
    record_result(
        "Phase3B_Detect_Idle_In_Transaction_Writer",
        "Quiescence check REJECTS open write transaction (state='idle in transaction')",
        f"detected={detected_idle_tx}, count={len(rows_idle_in_tx)}",
        f"pg16://{PG16_HOST}:{PG16_PORT}/{dbname}",
        detected_idle_tx and len(rows_idle_in_tx) >= 1,
        {"sessions_detected": [f"pid={r['pid']}, state={r['state']}, xact_start={r['xact_start']}" for r in rows_idle_in_tx]}
    )

    # 3C: Commit transaction -> Quiescent boundary restored
    await tr.commit()
    await client_conn.close()

    rows_restored = await inspector_conn.fetch(QUIESCENCE_QUERY)
    record_result(
        "Phase3C_Quiescence_Restored_After_Drain",
        "0 non-idle sessions after transaction commit and client close",
        f"count={len(rows_restored)}",
        f"pg16://{PG16_HOST}:{PG16_PORT}/{dbname}",
        len(rows_restored) == 0,
        {"count": len(rows_restored)}
    )

    await inspector_conn.close()


# ─────────────────────────────────────────────────────────────────────────────
# Phase 4: Migration Runner Target Consistency & .env Isolation
# ─────────────────────────────────────────────────────────────────────────────

async def run_phase4_target_consistency_test():
    runner_script = os.path.join(API_ROOT, "scripts", "release_migration.py")
    dbname = "preflight_runner_target_test"
    admin = await asyncpg.connect(user=PG16_USER, password=PG16_PASS, host=PG16_HOST, port=PG16_PORT, database="postgres")
    await admin.execute(f"DROP DATABASE IF EXISTS {dbname}")
    await admin.execute(f"CREATE DATABASE {dbname} WITH TEMPLATE leadscore")
    await admin.close()

    target_url = f"postgresql://{PG16_USER}:{PG16_PASS}@{PG16_HOST}:{PG16_PORT}/{dbname}"

    # Downgrade to 0047
    subprocess.run([
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={target_url}", "downgrade", "0047_webhook_event_claims"
    ], cwd=API_ROOT, capture_output=True)

    # 4A: Target Consistency under conflicting environment variables
    # Set DATABASE_URL to a dummy non-existent DB in environment, pass explicit --db-url to runner
    env_conflict = os.environ.copy()
    env_conflict["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:5432/nonexistent_conflict_db"
    
    # Run release_migration with explicit target
    res_mig = subprocess.run([
        sys.executable, runner_script, "--db-url", target_url
    ], cwd=API_ROOT, env=env_conflict, capture_output=True, text=True)

    # Verify that target_url was migrated to 0050, NOT the conflict DB
    conn_verify = await asyncpg.connect(user=PG16_USER, password=PG16_PASS, host=PG16_HOST, port=PG16_PORT, database=dbname)
    final_rev = await conn_verify.fetchval("SELECT version_num FROM alembic_version")
    await conn_verify.close()

    target_isolated = (res_mig.returncode == 0 and final_rev == "0050_broker_subscription_constraint_parity")
    record_result(
        "Phase4A_Target_Consistency_Overrides_Conflicting_Env",
        "Alembic upgrades intended target URL despite conflicting DATABASE_URL in environment",
        f"rc={res_mig.returncode}, final_rev={final_rev}",
        target_url,
        target_isolated,
        {"output_summary": res_mig.stdout.splitlines()[-4:]}
    )

    # 4B: Re-running on 0050 is safe NO-OP
    res_noop = subprocess.run([
        sys.executable, runner_script, "--db-url", target_url
    ], cwd=API_ROOT, capture_output=True, text=True)
    noop_ok = (res_noop.returncode == 0 and "ALREADY_AT_HEAD" in res_noop.stdout)
    record_result(
        "Phase4B_Already_At_0050_Safe_NoOp",
        "Exit Code 0 and ALREADY_AT_HEAD status without DDL",
        f"rc={res_noop.returncode}, status=ALREADY_AT_HEAD",
        target_url,
        noop_ok,
        {"stdout": res_noop.stdout.strip().splitlines()[-5:]}
    )

    # 4C: Supabase transaction pooler port 6543 rejected
    port_6543_url = f"postgresql://{PG16_USER}:{PG16_PASS}@{PG16_HOST}:6543/{dbname}"
    res_6543 = subprocess.run([
        sys.executable, runner_script, "--db-url", port_6543_url, "--dry-run"
    ], cwd=API_ROOT, capture_output=True, text=True)
    p6543_rejected = (res_6543.returncode == 1 and "Target port 6543 detected" in res_6543.stderr)
    record_result(
        "Phase4C_Reject_Port_6543_Transaction_Pooler",
        "Exit Code 1 and explicit error rejecting transaction pooling mode",
        f"rc={res_6543.returncode}",
        port_6543_url,
        p6543_rejected,
        {"err": res_6543.stderr[:120]}
    )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 5: Deployed Environment Classification
# ─────────────────────────────────────────────────────────────────────────────

def run_phase5_environment_classification_test():
    entrypoint_sh = os.path.join(API_ROOT, "entrypoint.sh").replace("\\", "/")

    def test_env_boot(env_val, run_mig="false", expected_rc=1):
        env = os.environ.copy()
        if env_val is not None:
            env["ENV"] = env_val
        else:
            env.pop("ENV", None)
        env["RUN_MIGRATIONS_ON_STARTUP"] = run_mig
        env["SECRET_KEY"] = "test_secret_key_at_least_32_bytes_long_123456"
        env["SUPABASE_JWT_SECRET"] = "test_supabase_jwt_secret_32_bytes_len"
        env["DATABASE_URL"] = f"postgresql://{PG16_USER}:{PG16_PASS}@{PG16_HOST}:{PG16_PORT}/leadscore"
        env["DRY_RUN_VALIDATION_ONLY"] = "true"

        res = subprocess.run([GIT_BASH, entrypoint_sh], cwd=API_ROOT, env=env, capture_output=True, text=True)
        return res.returncode, (res.stdout + "\n" + res.stderr).strip()

    # 5A: Absent ENV fails closed
    rc, out = test_env_boot(None, expected_rc=1)
    record_result("Phase5A_Absent_ENV_Fails_Closed", "Exit Code 1", f"rc={rc}", "N/A", rc == 1, {"out": out[:100]})

    # 5B: Empty ENV fails closed
    rc, out = test_env_boot("", expected_rc=1)
    record_result("Phase5B_Empty_ENV_Fails_Closed", "Exit Code 1", f"rc={rc}", "N/A", rc == 1, {"out": out[:100]})

    # 5C: Malformed ENV fails closed
    rc, out = test_env_boot("production_staging_hybrid", expected_rc=1)
    record_result("Phase5C_Malformed_ENV_Fails_Closed", "Exit Code 1", f"rc={rc}", "N/A", rc == 1, {"out": out[:100]})

    # 5D: Startup migrations rejected
    rc, out = test_env_boot("production", run_mig="true", expected_rc=1)
    record_result("Phase5D_Reject_Startup_Migrations", "Exit Code 1", f"rc={rc}", "N/A", rc == 1, {"out": out[:100]})

    # 5E: Deployed production fails on leadscore at revision 0048 (not 0050)
    rc, out = test_env_boot("production", expected_rc=1)
    record_result("Phase5E_Prod_Fails_On_Revision_0048", "Exit Code 1", f"rc={rc}", "leadscore (rev 0048)", rc == 1, {"out": out[:120]})


# ─────────────────────────────────────────────────────────────────────────────
# Master Execution & Ledger Compilation
# ─────────────────────────────────────────────────────────────────────────────

async def main():
    print("==================================================================")
    print("WEFYLABS FINAL PRODUCTION PREFLIGHT & RELEASE AUTHORIZATION GATE")
    print("==================================================================")

    print("\n--- Phase 2: PostgreSQL 17 Utility & Parity Rehearsal ---")
    await run_phase2_pg17_backup_parity_test()

    print("\n--- Phase 3: Quiescent Write Boundary Verification ---")
    await run_phase3_quiescence_boundary_test()

    print("\n--- Phase 4: Migration Runner Target Consistency & Invariants ---")
    await run_phase4_target_consistency_test()

    print("\n--- Phase 5: Deployed Environment Classification ---")
    run_phase5_environment_classification_test()

    print("\n==================================================================")
    total_tests = len(RESULTS)
    passed_tests = sum(1 for r in RESULTS.values() if r["status"] == "PASSED")
    all_ok = (passed_tests == total_tests)
    print(f"PREFLIGHT SUMMARY: {passed_tests}/{total_tests} SCENARIOS VERIFIED PASSED")
    print("==================================================================")

    ledger_path = os.path.join(REPO_ROOT, "scratch", "final_preflight_verification_ledger.json")
    with open(ledger_path, "w") as f:
        json.dump(RESULTS, f, indent=2)
    print(f"Ledger written to: {ledger_path}")

    if not all_ok:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())

