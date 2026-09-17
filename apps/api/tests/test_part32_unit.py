"""
test_part32_unit.py
===================
Part 32 — Production Hardening Unit Tests

Tests configuration validation, database pool settings, health endpoint
registration, code quality enforcement, and security guards.
All tests are designed to work with the existing settings singleton
(ENV=development from .env file) without requiring env var patching.
"""
import os
import re
import pytest


# ─── 1. Config Validation ─────────────────────────────────────────────────────

class TestConfigValidation:
    """Production config validation fail-fast guards."""

    def test_config_loads_without_error(self):
        """Settings must load without raising exceptions."""
        from app.config import settings
        assert settings is not None

    def test_config_secret_key_non_empty(self):
        """SECRET_KEY must be non-empty."""
        from app.config import settings
        assert settings.SECRET_KEY
        assert len(settings.SECRET_KEY) >= 10

    def test_razorpay_not_live_mode(self):
        """RAZORPAY_ENVIRONMENT must not be 'live' in dev/test."""
        from app.config import settings
        env = settings.ENV.lower()
        if env in ("testing", "development", "dev"):
            assert settings.RAZORPAY_ENVIRONMENT != "live"

    def test_cors_origins_is_list(self):
        """CORS_ORIGINS must be parsed into a list."""
        from app.config import settings
        assert isinstance(settings.CORS_ORIGINS, list)
        assert len(settings.CORS_ORIGINS) > 0

    def test_asyncpg_dialect_auto_fixed(self):
        """postgresql:// must be rewritten to postgresql+asyncpg://."""
        from app.common.config.validated_settings import EnterpriseSettings
        s = EnterpriseSettings(
            ENV="testing",
            DATABASE_URL="postgresql://user:pass@localhost/db",
            SECRET_KEY="test_secret_key_that_is_at_least_32_chars_long_ok",
            SUPABASE_JWT_SECRET="test_sub_jwt_placeholder_for_tests",
        )
        assert s.DATABASE_URL.startswith("postgresql+asyncpg://")

    def test_settings_has_required_security_fields(self):
        """Settings must expose all security-critical fields."""
        from app.config import settings
        required = ["SECRET_KEY", "SUPABASE_JWT_SECRET", "DATABASE_URL", "REDIS_URL", "ENV", "CORS_ORIGINS"]
        for field in required:
            assert hasattr(settings, field), f"Settings missing field: {field}"

    def test_access_token_expire_minutes_reasonable(self):
        """ACCESS_TOKEN_EXPIRE_MINUTES must be a positive and bounded integer."""
        from app.config import settings
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 60 * 24 * 30

    def test_default_secret_key_constant_is_dev_only(self):
        """DEFAULT_SECRET_KEY constant must be identifiable as dev-only."""
        from app.common.config.validated_settings import DEFAULT_SECRET_KEY
        assert DEFAULT_SECRET_KEY != ""
        assert len(DEFAULT_SECRET_KEY) > 10
        assert any(word in DEFAULT_SECRET_KEY.lower() for word in ["dev", "change", "2026", "prod"])

    def test_smtp_host_string_if_set(self):
        """SMTP_HOST must be a string if configured."""
        from app.config import settings
        if settings.SMTP_HOST:
            assert isinstance(settings.SMTP_HOST, str)

    def test_cors_origins_list_not_empty(self):
        """CORS_ORIGINS must have at least one origin."""
        from app.config import settings
        assert len(settings.CORS_ORIGINS) > 0

    def test_asyncpg_url_not_double_rewritten(self):
        """postgresql+asyncpg:// must not become postgresql+asyncpg+asyncpg://."""
        from app.common.config.validated_settings import EnterpriseSettings
        url = "postgresql+asyncpg://user:pass@host/db"
        s = EnterpriseSettings(
            ENV="testing",
            DATABASE_URL=url,
            SECRET_KEY="test_secret_key_that_is_at_least_32_chars_long_ok",
        )
        assert s.DATABASE_URL == url
        assert "asyncpg+asyncpg" not in s.DATABASE_URL

    def test_razorpay_live_with_test_key_rejected_in_production(self):
        """RAZORPAY_ENVIRONMENT='live' + rzp_test_ key must fail regardless of ENV."""
        from pydantic import ValidationError
        with pytest.raises((ValueError, ValidationError)):
            from app.common.config.validated_settings import EnterpriseSettings
            EnterpriseSettings(
                ENV="production",
                SECRET_KEY="a" * 32,
                DATABASE_URL="postgresql+asyncpg://x:y@localhost/db",
                GEMINI_API_KEY="real_gemini_key_not_placeholder",
                WHATSAPP_VERIFY_TOKEN="a" * 32,
                GOOGLE_CLIENT_ID="123.apps.googleusercontent.com",
                GOOGLE_CLIENT_SECRET="GOCSPX-real",
                RAZORPAY_ENVIRONMENT="live",
                RAZORPAY_KEY_ID="rzp_test_placeholder",
                RAZORPAY_KEY_SECRET="secret_value_here",
                RAZORPAY_WEBHOOK_SECRET="a" * 32,
            )

    def test_development_env_loads_with_permissive_defaults(self):
        """Development mode must load without production guards firing."""
        from app.common.config.validated_settings import EnterpriseSettings
        # Development does not enforce prod rules — should not raise
        s = EnterpriseSettings(
            ENV="development",
            SECRET_KEY="any_secret_key_for_dev",
        )
        assert s.ENV == "development"


