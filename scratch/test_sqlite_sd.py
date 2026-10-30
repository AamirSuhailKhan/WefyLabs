import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import text, String

class Base(DeclarativeBase):
    pass

class Test(Base):
    __tablename__ = 'test'
    id: Mapped[int] = mapped_column(primary_key=True)
    notes: Mapped[str] = mapped_column(String, server_default=text("'[]'"))

async def main():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
            print('SQLite create_all succeeded!')
        except Exception as e:
            print('SQLite create_all failed:', e)

asyncio.run(main())
