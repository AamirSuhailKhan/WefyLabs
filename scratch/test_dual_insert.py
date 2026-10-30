import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text

LEADSCORE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore"
PILOT_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore_pilot"

async def test_insert(url, name):
    engine = create_async_engine(url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    
    test_id = str(uuid.uuid4())
    test_org = "35c904e8-1d5a-41d9-a54e-2dc2e93f4a9d"
    test_lead = "dac1a157-657b-4e48-8e76-f5469ee2af6b"

    async with session_factory() as session:
        # Test 1: Insert using plain SQL text with string parameters
        try:
            await session.execute(
                text("INSERT INTO source_attributions (id, organization_id, lead_id, created_at) VALUES (:id, :org, :lead, NOW())"),
                {"id": test_id, "org": test_org, "lead": test_lead}
            )
            print(f"[{name}] INSERT with string parameters: SUCCESS")
        except Exception as e:
            print(f"[{name}] INSERT with string parameters: FAILED -> {e}")
        finally:
            await session.rollback()

    await engine.dispose()

async def main():
    await test_insert(LEADSCORE_URL, "0048 (leadscore)")
    await test_insert(PILOT_URL, "0049 (leadscore_pilot)")

if __name__ == "__main__":
    asyncio.run(main())

