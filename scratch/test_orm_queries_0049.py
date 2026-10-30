import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.acquisition_models import SourceAttribution

PILOT_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore_pilot"

async def test_orm_queries():
    engine = create_async_engine(PILOT_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    
    lead_uuid = uuid.UUID("dac1a157-657b-4e48-8e76-f5469ee2af6b")
    lead_str = "dac1a157-657b-4e48-8e76-f5469ee2af6b"

    async with session_factory() as session:
        # 1. Query with UUID
        try:
            stmt = select(SourceAttribution).where(SourceAttribution.lead_id == lead_uuid)
            res = (await session.execute(stmt)).scalars().all()
            print(f"Query with UUID: SUCCESS, found {len(res)} records")
        except Exception as e:
            print(f"Query with UUID: FAILED -> {type(e).__name__}: {e}")

        # 2. Query with str
        try:
            stmt = select(SourceAttribution).where(SourceAttribution.lead_id == lead_str)
            res = (await session.execute(stmt)).scalars().all()
            print(f"Query with str: SUCCESS, found {len(res)} records")
        except Exception as e:
            print(f"Query with str: FAILED -> {type(e).__name__}: {e}")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_orm_queries())

