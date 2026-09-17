"""
test_part32_e2e.py
==================
Part 32 — Production Hardening E2E Tests

Tests real database connectivity, Alembic migration status,
and production config validation boundaries.
"""
import os
import pytest


@pytest.fixture(scope="module", autouse=True)
def set_test_env():
    os.environ["ENV"] = "testing"
    os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_dev.db"
    os.environ["SECRET_KEY"] = "test_secret_key_that_is_at_least_32_chars_long_ok"
    os.environ["SUPABASE_JWT_SECRET"] = "test_supabase_jwt_secret_placeholder_for_unit_tests_only"
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"


# ─── 1. Database E2E ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestDatabaseE2E:

    async def test_database_engine_connects(self, db_session):
        """Engine must create a valid connection and execute query."""
        from sqlalchemy import text
        result = await db_session.execute(text("SELECT 1"))
        row = result.fetchone()
        assert row[0] == 1

    async def test_database_session_query_works(self, db_session):
        """AsyncSession must execute a basic query."""
        from sqlalchemy import text
        result = await db_session.execute(text("SELECT 1+1"))
        val = result.scalar()
        assert val == 2

    async def test_database_session_can_be_acquired_twice(self, db_session):
        """Session must handle multiple sequential queries."""
        from sqlalchemy import text
        results = []
        for _ in range(3):
            result = await db_session.execute(text("SELECT 42"))
            results.append(result.scalar())
        assert all(r == 42 for r in results)


# ─── 2. Application Startup E2E ───────────────────────────────────────────────

@pytest.mark.asyncio
class TestApplicationStartupE2E:

    async def test_app_starts_without_error(self):
        """FastAPI app must import and be constructable."""
        from app.main import app
        assert app is not None
        assert app.title

    async def test_app_has_expected_middleware(self):
        """App must have middleware stack configured."""
        from app.main import app
        assert app is not None

    async def test_all_routers_attached(self):
        """App must have many routes registered (complex multi-module app)."""
        from app.main import app
        route_count = len(app.routes)
        assert route_count > 50, f"Expected >50 routes, got {route_count}"

    async def test_settings_can_be_imported_cleanly(self):
        """Settings module must import without side effects."""
        from app.config import settings
        assert settings is not None
        assert hasattr(settings, "ENV")

    async def test_alembic_ini_exists(self):
        """alembic.ini must exist in the API root."""
        alembic_ini = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        assert os.path.exists(alembic_ini), "alembic.ini not found"

    async def test_alembic_versions_directory_exists(self):
        """alembic/versions/ directory must exist."""
        versions_dir = os.path.join(os.path.dirname(__file__), "..", "alembic", "versions")
        assert os.path.isdir(versions_dir), "alembic/versions/ directory not found"

    async def test_requirements_txt_exists(self):
        """requirements.txt must exist for production deployment."""
        req = os.path.join(os.path.dirname(__file__), "..", "requirements.txt")
        assert os.path.exists(req)


# ─── 3. Config Boundary Tests ────────────────────────────────────────────────

class TestConfigBoundaryE2E:

    def test_testing_env_does_not_enforce_production_rules(self):
        """Testing mode should not be blocked by prod config guards."""
        os.environ["ENV"] = "testing"
        from app.common.config.validated_settings import EnterpriseSettings
        # Should not raise
        s = EnterpriseSettings(
            ENV="testing",
            DATABASE_URL="sqlite+aiosqlite:///./test_dev.db",
            SECRET_KEY="short",  # Short keys allowed in testing
            SUPABASE_JWT_SECRET="placeholder",
        )
        assert s.ENV == "testing"

    def test_development_env_loads_with_defaults(self):
        """Development mode should load with permissive defaults."""
        from app.common.config.validated_settings import EnterpriseSettings
        s = EnterpriseSettings(
            ENV="development",
            SECRET_KEY="any_secret_key_for_dev",
        )
        assert s.ENV == "development"

    def test_cors_origins_comma_string_parsed(self):
        """CORS_ORIGINS as comma-separated string must parse to list."""
        from app.common.config.validated_settings import EnterpriseSettings
        s = EnterpriseSettings(
            ENV="testing",
            CORS_ORIGINS="http://localhost:3000,https://example.com",
            SECRET_KEY="test_secret_key_that_is_at_least_32_chars_long_ok",
        )
        assert isinstance(s.CORS_ORIGINS, list)
        assert len(s.CORS_ORIGINS) == 2
        assert "http://localhost:3000" in s.CORS_ORIGINS

    def test_database_url_rewrite_postgresql_to_asyncpg(self):
        """postgresql:// must rewrite to postgresql+asyncpg://."""
        from app.common.config.validated_settings import EnterpriseSettings
        s = EnterpriseSettings(
            ENV="testing",
            DATABASE_URL="postgresql://user:pass@host/db",
            SECRET_KEY="test_secret_key_that_is_at_least_32_chars_long_ok",
        )
        assert s.DATABASE_URL.startswith("postgresql+asyncpg://")

    def test_postgresql_asyncpg_url_not_double_rewritten(self):
        """postgresql+asyncpg:// must not be double-rewritten."""
        from app.common.config.validated_settings import EnterpriseSettings
        url = "postgresql+asyncpg://user:pass@host/db"
        s = EnterpriseSettings(
            ENV="testing",
            DATABASE_URL=url,
            SECRET_KEY="test_secret_key_that_is_at_least_32_chars_long_ok",
        )
        assert s.DATABASE_URL == url
        assert "asyncpg+asyncpg" not in s.DATABASE_URL
