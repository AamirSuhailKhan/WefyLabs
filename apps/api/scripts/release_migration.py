"""
WefyLabs Dedicated Release Migration Runner
============================================
Single authorized mechanism for executing production database migrations.
Enforces:
1. Pre-flight target identification & credential masking.
2. Current revision validation (confirms expected predecessor).
3. Controlled sequential migration execution via Alembic.
4. Post-migration schema verification (UUID types, FKs, check constraints).
5. Fail-closed exit codes on any anomaly.
"""
import sys
import os
import argparse
import asyncio
import logging
from urllib.parse import urlparse, urlunparse

# Ensure apps/api is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
API_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

from dotenv import load_dotenv
# Load environment files
load_dotenv(os.path.join(API_ROOT, "../../.env"), override=False)
load_dotenv(os.path.join(API_ROOT, ".env"), override=False)

import asyncpg
from alembic.config import Config
from alembic import command

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("wefylabs.release_migration")

TARGET_HEAD = "0050_broker_subscription_constraint_parity"
VALID_PREDECESSORS = {
    "0047_webhook_event_claims",
    "0048_schema_reconciliation_parity",
    "0049_source_attribution_uuid_parity"
}


def sanitize_url(raw_url: str) -> str:
    if not raw_url:
        return "[EMPTY]"
    try:
        clean = raw_url.replace("+asyncpg", "").replace("+aiosqlite", "")
        p = urlparse(clean)
        netloc = p.netloc
        if "@" in netloc:
            _, host = netloc.split("@", 1)
            netloc = f"***:***@{host}"
        return urlunparse(p._replace(netloc=netloc))
    except Exception:
        return "[SANITIZED]"


def resolve_target_url(explicit_url: str = None) -> str:
    """Resolve database target URL securely.
    Prioritizes:
    1. Explicit function argument (if provided).
    2. TARGET_DATABASE_URL environment variable (secure injection).
    3. Standard libpq environment variables (PGHOST, PGUSER, PGPASSWORD, PGDATABASE, PGPORT).
    4. DATABASE_URL environment variable.
    Prevents password exposure in shell history and ps command arguments.
    """
    if explicit_url:
        return explicit_url
    if os.environ.get("TARGET_DATABASE_URL"):
        return os.environ.get("TARGET_DATABASE_URL")
    if os.environ.get("PGHOST") and os.environ.get("PGUSER") and os.environ.get("PGDATABASE"):
        user = os.environ.get("PGUSER")
        password = os.environ.get("PGPASSWORD", "")
        host = os.environ.get("PGHOST")
        port = os.environ.get("PGPORT", "5432")
        db = os.environ.get("PGDATABASE")
        auth = f"{user}:{password}@" if password else f"{user}@"
        return f"postgresql://{auth}{host}:{port}/{db}"
    return os.environ.get("DATABASE_URL")


