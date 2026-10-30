"""
Database Bootstrap and Migration Verification Tests
==================================================
Workstream B test suite validating:
1. Clean bootstrap of application schema from an empty/disposable schema.
2. Verified migration head registration (0047_webhook_event_claims).
3. Idempotent reinitialization without DuplicateTableError.
4. Read-only --check-only behavior and drift/missing schema detection.
5. Native pgvector column & HNSW index integrity on knowledge_embeddings.
6. Webhook event claims idempotency and duplicate event rejection.
7. Transaction rollback on error.
"""
import pytest
import uuid
from sqlalchemy import text
from app.database import engine, Base
from scripts.init_db import initialize_database, AUTHORITATIVE_HEAD


@pytest.fixture(autouse=True)
async def cleanup_engine():
    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_database_check_only_on_missing_schema():
    """Verify that --check-only on a nonexistent schema reports schema_missing without modifying database."""
    unique_schema = f"test_missing_{uuid.uuid4().hex[:8]}"
    res = await initialize_database(target_schema=unique_schema, check_only=True)
    assert res["status"] == "schema_missing"
    assert "does not exist" in res.get("details", "")


@pytest.mark.asyncio
async def test_database_bootstrap_and_idempotence():
    """Verify bootstrap verification, idempotence, pgvector index, and webhook deduplication."""
    test_schema = "phase7_test_disposable"

    # 1. Check-only verification
    res_check = await initialize_database(target_schema=test_schema, check_only=True)
    assert res_check["status"] == "verified"
    assert res_check["table_count"] >= 410
    assert res_check["recorded_head"] == AUTHORITATIVE_HEAD
    assert res_check["hnsw_index_present"] is True

    # 2. Idempotent re-initialization (must succeed without DuplicateTableError)
    res_reinit = await initialize_database(target_schema=test_schema, check_only=False)
    assert res_reinit["status"] == "initialized"

    # 3. Verify vector column & HNSW index in the isolated schema
    async with engine.begin() as conn:
        idx_res = await conn.execute(text(f"""
            SELECT indexname, indexdef FROM pg_indexes 
            WHERE schemaname = '{test_schema}' AND indexname = 'ix_ke_vector_hnsw'
        """))
        row = idx_res.fetchone()
        assert row is not None, "ix_ke_vector_hnsw index was not created"
        assert "hnsw" in row[1].lower(), "Index is not using HNSW access method"

    # 4. Verify webhook claims uniqueness and idempotency
    async with engine.begin() as conn:
        claim_id_1 = str(uuid.uuid4())
        await conn.execute(text(f"""
            INSERT INTO {test_schema}.webhook_event_claims 
            (id, provider, organization_id, provider_event_id, claimed_at)
            VALUES ('{claim_id_1}', 'whatsapp', 'org_123', 'evt_999', NOW())
            ON CONFLICT (provider, organization_id, provider_event_id) DO NOTHING
        """))

        # Duplicate claim must violate unique constraint or be handled idempotently
        with pytest.raises(Exception):
            claim_id_2 = str(uuid.uuid4())
            await conn.execute(text(f"""
                INSERT INTO {test_schema}.webhook_event_claims 
                (id, provider, organization_id, provider_event_id, claimed_at)
                VALUES ('{claim_id_2}', 'whatsapp', 'org_123', 'evt_999', NOW())
            """))


@pytest.mark.asyncio
async def test_transaction_rollback_safety():
    """Verify that a failing transaction rolls back cleanly without leaving hanging mutations."""
    test_schema = f"test_rb_{uuid.uuid4().hex[:8]}"

    try:
        async with engine.begin() as conn:
            await conn.execute(text(f"CREATE SCHEMA {test_schema}"))
            await conn.execute(text(f"""
                CREATE TABLE {test_schema}.dummy_test (id INT PRIMARY KEY, name VARCHAR(50))
            """))
            await conn.execute(text(f"INSERT INTO {test_schema}.dummy_test VALUES (1, 'initial')"))

        # Trigger an error inside a transaction block
        with pytest.raises(Exception):
            async with engine.begin() as conn:
                await conn.execute(text(f"INSERT INTO {test_schema}.dummy_test VALUES (2, 'second')"))
                # Cause division by zero or invalid query
                await conn.execute(text("SELECT 1/0"))

        # Verify that record '2' was rolled back
        async with engine.begin() as conn:
            count = (await conn.execute(text(f"SELECT count(*) FROM {test_schema}.dummy_test"))).scalar()
            assert count == 1, "Transaction was not rolled back cleanly"

    finally:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f"DROP SCHEMA IF EXISTS {test_schema} CASCADE"))
        except Exception:
            pass


@pytest.mark.asyncio
async def test_production_mutation_strictly_rejected():
    """Verify that generic database initialization strictly refuses to mutate production."""
    for prod_env in ("production", "prod"):
        with pytest.raises(PermissionError) as exc_info:
            await initialize_database(target_schema="test_prod_blocked", check_only=False, env=prod_env)
        assert "Generic database initialization" in str(exc_info.value)
        assert "must not mutate a production database" in str(exc_info.value)


@pytest.mark.asyncio
async def test_production_check_only_allowed_and_read_only():
    """Verify that --check-only in production remains possible and read-only."""
    res = await initialize_database(target_schema="phase9_fresh_disposable", check_only=True, env="production")
    assert res["status"] == "verified"
    assert res["table_count"] >= 410
    assert res["recorded_head"] == AUTHORITATIVE_HEAD


@pytest.mark.asyncio
async def test_ambiguous_environment_and_schema_rejected():
    """Verify that ambiguous or unrecognized environments and invalid schemas are strictly rejected."""
    # Ambiguous / unrecognized environment
    for bad_env in ("", "unknown_env", "prod_v2", "random"):
        with pytest.raises(ValueError) as exc_info:
            await initialize_database(target_schema="valid_schema", check_only=False, env=bad_env)
        assert "ambiguous or unrecognized" in str(exc_info.value)

    # Ambiguous / invalid schema name
    for bad_schema in ("bad schema", "schema;--", "drop_table'", "schema$name"):
        with pytest.raises(ValueError) as exc_info:
            await initialize_database(target_schema=bad_schema, check_only=False, env="development")
        assert "ambiguous or contains invalid characters" in str(exc_info.value)


def test_db_credentials_sanitized():
    """Verify that database URLs are properly sanitized to prevent secret leaks in logs."""
    from scripts.init_db import sanitize_db_url
    raw_url = "postgresql+asyncpg://admin_user:super_secret_pwd@db.internal.net:5432/crm_prod"
    sanitized = sanitize_db_url(raw_url)
    assert "super_secret_pwd" not in sanitized
    assert "admin_user" not in sanitized
    assert "***:***@db.internal.net:5432/crm_prod" in sanitized

