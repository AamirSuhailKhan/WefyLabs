import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from app.models.acquisition_models import SourceAttribution

PILOT_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore_pilot"

async def test_insert_strings():
    engine = create_async_engine(PILOT_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    
    async with session_factory() as session:
        # Pass STRINGS for organization_id and lead_id
        attr = SourceAttribution(
            id=str(uuid.uuid4()),
            organization_id="35c904e8-1d5a-41d9-a54e-2dc2e93f4a9d",
            lead_id="dac1a157-657b-4e48-8e76-f5469ee2af6b",
            channel="WEBSITE",
            provider="meta_ads"
        )
        session.add(attr)
        try:
            await session.flush()
            print("Flushed SourceAttribution with STRINGS on 0049: SUCCESS")
        except Exception as e:
            print(f"Flushed SourceAttribution with STRINGS on 0049: FAILED -> {type(e).__name__}: {e}")
        finally:
            await session.rollback()

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_insert_strings())

