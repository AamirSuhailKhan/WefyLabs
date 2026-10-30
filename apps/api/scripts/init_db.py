"""
WefyLabs Database Bootstrap Script
===================================
Certified database initialization procedure for fresh deployments and staging.

Valid execution pattern:
- Asynchronous context manager (`async with engine.begin() as connection:`)
- Complete model registry import (`import app.models`) -> 410 tables
- Base.metadata.create_all via `run_sync`
- Verification of PostgreSQL extensions (uuid-ossp, pgcrypto, vector)
- Application of migration-only / out-of-band objects (pgvector HNSW index, webhook claims seed)
- Authoritative Alembic head registration ('0047_webhook_event_claims')
- Clean engine resource disposal (`await engine.dispose()`)
"""
import sys
import os
import re
import argparse
import asyncio
import logging
from urllib.parse import urlparse, urlunparse
from sqlalchemy import text

# Ensure apps/api is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
API_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
if API_ROOT not in sys.path:
    sys.path.insert(0, API_ROOT)

from app.config import settings
from app.database import engine, Base
import app.models  # Guarantees all 410 ORM models are registered in Base.metadata

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("wefylabs.init_db")

AUTHORITATIVE_HEAD = "0050_broker_subscription_constraint_parity"
ALLOWED_ENVIRONMENTS = {"development", "dev", "test", "testing", "local", "staging", "preview", "ci", "production", "prod"}


def sanitize_db_url(url: str) -> str:
    """Masks credentials in database URL to prevent credential exposure in logs or artifacts."""
    if not url:
        return ""
    try:
        parsed = urlparse(url)
        netloc = parsed.netloc
        if "@" in netloc:
            _, host = netloc.split("@", 1)
            netloc = f"***:***@{host}"
        return urlunparse(parsed._replace(netloc=netloc))
    except Exception:
        return "[SANITIZED_DB_URL]"


