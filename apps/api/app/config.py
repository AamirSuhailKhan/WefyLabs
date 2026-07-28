from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "BeetleLabs API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    ENV: str = "development"
    
    # Required Environment Variables
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore"
    REDIS_URL: str = "redis://localhost:6379/0"
    OPENAI_API_KEY: str = "sk-placeholder"
    GEMINI_API_KEY: Optional[str] = None
    WHATSAPP_API_KEY: str = "wa-placeholder"
    DIALOG360_API_KEY: str = "d360_key_placeholder"
    DIALOG360_API_BASE: str = "https://waba.360dialog.io/v1"
    
    # Meta Cloud API Direct (Free 1,000 conversations/month)
    WHATSAPP_ACCESS_TOKEN: Optional[str] = None
    PHONE_NUMBER_ID: Optional[str] = None
    WABA_ID: Optional[str] = None  # WhatsApp Business Account ID
    WHATSAPP_VERIFY_TOKEN: str = "beetlelabs_webhook_secret_123"

    # Razorpay Payments
    RAZORPAY_KEY_ID: str = "rzp_test_placeholder"
    RAZORPAY_KEY_SECRET: str = "secret_placeholder"
    RAZORPAY_WEBHOOK_SECRET: str = "whsec_placeholder"
    
    # Supabase Auth
    SUPABASE_URL: str = "https://placeholder.supabase.co"
    SUPABASE_JWT_SECRET: str = "supabase_jwt_secret_placeholder"
    
    # Security
    SECRET_KEY: str = "beetlelabs_super_secret_jwt_key_2026_change_in_prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://beetlelabs.ai",
        "https://*.beetlelabs.ai"
    ]

    @field_validator("CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> Union[List[str], str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",")]
        elif isinstance(v, (list, str)):
            return v
        raise ValueError(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
