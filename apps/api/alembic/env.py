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

# Ensure .env is loaded without overriding existing environment variables
root_env = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../.env"))
load_dotenv(root_env, override=False)
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.env")), override=False)
load_dotenv(os.path.abspath(os.path.join(os.path.dirname(__file__), "../.env")), override=False)
load_dotenv(override=False)

from sqlalchemy import pool, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.config import settings

# Import Base and ALL 401 models so Alembic can detect complete schema changes.
from app.database import Base
import app.models

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    Used for generating SQL scripts without a live DB connection.
    """
    x_args = context.get_x_argument(as_dictionary=True)
    raw_url = x_args.get("db_url") or os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    url = raw_url.replace("+asyncpg", "").replace("+aiosqlite", "")
    target_schema = os.getenv("ALEMBIC_SCHEMA")
    kwargs = {
        "url": url,
        "target_metadata": target_metadata,
        "literal_binds": True,
        "dialect_opts": {"paramstyle": "named"},
        "render_as_batch": True,  # SQLite compatibility for ALTER TABLE
        "compare_type": True,
        "compare_server_default": True,
    }
    if target_schema:
        kwargs["version_table_schema"] = target_schema
    context.configure(**kwargs)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    target_schema = os.getenv("ALEMBIC_SCHEMA")
    if target_schema:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {target_schema}"))
        connection.execute(text(f"SET search_path TO {target_schema}, extensions"))
        table_name = f"{target_schema}.alembic_version"
    else:
        table_name = "alembic_version"

    # Ensure version_num column can hold longer revision names (e.g. 0039_build09_revenue_intelligence is 35 chars)
    if "postgresql" in connection.dialect.name:
        connection.execute(text(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                version_num VARCHAR(64) NOT NULL PRIMARY KEY
            )
        """))
        connection.execute(text(f"""
            ALTER TABLE {table_name} ALTER COLUMN version_num TYPE VARCHAR(64)
        """))

    kwargs = {
        "connection": connection,
        "target_metadata": target_metadata,
        "render_as_batch": True,   # SQLite compatibility
        "compare_type": True,
        "compare_server_default": True,
    }
    if target_schema:
        kwargs["version_table_schema"] = target_schema
    context.configure(**kwargs)

    with context.begin_transaction():
        context.run_migrations()


from sqlalchemy.ext.asyncio import create_async_engine

async def run_async_migrations() -> None:
    """Creates async engine and runs migrations against live database."""
    x_args = context.get_x_argument(as_dictionary=True)
    raw_url = x_args.get("db_url") or os.environ.get("DATABASE_URL") or settings.DATABASE_URL
    if "postgresql://" in raw_url and "+asyncpg" not in raw_url:
        raw_url = raw_url.replace("postgresql://", "postgresql+asyncpg://")

    connectable = create_async_engine(
        raw_url,
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
        await connection.commit()

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode against a live database."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