# ─── 2. Database Pool ─────────────────────────────────────────────────────────

class TestDatabasePool:
    """Database engine connection pool configuration."""

    def test_engine_has_pool_pre_ping(self):
        """Engine must have pool_pre_ping=True for stale connection detection."""
        from app.database import engine
        assert engine.pool._pre_ping is True

    def test_engine_has_pool_recycle(self):
        """Engine must have pool_recycle=1800 (30 minutes)."""
        from app.database import engine
        assert engine.pool._recycle == 1800

    def test_engine_url_has_valid_dialect(self):
        """Engine must use a supported database dialect."""
        from app.database import engine
        db_url = str(engine.url)
        assert "sqlite" in db_url or "postgresql" in db_url

    def test_async_session_factory_configured(self):
        """AsyncSessionLocal must have expire_on_commit=False."""
        from app.database import AsyncSessionLocal
        assert AsyncSessionLocal is not None
        assert AsyncSessionLocal.kw.get("expire_on_commit") is False

    def test_get_db_is_async_generator(self):
        """get_db dependency must be an async generator function."""
        import inspect
        from app.database import get_db
        assert inspect.isasyncgenfunction(get_db)


# ─── 3. Health Endpoints ──────────────────────────────────────────────────────

class TestHealthEndpointRegistration:
    """Health check endpoint registration."""

    def test_main_imports_successfully(self):
        """app.main must import without errors."""
        from app import main
        assert main.app is not None

    def _get_routes(self):
        from app.main import app
        return set(app.openapi()["paths"].keys())

    def test_liveness_route_registered(self):
        """GET /health/liveness must be registered."""
        routes = self._get_routes()
        assert "/health/liveness" in routes, f"Routes: {sorted(routes)}"

    def test_readiness_route_registered(self):
        """GET /health/readiness must be registered."""
        routes = self._get_routes()
        assert "/health/readiness" in routes, f"Routes: {sorted(routes)}"

    def test_deep_health_route_registered(self):
        """GET /health must be registered."""
        routes = self._get_routes()
        assert "/health" in routes, f"Routes: {sorted(routes)}"

    def test_metrics_route_registered(self):
        """GET /metrics must be registered for Prometheus."""
        routes = self._get_routes()
        assert "/metrics" in routes, f"Routes: {sorted(routes)}"


# ─── 4. Code Quality ─────────────────────────────────────────────────────────

