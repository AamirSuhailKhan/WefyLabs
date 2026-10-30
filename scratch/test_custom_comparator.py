import asyncio
import uuid
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select, String, TypeDecorator, cast
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from app.models.lead import Lead

LEADSCORE_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore"
PILOT_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore_pilot"

class Base(DeclarativeBase):
    pass

class CompatibleUUID(TypeDecorator):
    impl = String(36)
    cache_ok = True

    class comparator_factory(TypeDecorator.Comparator):
        def __eq__(self, other):
            if other is None:
                return self.expr.is_(None)
            # Cast column to UUID in PostgreSQL so it compares cleanly with UUID or string
            return cast(self.expr, PG_UUID(as_uuid=True)) == (
                cast(other, PG_UUID(as_uuid=True)) if not isinstance(other, uuid.UUID) else other
            )

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(str(value)) if not isinstance(value, uuid.UUID) else value

class TestAttr(Base):
    __tablename__ = "source_attributions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID)
    lead_id: Mapped[uuid.UUID] = mapped_column(CompatibleUUID)

async def test_db(url, label):
    engine = create_async_engine(url, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession)
    
    test_org_uuid = uuid.UUID("35c904e8-1d5a-41d9-a54e-2dc2e93f4a9d")
    test_org_str = "35c904e8-1d5a-41d9-a54e-2dc2e93f4a9d"
    test_lead_uuid = uuid.UUID("dac1a157-657b-4e48-8e76-f5469ee2af6b")

    print(f"\n================ TESTING {label} ================")
    async with session_factory() as session:
        # 1. SELECT with UUID filter
        try:
            stmt = select(TestAttr).where(TestAttr.lead_id == test_lead_uuid)
            res = (await session.execute(stmt)).scalars().all()
            print(f"[{label}] SELECT with UUID filter: SUCCESS, found {len(res)} rows")
        except Exception as e:
            print(f"[{label}] SELECT with UUID filter: FAILED -> {e}")

        # 2. SELECT with str filter
        try:
            stmt = select(TestAttr).where(TestAttr.organization_id == test_org_str)
            res = (await session.execute(stmt)).scalars().all()
            print(f"[{label}] SELECT with str filter: SUCCESS, found {len(res)} rows")
        except Exception as e:
            print(f"[{label}] SELECT with str filter: FAILED -> {e}")

        # 3. JOIN with Lead table
        try:
            stmt = select(Lead.id, TestAttr.id).join(TestAttr, Lead.id == TestAttr.lead_id)
            res = (await session.execute(stmt)).all()
            print(f"[{label}] JOIN Lead.id == TestAttr.lead_id: SUCCESS, joined {len(res)} rows")
        except Exception as e:
            print(f"[{label}] JOIN Lead.id == TestAttr.lead_id: FAILED -> {e}")

        # 4. INSERT record and rollback
        try:
            new_id = str(uuid.uuid4())
            attr = TestAttr(id=new_id, organization_id=test_org_uuid, lead_id=test_lead_uuid)
            session.add(attr)
            await session.flush()
            print(f"[{label}] INSERT with flush: SUCCESS")
        except Exception as e:
            print(f"[{label}] INSERT with flush: FAILED -> {e}")
        finally:
            await session.rollback()

    await engine.dispose()

async def main():
    await test_db(LEADSCORE_URL, "0048 (leadscore - production)")
    await test_db(PILOT_URL, "0049 (leadscore_pilot - migrated)")

if __name__ == "__main__":
    asyncio.run(main())

