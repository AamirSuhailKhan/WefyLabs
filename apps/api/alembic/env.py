"""
BeetleLabs Alembic Migration Environment
==========================================
Async Alembic configuration for PostgreSQL (production) and SQLite (testing).

To generate a new migration:
    alembic revision --autogenerate -m "description_of_change"

To apply migrations:
    alembic upgrade head

To rollback one step:
    alembic downgrade -1

To show current revision:
    alembic current
"""
import asyncio
import os
from logging.config import fileConfig
from dotenv import load_dotenv

# Ensure .env is loaded from workspace root (3 levels up) or apps/api
root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.env"))
load_dotenv(root_env, override=True)
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.env")), override=False)
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env")), override=False)
load_dotenv(override=False)

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.config import settings

# Import Base and ALL models so Alembic can detect schema changes.
# Every new model file must be imported here.
from app.database import Base
import app.models.broker
import app.models.lead
import app.models.conversation
import app.models.score
import app.models.follow_up
import app.models.subscription
import app.models.crm_models
import app.models.organization
import app.models.audit_log
import app.models.communication_models
import app.models.property_models
import app.models.transaction_models
import app.models.workflow_models
import app.models.developer_models

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Used for generating SQL scripts without a live DB connection.
    """
    raw_url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    url = raw_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # SQLite compatibility for ALTER TABLE
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,   # SQLite compatibility
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


from sqlalchemy.ext.asyncio import create_async_engine

async def run_async_migrations() -> None:
    """Creates async engine and runs migrations against live database."""
    raw_url = os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    if "postgresql://" in raw_url and "+asyncpg" not in raw_url:
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://")

    connectable = create_async_engine(
        raw_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
