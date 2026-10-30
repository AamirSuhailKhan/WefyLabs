import asyncio
import uuid
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.acquisition_models import SourceAttribution
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.broker import Broker

PILOT_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore_pilot"

async def test_pg_behavior():
    engine = create_async_engine(PILOT_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    
    org_id = uuid.uuid4()
    broker_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    attr_id = str(uuid.uuid4())

    async with session_factory() as session:
        # Create prerequisite org, broker, and lead
        org = Organization(id=org_id, name="Attribution Test Org", slug=f"attr-org-{org_id.hex[:8]}")
        broker = Broker(id=broker_id, email=f"broker_{broker_id.hex[:6]}@test.com", name="Broker Test")
        lead = Lead(
            id=lead_id,
            organization_id=org_id,
            broker_id=broker_id,
            phone="+971501234567",
            name="Attribution Lead",
            source="WEBSITE",
            pipeline_stage="new"
        )
        session.add_all([org, broker, lead])
        await session.flush()

        # Insert SourceAttribution referencing lead via UUID
        attr = SourceAttribution(
            id=attr_id,
            organization_id=org_id,
            lead_id=lead_id,
            channel="WEBSITE",
            provider="meta_ads",
            created_at=datetime.now(timezone.utc)
        )
        session.add(attr)
        await session.flush()

        # Query 1: Filter by UUID object
        q1 = await session.execute(
            select(SourceAttribution).where(SourceAttribution.lead_id == lead_id)
        )
        res1 = q1.scalar_one_or_none()
        assert res1 is not None and res1.id == attr_id
        print("PG: Query 1 by UUID object: PASSED")

        # Query 2: Filter by str representation of UUID
        q2 = await session.execute(
            select(SourceAttribution).where(SourceAttribution.lead_id == str(lead_id))
        )
        res2 = q2.scalar_one_or_none()
        assert res2 is not None and res2.id == attr_id
        print("PG: Query 2 by str representation: PASSED")

        # Query 3: Join Lead and SourceAttribution
        join_q = await session.execute(
            select(Lead.id, SourceAttribution.channel).join(
                SourceAttribution, Lead.id == SourceAttribution.lead_id
            ).where(Lead.id == lead_id)
        )
        joined_row = join_q.first()
        assert joined_row is not None
        assert joined_row[0] == lead_id
        assert joined_row[1] == "WEBSITE"
        print("PG: Query 3 JOIN Lead.id == SourceAttribution.lead_id: PASSED")

        # Query 4: Delete the lead -> test SET NULL in PostgreSQL
        await session.delete(lead)
        await session.flush()

        # Expire / refresh session to see DB-level SET NULL trigger
        session.expire_all()
        refetched = (await session.execute(
            select(SourceAttribution).where(SourceAttribution.id == attr_id)
        )).scalar_one_or_none()
        assert refetched is not None
        assert refetched.lead_id is None, f"Expected lead_id to be None, got {refetched.lead_id}"
        print("PG: Query 4 ON DELETE SET NULL: PASSED")

        await session.rollback()

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_pg_behavior())