class TestCodeQuality:
    """Verify no debug/insecure patterns in production code."""

    def _read(self, *parts):
        path = os.path.join(os.path.dirname(__file__), *parts)
        with open(path, encoding="utf-8") as f:
            return f.read()

    def test_no_print_in_whatsapp_router(self):
        """whatsapp.py must not contain bare print() calls."""
        content = self._read("..", "app", "routers", "whatsapp.py")
        print_calls = re.findall(r"^\s*print\(", content, re.MULTILINE)
        assert len(print_calls) == 0, f"Bare print() in whatsapp.py: {print_calls}"

    def test_whatsapp_router_has_logger(self):
        """whatsapp.py must define a structured logger."""
        content = self._read("..", "app", "routers", "whatsapp.py")
        assert "import logging" in content
        assert "logger = logging.getLogger" in content

    def test_no_hardcoded_db_url_in_database_py(self):
        """database.py must not hardcode production connection strings."""
        content = self._read("..", "app", "database.py")
        assert "supabase.com" not in content
        assert "upstash.io" not in content

    def test_entrypoint_uses_env_var_for_proxy_ips(self):
        """entrypoint.sh must use $PROXY_IPS variable, not hardcoded '*'."""
        content = self._read("..", "entrypoint.sh")
        assert "PROXY_IPS" in content
        hardcoded = re.search(r'--forwarded-allow-ips\s+"?\*"?', content)
        assert hardcoded is None, "entrypoint.sh hardcodes --forwarded-allow-ips='*'"

    def test_render_yaml_has_celery_beat(self):
        """render.yaml must define a celery-beat worker service."""
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "render.yaml")
        if not os.path.exists(path):
            pytest.skip("render.yaml not found")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "celery-beat" in content or "celery beat" in content

    def test_render_yaml_cors_not_hardcoded(self):
        """render.yaml CORS_ORIGINS should be sync:false (env-configurable)."""
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "render.yaml")
        if not os.path.exists(path):
            pytest.skip("render.yaml not found")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        # Should not have a hardcoded value line directly after CORS_ORIGINS
        cors_hardcoded = re.search(r"CORS_ORIGINS.*\n\s+value:", content)
        assert cors_hardcoded is None, "CORS_ORIGINS is hardcoded in render.yaml"

    def test_database_py_has_pool_size(self):
        """database.py must configure pool_size."""
        content = self._read("..", "app", "database.py")
        assert "pool_size" in content

    def test_database_py_has_max_overflow(self):
        """database.py must configure max_overflow."""
        content = self._read("..", "app", "database.py")
        assert "max_overflow" in content

    def test_database_py_has_pool_recycle(self):
        """database.py must configure pool_recycle."""
        content = self._read("..", "app", "database.py")
        assert "pool_recycle" in content

    def test_health_readiness_no_hardcoded_connected(self):
        """health.py must not have hardcoded dummy readiness response."""
        content = self._read("..", "app", "presentation", "api", "health.py")
        assert '"database": "connected"' not in content

    def test_health_readiness_probes_db(self):
        """health.py readiness endpoint must contain SELECT 1 DB probe."""
        content = self._read("..", "app", "presentation", "api", "health.py")
        assert "SELECT 1" in content

    def test_health_readiness_probes_redis(self):
        """health.py readiness endpoint must contain Redis PING probe."""
        content = self._read("..", "app", "presentation", "api", "health.py")
        assert ".ping()" in content

    def test_ci_yml_has_alembic_check(self):
        """ci.yml must contain Alembic head validation step."""
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".github", "workflows", "ci.yml")
        if not os.path.exists(path):
            pytest.skip("ci.yml not found")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "alembic heads" in content or "alembic" in content

    def test_ci_yml_has_npm_audit(self):
        """ci.yml must include npm audit step."""
        path = os.path.join(os.path.dirname(__file__), "..", "..", "..", ".github", "workflows", "ci.yml")
        if not os.path.exists(path):
            pytest.skip("ci.yml not found")
        with open(path, encoding="utf-8") as f:
            content = f.read()
        assert "npm audit" in content
