import asyncio
import uuid
import traceback
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

PILOT_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore_pilot"

class Base(DeclarativeBase):
    pass

class StringAttribution(Base):
    __tablename__ = "source_attributions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    lead_id: Mapped[str] = mapped_column(String(36))

async def test():
    engine = create_async_engine(PILOT_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)

    test_lead_id = "dac1a157-657b-4e48-8e76-f5469ee2af6b"
    async with session_factory() as session:
        try:
            stmt = select(StringAttribution).where(StringAttribution.lead_id == test_lead_id)
            print("SQL:", stmt)
            res = await session.execute(stmt)
            print("Result with String(36) on 0049:", res.scalars().all())
        except Exception as e:
            print("FAILED with:")
            traceback.print_exc()

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test())

