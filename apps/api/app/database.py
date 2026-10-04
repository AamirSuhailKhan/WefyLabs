from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool
from app.config import settings

# ─── Connection Pool Configuration ───────────────────────────────────────────
# Tuned for Supabase/PgBouncer transaction-mode pooler.
# In production: pool_size=10 per worker (4 workers = 40 connections max).
# Supabase free tier allows 60 concurrent connections.
_IS_SQLITE = settings.DATABASE_URL.startswith("sqlite")
_IS_PROD = settings.ENV.lower() in ("production", "prod", "staging")
_IS_TEST = settings.ENV.lower() in ("testing", "test")

_engine_kwargs: dict = {
    "echo": False,
    "pool_pre_ping": True,          # Drop stale connections before use
    "pool_recycle": 1800,           # Recycle connections every 30 minutes
}

if _IS_TEST:
    # Under test runners (pytest-asyncio), NullPool prevents connections
    # from outliving individual test event loops.
    _engine_kwargs["poolclass"] = NullPool
    if _IS_SQLITE:
        _engine_kwargs["connect_args"] = {"check_same_thread": False}
elif _IS_SQLITE:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # PostgreSQL / asyncpg pool settings
    _engine_kwargs["pool_size"] = 10 if _IS_PROD else 5
    _engine_kwargs["max_overflow"] = 20 if _IS_PROD else 5
    _engine_kwargs["pool_timeout"] = 30          # Wait max 30s for a pool slot
    _engine_kwargs["connect_args"] = {
        "command_timeout": 20,                   # Kill queries exceeding 20s
        "server_settings": {
            "application_name": "wefylabs-api",
        }
    }

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)
async_session_maker = AsyncSessionLocal
async_session_factory = AsyncSessionLocal


class Base(AsyncAttrs, DeclarativeBase):
    """Base model class for SQLAlchemy 2.0 declarative models."""
    pass


async def get_db():
    """Async dependency yielding a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