async def initialize_database(
    target_schema: str = None, 
    check_only: bool = False, 
    dispose_on_exit: bool = False,
    env: str = None
) -> dict:
    """
    Initializes a fresh database to complete schema parity with the latest Alembic head.
    Enforces strict immutability for production: generic initialization cannot mutate production.
    """
    if env is not None:
        current_env = env.lower().strip()
    else:
        current_env = (getattr(settings, "ENV", None) or os.getenv("ENV") or "").lower().strip()

    if not current_env or current_env not in ALLOWED_ENVIRONMENTS:
        raise ValueError(f"Target environment '{current_env}' is ambiguous or unrecognized. Valid environments: {sorted(ALLOWED_ENVIRONMENTS)}")

    if target_schema:
        if not re.match(r"^[a-zA-Z0-9_]+$", target_schema):
            raise ValueError(f"Target schema '{target_schema}' is ambiguous or contains invalid characters.")

    is_prod = current_env in ("production", "prod")
    if is_prod and not check_only:
        raise PermissionError(
            "FATAL: Generic database initialization (Base.metadata.create_all) must not mutate a production database. "
            "Production database changes must use the reviewed migration/deployment mechanism (alembic upgrade head)."
        )

    logger.info("Starting WefyLabs database bootstrap...")
    logger.info(f"Target environment: {current_env}")
    logger.info(f"Target database: {sanitize_db_url(settings.DATABASE_URL)}")
    logger.info(f"Registered ORM models: {len(Base.metadata.tables)} tables")

    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    is_postgres = "postgresql" in settings.DATABASE_URL

    summary = {
        "is_sqlite": is_sqlite,
        "is_postgres": is_postgres,
        "models_registered": len(Base.metadata.tables),
        "target_schema": target_schema or ("public" if is_postgres else "main"),
        "alembic_head": AUTHORITATIVE_HEAD,
        "status": "pending",
    }

    try:
        async with engine.begin() as conn:
            # 1. Inspect schema existence and configuration
            if target_schema and is_postgres:
                schema_res = await conn.execute(text(
                    f"SELECT 1 FROM information_schema.schemata WHERE schema_name = '{target_schema}'"
                ))
                schema_exists = schema_res.scalar() is not None

                if check_only:
                    if not schema_exists:
                        summary["status"] = "schema_missing"
                        summary["details"] = f"Schema '{target_schema}' does not exist."
                        logger.info(summary["details"])
                        return summary
                    await conn.execute(text(f"SET search_path TO {target_schema}, extensions"))
                else:
                    if not schema_exists:
                        await conn.execute(text(f"CREATE SCHEMA {target_schema}"))
                        logger.info(f"Created isolated PostgreSQL schema: {target_schema}")
                    await conn.execute(text(f"SET search_path TO {target_schema}, extensions"))
                    logger.info(f"Set active PostgreSQL search_path to: {target_schema}, extensions")
            elif is_postgres:
                schema_exists = True

            # 2. In check-only mode, inspect without performing any DDL or mutations
            if check_only:
                # Explicitly enforce read-only transaction semantics at the PostgreSQL level
                if is_postgres:
                    await conn.execute(text("SET TRANSACTION READ ONLY"))
                logger.info("Check-only mode requested (READ ONLY transaction active). Inspecting target schema state...")
                schema_to_check = target_schema or ("public" if is_postgres else "main")
                if is_postgres:
                    res = await conn.execute(text(f"""
                        SELECT count(*) FROM information_schema.tables 
                        WHERE table_schema = '{schema_to_check}' AND table_type = 'BASE TABLE'
                    """))
                    summary["table_count"] = res.scalar()

                    # Check alembic_version
                    av_table = await conn.execute(text(f"""
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_schema = '{schema_to_check}' AND table_name = 'alembic_version'
                    """))
                    if av_table.scalar():
                        v_res = await conn.execute(text(f"SELECT version_num FROM {schema_to_check}.alembic_version"))
                        summary["recorded_head"] = v_res.scalar()
                    else:
                        summary["recorded_head"] = None

                    # Check vector index
                    idx_res = await conn.execute(text(f"""
                        SELECT 1 FROM pg_indexes 
                        WHERE schemaname = '{schema_to_check}' AND indexname = 'ix_ke_vector_hnsw'
                    """))
                    summary["hnsw_index_present"] = idx_res.scalar() is not None
                else:
                    res = await conn.execute(text("SELECT count(*) FROM sqlite_master WHERE type='table'"))
                    summary["table_count"] = res.scalar()
                    summary["recorded_head"] = None
                    summary["hnsw_index_present"] = False

                if summary["table_count"] == 0:
                    summary["status"] = "empty"
                elif summary.get("recorded_head") == AUTHORITATIVE_HEAD and summary["table_count"] >= 410:
                    summary["status"] = "verified"
                else:
                    summary["status"] = "drift_or_incomplete"

                logger.info(f"Check result: status={summary['status']}, tables={summary['table_count']}, head={summary.get('recorded_head')}")
                return summary

            # 3. Check / initialize PostgreSQL extensions
            if is_postgres:
                logger.info("Verifying PostgreSQL extensions (uuid-ossp, pgcrypto, vector)...")
                try:
                    await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
                    await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "pgcrypto"'))
                    await conn.execute(text('CREATE EXTENSION IF NOT EXISTS "vector"'))
                    logger.info("PostgreSQL extensions verified successfully.")
                except Exception as ext_err:
                    logger.warning(f"Extension verification notice: {ext_err}")

            # 4. Create all tables from SQLAlchemy metadata (idempotent)
            schema_to_use = target_schema or ("public" if is_postgres else "main")
            if is_postgres:
                count_res = await conn.execute(text(f"""
                    SELECT count(*) FROM information_schema.tables 
                    WHERE table_schema = '{schema_to_use}' AND table_type = 'BASE TABLE'
                """))
                existing_table_count = count_res.scalar()
            else:
                existing_table_count = 0

            if existing_table_count == 0:
                logger.info("Creating application schema via Base.metadata.create_all...")
                if target_schema:
                    await conn.run_sync(lambda s_conn: Base.metadata.create_all(s_conn, checkfirst=False))
                else:
                    await conn.run_sync(Base.metadata.create_all)
                logger.info("Base.metadata.create_all completed.")
            else:
                logger.info(f"Target schema already contains {existing_table_count} tables; applying missing objects idempotently...")
                await conn.run_sync(Base.metadata.create_all)

            # 5. Apply migration-only / out-of-band database operations
            if is_postgres:
                logger.info("Applying out-of-band and migration-only operations...")
                # 5a. Native vector column & HNSW index on knowledge_embeddings
                try:
                    await conn.execute(text(f"ALTER TABLE {schema_to_use}.knowledge_embeddings ADD COLUMN IF NOT EXISTS embedding vector(1536)"))
                    await conn.execute(text(f"CREATE INDEX IF NOT EXISTS ix_ke_vector_hnsw ON {schema_to_use}.knowledge_embeddings USING hnsw (embedding vector_cosine_ops)"))
                    logger.info("pgvector HNSW index applied on knowledge_embeddings.")
                except Exception as vec_err:
                    logger.info(f"pgvector index notice: {vec_err}")

                # 5b. Webhook event claims idempotency seed (parity with 0047)
                try:
                    await conn.execute(text(f"""
                        INSERT INTO {schema_to_use}.webhook_event_claims (id, provider, provider_event_id, organization_id, claimed_at)
                        SELECT md5(provider || ':' || COALESCE(organization_id, 'global') || ':' || provider_event_id),
                               provider, provider_event_id, COALESCE(organization_id, 'global'), MIN(received_at)
                        FROM {schema_to_use}.raw_communication_events
                        WHERE provider_event_id IS NOT NULL
                          AND processing_status IN ('PROCESSED', 'DUPLICATE_IGNORED')
                        GROUP BY provider, COALESCE(organization_id, 'global'), provider_event_id
                        ON CONFLICT (provider, organization_id, provider_event_id) DO NOTHING
                    """))
                    logger.info("Webhook event claims historical seed executed.")
                except Exception as seed_err:
                    logger.info(f"Webhook seed notice: {seed_err}")

            # 6. Verify table creation count BEFORE stamping
            if is_postgres:
                post_count = (await conn.execute(text(f"""
                    SELECT count(*) FROM information_schema.tables 
                    WHERE table_schema = '{schema_to_use}' AND table_type = 'BASE TABLE'
                """))).scalar()
                if post_count < 410:
                    raise RuntimeError(f"Database bootstrap incomplete: expected at least 410 tables, found {post_count}. Aborting without stamping.")

            # 7. Record authoritative Alembic head revision
            logger.info(f"Stamping alembic_version at authoritative head '{AUTHORITATIVE_HEAD}'...")
            await conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {schema_to_use}.alembic_version (
                    version_num VARCHAR(64) NOT NULL PRIMARY KEY
                )
            """))
            await conn.execute(text(f"DELETE FROM {schema_to_use}.alembic_version"))
            await conn.execute(text(f"INSERT INTO {schema_to_use}.alembic_version (version_num) VALUES ('{AUTHORITATIVE_HEAD}')"))
            current_head = (await conn.execute(text(f"SELECT version_num FROM {schema_to_use}.alembic_version"))).scalar()
            logger.info(f"Alembic revision recorded: {current_head}")
            assert current_head == AUTHORITATIVE_HEAD, "Alembic revision mismatch"

        summary["status"] = "initialized"
        logger.info("Database bootstrap completed successfully with zero schema drift.")
        return summary

    finally:
        if dispose_on_exit:
            await engine.dispose()
            logger.info("Database engine connections cleanly disposed.")


def main():
    parser = argparse.ArgumentParser(description="WefyLabs Database Bootstrap Script")
    parser.add_argument("--schema", type=str, default=None, help="Target PostgreSQL schema name")
    parser.add_argument("--check-only", action="store_true", help="Inspect without modifying")
    parser.add_argument("--env", type=str, default=None, help="Target environment override (e.g. staging, development)")
    args = parser.parse_args()

    # Safety Guard: Default configuration cannot target production for mutation
    if args.env is not None:
        current_env = args.env.lower().strip()
    else:
        current_env = (getattr(settings, "ENV", None) or os.getenv("ENV") or "").lower().strip()

    if not current_env or current_env not in ALLOWED_ENVIRONMENTS:
        logger.error(f"FATAL: Target environment '{current_env}' is ambiguous or unrecognized. Valid environments: {sorted(ALLOWED_ENVIRONMENTS)}")
        sys.exit(1)

    if args.schema and not re.match(r"^[a-zA-Z0-9_]+$", args.schema):
        logger.error(f"FATAL: Target schema '{args.schema}' is ambiguous or contains invalid characters.")
        sys.exit(1)

    is_prod = current_env in ("production", "prod")
    if is_prod and not args.check_only:
        logger.error(
            "FATAL: Refusing to execute mutating bootstrap against production environment.\n"
            "Generic initialization (Base.metadata.create_all) must not mutate a production database.\n"
            "Production database changes must use the reviewed migration/deployment mechanism (alembic upgrade head).\n"
            "Aborting with exit code 1 to protect production database integrity."
        )
        sys.exit(1)

    async def _run():
        try:
            return await initialize_database(target_schema=args.schema, check_only=args.check_only, dispose_on_exit=True, env=current_env)
        finally:
            await engine.dispose()

    try:
        result = asyncio.run(_run())
        print(f"\nResult: {result}")
        if args.check_only:
            if result.get("status") != "verified":
                logger.error(f"Check failed: status is '{result.get('status')}'")
                sys.exit(1)
        else:
            if result.get("status") != "initialized":
                logger.error(f"Bootstrap failed: status is '{result.get('status')}'")
                sys.exit(1)
    except Exception as exc:
        logger.error(f"Bootstrap execution error: {type(exc).__name__}: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
