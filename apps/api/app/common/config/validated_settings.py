"""
BeetleLabs Central Config & Validation Module
=============================================
Fail-fast configuration validation.
Validates environment variables at application startup.
Ensures insecure defaults (placeholders, weak secret keys) are rejected in production.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import List, Union, Optional
from dotenv import load_dotenv
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger("beetlelabs.config")

# Calculate absolute paths to project directories
API_DIR = Path(__file__).resolve().parent.parent.parent.parent
REPO_ROOT = API_DIR.parent.parent

# Explicitly load .env files with repo root taking canonical precedence
if (REPO_ROOT / ".env").exists():
    load_dotenv(REPO_ROOT / ".env", override=True)
if (API_DIR / ".env").exists():
    load_dotenv(API_DIR / ".env", override=False)
if (REPO_ROOT / ".env.local").exists():
    load_dotenv(REPO_ROOT / ".env.local", override=True)
if (API_DIR / ".env.local").exists():
    load_dotenv(API_DIR / ".env.local", override=True)
load_dotenv(Path.cwd() / ".env", override=False)

DEFAULT_SECRET_KEY = "beetlelabs_super_secret_jwt_key_2026_change_in_prod"
DEFAULT_SUPABASE_SECRET = "supabase_jwt_secret_placeholder_32b_dev"


class EnterpriseSettings(BaseSettings):
    PROJECT_NAME: str = "WefyLabs API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"

    # Database & Cache
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore"
    REDIS_URL: str = "redis://localhost:6379/0"

    # AI Engine Keys (Google Gemini is the Primary & Sole AI Provider)
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-3.5-flash"

    # WhatsApp Meta Cloud Direct / 360Dialog
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    PHONE_NUMBER_ID: Optional[str] = None
    WABA_ID: Optional[str] = None
    WHATSAPP_VERIFY_TOKEN: str = "beetlelabs_webhook_secret_123"
    WHATSAPP_API_KEY: str = "wa-placeholder"
    DIALOG360_API_KEY: str = "d360_key_placeholder"
    DIALOG360_API_BASE: str = "https://waba.360dialog.io/v1"

    # Email SMTP (Brevo Free via SMTP / Generic SMTP)
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: Optional[str] = "noreply@wefylabs.com"
    EMAIL_FROM_ADDRESS: Optional[str] = None
    SMTP_FROM_NAME: str = "WefyLabs Real Estate"
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_SECURITY: Optional[str] = "STARTTLS"

    # Razorpay Payments
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder"
    RAZORPAY_KEY_SECRET: str = "secret_placeholder"
    RAZORPAY_WEBHOOK_SECRET: str = "whsec_placeholder"
    RAZORPAY_ENVIRONMENT: str = "test"  # "test" | "live"
    RAZORPAY_ACCOUNT_ID: Optional[str] = None
    PAYMENTS_EMERGENCY_PAUSE: bool = False

    # Supabase Auth
    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_JWT_SECRET: str = DEFAULT_SUPABASE_SECRET

    # Google OAuth 2.0
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:3000/auth/callback"
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # Security
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    WHATSAPP_APP_SECRET: Optional[str] = None
    # This is deliberately separate from tenant roles. Platform operations are
    # not a tenant capability and must fail closed until operators are named.
    SUPER_ADMIN_EMAILS: List[str] = []

    # Knowledge & Local OCR
    KNOWLEDGE_STORAGE_PROVIDER: str = "local"
    KNOWLEDGE_STORAGE_ROOT: str = "./storage/knowledge"
    KNOWLEDGE_MAX_UPLOAD_MB: int = 50
    KNOWLEDGE_EMBEDDING_PROVIDER: str = "gemini"
    KNOWLEDGE_EMBEDDING_MODEL: str = "gemini-embedding-001"
    KNOWLEDGE_VECTOR_STORE_PROVIDER: str = "pgvector"
    KNOWLEDGE_OCR_PROVIDER: str = "tesseract"
    KNOWLEDGE_OCR_CONFIDENCE_THRESHOLD: float = 0.7
    KNOWLEDGE_RERANKER_PROVIDER: str = "score_boost"
    EMERGENCY_ALLOW_MOCK_OCR: bool = False

    # Observability & Alerting Destinations
    ALERT_SLACK_WEBHOOK_URL: Optional[str] = None
    ALERT_PAGERDUTY_ROUTING_KEY: Optional[str] = None
    ALERT_WEBHOOK_URL: Optional[str] = None

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://wefylabs.com",
        "https://app.wefylabs.com",
        "https://api.wefylabs.com",
        "https://*.wefylabs.com",
        "https://beetlelabs.ai",
        "https://*.beetlelabs.ai"
    ]

    @field_validator("DATABASE_URL", mode="before")
    def ensure_asyncpg_dialect(cls, v: str) -> str:
        if isinstance(v, str) and v.startswith("postgresql://") and not v.startswith("postgresql+asyncpg://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("CORS_ORIGINS", "SUPER_ADMIN_EMAILS", mode="before")
    def parse_comma_separated_values(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    @model_validator(mode="before")
    @classmethod
    def resolve_aliases_and_sanitize(cls, data: dict) -> dict:
        if not isinstance(data, dict):
            return data

        # 1. Resolve Google Client ID aliases & sanitize
        client_id = data.get("GOOGLE_CLIENT_ID")
        if not client_id or (isinstance(client_id, str) and "placeholder" in client_id.lower()):
            alias_id = (
                data.get("GOOGLE_OAUTH_CLIENT_ID")
                or data.get("GOOGLE_CLIENTID")
                or os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
                or os.environ.get("GOOGLE_CLIENTID")
            )
            if alias_id:
                client_id = alias_id
        if not client_id:
            client_id = os.environ.get("GOOGLE_CLIENT_ID")

        if isinstance(client_id, str):
            client_id = client_id.strip().strip("'\"").strip()
            data["GOOGLE_CLIENT_ID"] = client_id

        # 2. Resolve Google Client Secret aliases & sanitize
        client_secret = data.get("GOOGLE_CLIENT_SECRET")
        if not client_secret or (isinstance(client_secret, str) and "placeholder" in client_secret.lower()):
            alias_secret = (
                data.get("GOOGLE_OAUTH_CLIENT_SECRET")
                or data.get("GOOGLE_OAUTH_SECRET")
                or data.get("GOOGLE_SECRET")
                or data.get("GOOGLE_CLIENT_SECRET_KEY")
                or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
                or os.environ.get("GOOGLE_OAUTH_SECRET")
                or os.environ.get("GOOGLE_SECRET")
                or os.environ.get("GOOGLE_CLIENT_SECRET_KEY")
            )
            if alias_secret:
                client_secret = alias_secret
        if not client_secret:
            client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")

        if isinstance(client_secret, str):
            client_secret = client_secret.strip().strip("'\"").strip()
            data["GOOGLE_CLIENT_SECRET"] = client_secret

        # 3. Resolve Google OAuth Redirect URI aliases & sanitize
        redirect_uri = data.get("GOOGLE_OAUTH_REDIRECT_URI")
        if not redirect_uri:
            redirect_uri = (
                data.get("GOOGLE_REDIRECT_URI")
                or data.get("GOOGLE_CALLBACK_URL")
                or os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
                or os.environ.get("GOOGLE_REDIRECT_URI")
                or os.environ.get("GOOGLE_CALLBACK_URL")
            )
        if isinstance(redirect_uri, str):
            redirect_uri = redirect_uri.strip().strip("'\"").strip()
            data["GOOGLE_OAUTH_REDIRECT_URI"] = redirect_uri
            data["GOOGLE_REDIRECT_URI"] = redirect_uri

        return data

    @model_validator(mode="after")
    def validate_production_security(self) -> EnterpriseSettings:
        """
        Fail-fast check for production environments.
        Aborts execution if insecure secret keys, weak tokens, or fallback placeholders are used in prod/staging.
        """
        is_prod = self.ENV.lower() in ("production", "prod", "staging")

        if is_prod:
            errors = []
            # 1. JWT & Encryption Secrets
            if self.SECRET_KEY in (DEFAULT_SECRET_KEY, "leadscore_super_secret_jwt_key_2026_change_in_prod") or len(self.SECRET_KEY) < 32:
                errors.append("SECRET_KEY must be a cryptographically random string with minimum 32 characters entropy!")
            if self.SUPABASE_JWT_SECRET == DEFAULT_SUPABASE_SECRET or "placeholder" in (self.SUPABASE_JWT_SECRET or ""):
                errors.append("SUPABASE_JWT_SECRET is using the default development placeholder!")
            
            # 2. Database
            if self.DATABASE_URL.startswith("sqlite"):
                errors.append("SQLite is not allowed in production! Configure PostgreSQL with pgvector.")
            
            # 3. AI Provider: Google Gemini
            has_gemini = bool(
                self.GEMINI_API_KEY 
                and not self.GEMINI_API_KEY.startswith("placeholder") 
                and not self.GEMINI_API_KEY.startswith("AIzaSy_placeholder")
            )
            if not has_gemini:
                errors.append("GEMINI_API_KEY is not configured with production credentials!")
            
            # 4. WhatsApp Webhook Token
            known_dummy_tokens = {"beetlelabs_webhook_secret_123", "leadscore_webhook_secret_123", "placeholder", "wa-placeholder"}
            if not self.WHATSAPP_VERIFY_TOKEN or self.WHATSAPP_VERIFY_TOKEN in known_dummy_tokens or len(self.WHATSAPP_VERIFY_TOKEN) < 32:
                errors.append("WHATSAPP_VERIFY_TOKEN must be a secure, random secret with minimum 32 characters entropy!")
            
            # 5. Razorpay Production Credentials (if production environment)
            if self.ENV.lower() in ("production", "prod"):
                # In production: must use live keys
                if self.RAZORPAY_KEY_ID.startswith("rzp_test_") or self.RAZORPAY_KEY_ID in ("rzp_test_placeholder", "rzp_test_dummy"):
                    errors.append("RAZORPAY_KEY_ID must use a production key (rzp_live_*) in production environment!")
                if self.RAZORPAY_KEY_SECRET in ("secret_placeholder", "placeholder") or not self.RAZORPAY_KEY_SECRET:
                    errors.append("RAZORPAY_KEY_SECRET cannot use placeholder in production environment!")
                if self.RAZORPAY_WEBHOOK_SECRET in ("whsec_placeholder", "placeholder") or len(self.RAZORPAY_WEBHOOK_SECRET) < 32:
                    errors.append("RAZORPAY_WEBHOOK_SECRET must be configured with minimum 32 characters in production!")

            # 5a. Razorpay — guard against live environment with test keys (any env)
            if self.RAZORPAY_ENVIRONMENT == "live":
                if not self.RAZORPAY_KEY_ID.startswith("rzp_live_"):
                    errors.append("RAZORPAY_ENVIRONMENT is 'live' but RAZORPAY_KEY_ID does not use an 'rzp_live_*' key!")
                if self.ENV.lower() == "staging":
                    errors.append("RAZORPAY_ENVIRONMENT cannot be 'live' in a staging environment! Use 'test' mode for staging.")

            # 6. OCR Provider Safety
            if self.ENV.lower() in ("production", "prod") and not self.EMERGENCY_ALLOW_MOCK_OCR:
                if self.KNOWLEDGE_OCR_PROVIDER == "mock":
                    errors.append("KNOWLEDGE_OCR_PROVIDER cannot be 'mock' in production! Configure 'tesseract' or 'local'.")

            # 7. Google OAuth Client Configuration (Production)
            if self.ENV.lower() in ("production", "prod"):
                if not self.GOOGLE_CLIENT_ID or "placeholder" in self.GOOGLE_CLIENT_ID.lower() or not self.GOOGLE_CLIENT_ID.endswith(".apps.googleusercontent.com"):
                    errors.append("GOOGLE_CLIENT_ID must be a valid Google OAuth Client ID ending with '.apps.googleusercontent.com' in production!")
                if not self.GOOGLE_CLIENT_SECRET or "placeholder" in self.GOOGLE_CLIENT_SECRET.lower():
                    errors.append("GOOGLE_CLIENT_SECRET cannot be a placeholder in production!")

            if errors:
                error_msg = "\n".join(f" - [CRITICAL CONFIG ERROR] {e}" for e in errors)
                logger.critical(f"\n=========================================\nPROD CONFIG VALIDATION FAILED:\n{error_msg}\n=========================================")
                raise ValueError(f"Production environment configuration invalid:\n{error_msg}")

        return self

    model_config = SettingsConfigDict(
        env_file=(
            str(REPO_ROOT / ".env"),
            str(API_DIR / ".env"),
            str(REPO_ROOT / ".env.local"),
            str(API_DIR / ".env.local"),
            ".env",
            "../.env"
        ),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


def load_settings() -> EnterpriseSettings:
    try:
        return EnterpriseSettings()
    except Exception as e:
        logger.error(f"Failed to load or validate settings: {e}")
        raise
