import asyncio
import uuid
import traceback
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.acquisition_models import SourceAttribution
from app.models.lead import Lead
from app.models.organization import Organization

LEADSCORE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore"

async def test_reproduce():
    engine = create_async_engine(LEADSCORE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    print("=== STEP 2: REPRODUCE EXACT SOURCE_ATTRIBUTION FAILURE ON LEADSCORE (0048) ===")
    
    async with session_factory() as session:
        # Get an existing lead and org id
        lead_row = (await session.execute(select(Lead.id, Lead.organization_id).limit(1))).first()
        if not lead_row:
            print("No lead found!")
            return
        lead_id, org_id = lead_row
        print(f"Sample DB Record -> lead_id: {lead_id} (type: {type(lead_id)}), org_id: {org_id} (type: {type(org_id)})")

        # Test A: Query SourceAttribution with UUID parameter for organization_id
        print("\n--- Test A: select(SourceAttribution).where(SourceAttribution.organization_id == org_id) ---")
        try:
            stmt = select(SourceAttribution).where(SourceAttribution.organization_id == org_id)
            print(f"SQL: {stmt}")
            res = await session.execute(stmt)
            print("Result:", res.scalars().all())
        except Exception as e:
            print("FAILED as expected with exception:")
            traceback.print_exc()

        # Test B: Query SourceAttribution with UUID parameter for lead_id
        print("\n--- Test B: select(SourceAttribution).where(SourceAttribution.lead_id == lead_id) ---")
        try:
            stmt = select(SourceAttribution).where(SourceAttribution.lead_id == lead_id)
            print(f"SQL: {stmt}")
            res = await session.execute(stmt)
            print("Result:", res.scalars().all())
        except Exception as e:
            print("FAILED as expected with exception:")
            traceback.print_exc()

        # Test C: Join Lead and SourceAttribution: Lead.id == SourceAttribution.lead_id
        print("\n--- Test C: select(Lead, SourceAttribution).join(SourceAttribution, Lead.id == SourceAttribution.lead_id) ---")
        try:
            stmt = select(Lead, SourceAttribution).join(SourceAttribution, Lead.id == SourceAttribution.lead_id)
            print(f"SQL: {stmt}")
            res = await session.execute(stmt)
            print("Result:", res.all())
        except Exception as e:
            print("FAILED as expected with exception:")
            traceback.print_exc()

        # Test D: Query with str parameter for lead_id
        print("\n--- Test D: select(SourceAttribution).where(SourceAttribution.lead_id == str(lead_id)) ---")
        try:
            stmt = select(SourceAttribution).where(SourceAttribution.lead_id == str(lead_id))
            print(f"SQL: {stmt}")
            res = await session.execute(stmt)
            print("Result:", res.scalars().all())
        except Exception as e:
            print("FAILED with exception:")
            traceback.print_exc()

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_reproduce())

