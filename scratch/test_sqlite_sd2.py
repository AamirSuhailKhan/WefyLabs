import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import text, String, Boolean, DateTime
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.expression import FunctionElement
from datetime import datetime

class DefaultTrialEndsAt(FunctionElement):
    name = "default_trial_ends_at"

@compiles(DefaultTrialEndsAt, "postgresql")
def compile_pg(element, compiler, **kw):
    return "now() + interval '7 days'"

@compiles(DefaultTrialEndsAt, "sqlite")
def compile_sqlite(element, compiler, **kw):
    return "datetime('now', '+7 days')"

class Base(DeclarativeBase):
    pass

class Test(Base):
    __tablename__ = 'test_sqlite_all'
    id: Mapped[str] = mapped_column(String, primary_key=True, server_default=text("gen_random_uuid()"))
    trial: Mapped[datetime] = mapped_column(DateTime, server_default=DefaultTrialEndsAt())
    is_demo: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    notes: Mapped[str] = mapped_column(String, server_default=text("'[]'"))

async def main():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
            print('SQLite create_all succeeded with DefaultTrialEndsAt!')
        except Exception as e:
            print('SQLite create_all failed:', e)

asyncio.run(main())
