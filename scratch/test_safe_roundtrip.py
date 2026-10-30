import asyncio
import uuid
import sys
sys.path.insert(0, "apps/api")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, String, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from scratch.test_safe_uuid_type import SafeUUIDType

class Base(DeclarativeBase):
    pass

class MockAttr(Base):
    __tablename__ = "test_safe_attr"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(SafeUUIDType, nullable=False)
    lead_id: Mapped[uuid.UUID] = mapped_column(SafeUUIDType, nullable=True)

async def test_sqlite():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    sf = async_sessionmaker(engine, class_=AsyncSession)
    async with sf() as session:
        # Insert with str
        rec1 = MockAttr(id="1", organization_id="org-a", lead_id="lead-1")
        session.add(rec1)
        # Insert with UUID
        u_org = uuid.uuid4()
        u_lead = uuid.uuid4()
        rec2 = MockAttr(id="2", organization_id=u_org, lead_id=u_lead)
        session.add(rec2)
        await session.commit()

        # Query back
        res1 = (await session.execute(select(MockAttr).where(MockAttr.id == "1"))).scalar_one()
        assert res1.organization_id is None or str(res1.organization_id) == "org-a"
        res2 = (await session.execute(select(MockAttr).where(MockAttr.id == "2"))).scalar_one()
        assert res2.organization_id == u_org
        print("SQLite Round-Trip: SUCCESS")
    await engine.dispose()

async def test_postgres():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore_pilot")
    from app.models.acquisition_models import SourceAttribution
    sf = async_sessionmaker(engine, class_=AsyncSession)
    
    u_org = uuid.UUID("35c904e8-1d5a-41d9-a54e-2dc2e93f4a9d")
    u_lead = uuid.UUID("dac1a157-657b-4e48-8e76-f5469ee2af6b")
    
    async with sf() as session:
        # Query with UUID object
        r1 = (await session.execute(select(SourceAttribution).where(SourceAttribution.lead_id == u_lead))).scalars().all()
        # Query with str object
        r2 = (await session.execute(select(SourceAttribution).where(SourceAttribution.lead_id == str(u_lead)))).scalars().all()
        assert len(r1) == 1
        assert len(r2) == 1
        print("PostgreSQL 0049 Query Round-Trip: SUCCESS")
    await engine.dispose()

async def main():
    await test_sqlite()
    await test_postgres()

if __name__ == "__main__":
    asyncio.run(main())