async def run_controlled_release(database_url: str = None, dry_run: bool = False) -> dict:
    raw_url = resolve_target_url(database_url)
    if not raw_url:
        raise ValueError(
            "Target database URL not found. Provide via TARGET_DATABASE_URL env var, "
            "standard libpq env vars (PGHOST, PGUSER, PGPASSWORD, PGDATABASE), or --db-url."
        )

    clean_url = raw_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    sanitized = sanitize_url(raw_url)
    parsed = urlparse(clean_url)

    logger.info("==================================================================")
    logger.info("WEFYLABS AUTHORIZED RELEASE MIGRATION RUNNER")
    logger.info(f"Target Database:   {sanitized}")
    logger.info(f"Target Host:       {parsed.hostname}:{parsed.port}")
    logger.info(f"Target Schema DB:   {parsed.path.lstrip('/')}")
    logger.info(f"Target Head Rev:   {TARGET_HEAD}")
    logger.info(f"Dry Run Mode:      {dry_run}")
    logger.info("==================================================================")

    # Invariant Check: Supabase Pooler mode check
    if parsed.port == 6543:
        raise RuntimeError(
            "FATAL: Target port 6543 detected (Supabase Transaction Pooler). "
            "Transaction pooling mode does NOT support DDL operations, advisory locks, or prepared statements. "
            "Connect using Session Mode (port 5432) or the direct database connection."
        )

    # Invariant Check: Verify repository Alembic DAG has exactly one head
    import subprocess
    cmd_heads = [sys.executable, "-m", "alembic", "-c", "alembic.ini", "heads"]
    res_heads = subprocess.run(cmd_heads, cwd=API_ROOT, capture_output=True, text=True)
    if res_heads.returncode != 0:
        raise RuntimeError(f"FATAL: Failed to query Alembic DAG heads:\n{res_heads.stderr}")
    heads_list = [line.split()[0] for line in res_heads.stdout.strip().splitlines() if line.strip()]
    if len(heads_list) != 1:
        raise RuntimeError(f"FATAL: Multiple Alembic heads detected in codebase DAG: {heads_list}. Split-brain migration DAG!")
    if heads_list[0] != TARGET_HEAD:
        raise RuntimeError(f"FATAL: Repository Alembic head mismatch! Found '{heads_list[0]}', expected '{TARGET_HEAD}'.")
    logger.info(f"[DAG CHECK OK] Verified exactly 1 repository head: {heads_list[0]}")

    # Step 1: Preflight connection and state inspection
    logger.info("[STEP 1/5] Inspecting current database state (read-only)...")
    conn = await asyncpg.connect(clean_url)
    try:
        current_db = await conn.fetchval("SELECT current_database()")
        server_ver = await conn.fetchval("SHOW server_version")
        inet_addr = await conn.fetchval("SELECT inet_server_addr()")
        
        # Check for multiple revisions in alembic_version table
        version_rows = await conn.fetch("SELECT version_num FROM alembic_version")
        if len(version_rows) > 1:
            multi_revs = [r["version_num"] for r in version_rows]
            raise RuntimeError(
                f"FATAL: Multiple revisions found in database alembic_version table: {multi_revs}. "
                "Split-brain database state detected! Aborting."
            )
        current_rev = version_rows[0]["version_num"] if version_rows else None

        logger.info(f"  Connected DB:    {current_db}")
        logger.info(f"  Server Version:  {server_ver}")
        logger.info(f"  Server IP:       {inet_addr}")
        logger.info(f"  Current Rev:     {current_rev}")

        if current_rev == TARGET_HEAD:
            logger.info(f"[NO-OP] Database is ALREADY at target head '{TARGET_HEAD}'. No migration needed.")
            return {
                "status": "ALREADY_AT_HEAD",
                "revision": current_rev,
                "target_head": TARGET_HEAD,
                "sanitized_url": sanitized
            }

        if current_rev not in VALID_PREDECESSORS:
            raise RuntimeError(
                f"FATAL: Database revision '{current_rev}' is not a recognized predecessor for head '{TARGET_HEAD}'. "
                f"Expected one of: {sorted(VALID_PREDECESSORS)}. Aborting to prevent split-brain DAG."
            )

        logger.info(f"[PREFLIGHT OK] Database at '{current_rev}' is an authorized predecessor.")
    finally:
        await conn.close()

    if dry_run:
        logger.info("[DRY RUN] Dry-run requested. Preflight checks passed. Exiting without migration.")
        return {"status": "DRY_RUN_PASSED", "predecessor": current_rev, "target_head": TARGET_HEAD}

    # Step 2: Execute Alembic migration in dedicated isolated process
    logger.info("[STEP 2/5] Executing controlled Alembic migration to head via isolated process...")
    import subprocess
    cmd_alembic = [
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={clean_url}",
        "upgrade", "head"
    ]
    env_alembic = os.environ.copy()
    env_alembic["DATABASE_URL"] = clean_url
    res_mig = subprocess.run(cmd_alembic, cwd=API_ROOT, env=env_alembic, capture_output=True, text=True)
    if res_mig.returncode != 0:
        logger.error(f"Alembic upgrade failed:\n{res_mig.stderr}\n{res_mig.stdout}")
        raise RuntimeError(f"Alembic migration failed with exit code {res_mig.returncode}: {res_mig.stderr}")
    logger.info(f"[MIGRATION COMPLETE] Alembic output:\n{res_mig.stderr.strip() or res_mig.stdout.strip()}")

    # Step 3: Post-migration verification
    logger.info("[STEP 3/5] Verifying post-migration revision and schema integrity...")
    conn = await asyncpg.connect(clean_url)
    try:
        final_rev = await conn.fetchval("SELECT version_num FROM alembic_version")
        if final_rev != TARGET_HEAD:
            raise RuntimeError(f"FATAL: Final revision mismatch! Expected '{TARGET_HEAD}', found '{final_rev}'.")
        logger.info(f"  Final Revision Confirmed: {final_rev}")

        # Check column types on source_attributions (schema-qualified)
        cols = await conn.fetch("""
            SELECT column_name, data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_schema = current_schema() AND table_name = 'source_attributions' AND column_name IN ('organization_id', 'lead_id')
        """)
        col_map = {r["column_name"]: (r["data_type"], r["is_nullable"]) for r in cols}
        assert col_map.get("organization_id") == ("uuid", "NO"), f"Bad organization_id column: {col_map}"
        assert col_map.get("lead_id") == ("uuid", "YES"), f"Bad lead_id column: {col_map}"
        logger.info("  Column Types Confirmed: native UUID on organization_id (NOT NULL) and lead_id (NULLABLE).")

        # Check foreign keys on table in active schema
        fks = await conn.fetch("""
            SELECT conname FROM pg_constraint 
            WHERE conrelid = 'source_attributions'::regclass
              AND conname IN ('fk_source_attributions_organization_id', 'fk_source_attributions_lead_id')
        """)
        assert len(fks) == 2, f"Missing foreign key constraints on source_attributions: found {len(fks)}"
        logger.info("  Foreign Keys Confirmed: fk_source_attributions_organization_id and fk_source_attributions_lead_id present.")

        # Check updated broker constraints on tables in active schema
        checks = await conn.fetch("""
            SELECT conname, pg_get_constraintdef(oid) as def FROM pg_constraint 
            WHERE conrelid IN ('brokers'::regclass, 'subscriptions'::regclass)
              AND conname IN ('ck_brokers_subscription_plan', 'ck_brokers_subscription_status', 'ck_subscriptions_status')
        """)
        check_map = {r["conname"]: r["def"] for r in checks}
        assert "pro_monthly" in check_map.get("ck_brokers_subscription_plan", ""), "Missing pro_monthly in plan constraint"
        assert "paused" in check_map.get("ck_brokers_subscription_status", ""), "Missing paused in broker status constraint"
        assert "paused" in check_map.get("ck_subscriptions_status", ""), "Missing paused in subscription status constraint"
        logger.info("  Check Constraints Confirmed: modern plans and statuses verified.")

    finally:
        await conn.close()

    logger.info("[STEP 4/5] Smoke testing relational queries on migrated schema...")
    conn = await asyncpg.connect(clean_url)
    try:
        # Relational join smoke
        join_test = await conn.fetch("SELECT leads.id FROM leads JOIN source_attributions ON leads.id = source_attributions.lead_id LIMIT 1")
        logger.info(f"  Relational JOIN Test: Succeeded without type mismatch (operator = uuid/varchar eliminated).")
    finally:
        await conn.close()

    logger.info("[STEP 5/5] Release migration successfully verified!")
    logger.info("==================================================================")
    logger.info("RELEASE MIGRATION SUCCESSFUL: DATABASE READY FOR APPLICATION TRAFFIC")
    logger.info("==================================================================")

    return {
        "status": "MIGRATION_SUCCESSFUL",
        "initial_revision": current_rev,
        "final_revision": final_rev,
        "target_head": TARGET_HEAD,
        "sanitized_url": sanitized
    }


def main():
    parser = argparse.ArgumentParser(description="WefyLabs Dedicated Release Migration Runner")
    parser.add_argument("--db-url", "--database-url", dest="db_url", type=str, default=None, help="Explicit target database URL (optional fallback; prefer TARGET_DATABASE_URL or libpq env vars to avoid exposing credentials in process table)")
    parser.add_argument("--target-head", type=str, default=TARGET_HEAD, help="Expected target head revision")
    parser.add_argument("--dry-run", action="store_true", help="Run preflight checks only")
    args = parser.parse_args()

    if args.target_head != TARGET_HEAD:
        logger.error(f"[FATAL] Mismatched --target-head '{args.target_head}'. Authoritative head is '{TARGET_HEAD}'.")
        sys.exit(1)

    try:
        result = asyncio.run(run_controlled_release(database_url=args.db_url, dry_run=args.dry_run))
        import json
        print("\nResult:")
        print(json.dumps(result, indent=2))
        sys.exit(0)
    except Exception as exc:
        logger.error(f"[FATAL MIGRATION FAILURE] {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
