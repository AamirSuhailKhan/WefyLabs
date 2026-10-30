"""
test_startup_ddl_guards.py
Unit tests verifying that AUTO_CREATE_SCHEMA_ON_STARTUP=True fails closed in production and staging environments (Master Prompt 10 Section 6).
"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.common.config.validated_settings import EnterpriseSettings
from app.main import lifespan


def test_production_config_rejects_auto_create_schema():
    """Verify validate_production_security aborts startup if AUTO_CREATE_SCHEMA_ON_STARTUP is True in prod."""
    with pytest.raises(ValueError) as excinfo:
        EnterpriseSettings(
            ENV="production",
            SECRET_KEY="a" * 32,
            SUPABASE_JWT_SECRET="b" * 32,
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/leadscore_prod",
            GEMINI_API_KEY="valid_gemini_key_prod",
            WHATSAPP_VERIFY_TOKEN="c" * 32,
            RAZORPAY_KEY_ID="rzp_live_1234567890",
            RAZORPAY_KEY_SECRET="valid_razorpay_secret_live",
            RAZORPAY_WEBHOOK_SECRET="d" * 32,
            RAZORPAY_ENVIRONMENT="live",
            GOOGLE_CLIENT_ID="valid_app.apps.googleusercontent.com",
            GOOGLE_CLIENT_SECRET="valid_google_client_secret",
            STORAGE_BACKEND="s3",
            AUTO_CREATE_SCHEMA_ON_STARTUP=True,
        )
    assert "AUTO_CREATE_SCHEMA_ON_STARTUP=True is strictly prohibited" in str(excinfo.value)


def test_staging_config_rejects_auto_create_schema():
    """Verify validate_production_security aborts startup if AUTO_CREATE_SCHEMA_ON_STARTUP is True in staging."""
    with pytest.raises(ValueError) as excinfo:
        EnterpriseSettings(
            ENV="staging",
            SECRET_KEY="a" * 32,
            SUPABASE_JWT_SECRET="b" * 32,
            DATABASE_URL="postgresql+asyncpg://user:pass@localhost:5432/leadscore_staging",
            GEMINI_API_KEY="valid_gemini_key_staging",
            WHATSAPP_VERIFY_TOKEN="c" * 32,
            RAZORPAY_KEY_ID="rzp_test_1234567890",
            RAZORPAY_KEY_SECRET="valid_razorpay_secret_staging",
            RAZORPAY_WEBHOOK_SECRET="d" * 32,
            RAZORPAY_ENVIRONMENT="test",
            GOOGLE_CLIENT_ID="valid_app.apps.googleusercontent.com",
            GOOGLE_CLIENT_SECRET="valid_google_client_secret",
            STORAGE_BACKEND="local",
            AUTO_CREATE_SCHEMA_ON_STARTUP=True,
        )
    assert "AUTO_CREATE_SCHEMA_ON_STARTUP=True is strictly prohibited" in str(excinfo.value)


@pytest.mark.asyncio
async def test_main_lifespan_fails_closed_on_postgres_prod_auto_create():
    """Verify main.py lifespan raises RuntimeError if auto_create is True on postgres in production."""
    mock_app = MagicMock()
    mock_engine = MagicMock()
    mock_engine.dialect.name = "postgresql"

    mock_settings = MagicMock()
    mock_settings.ENV = "production"
    mock_settings.AUTO_CREATE_SCHEMA_ON_STARTUP = True

    with patch("app.main.engine", mock_engine), \
         patch("app.main.settings", mock_settings), \
         patch("app.main.register_default_subscribers"):
        with pytest.raises(RuntimeError) as excinfo:
            async with lifespan(mock_app):
                pass

        assert "[DB Security Violation]" in str(excinfo.value)

