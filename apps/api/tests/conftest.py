import asyncio
import os
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

# Phase 0 P0.1: Ensure default testing environment before application imports.
# This guarantees OAuth state/replay store uses bounded in-memory backend and
# mock-disabled production paths stay disabled regardless of local .env.
os.environ.setdefault("ENV", "testing")
from app.config import settings

@pytest.fixture(autouse=True)
def scope_test_environment(monkeypatch):
    """Enforces strict per-test environment isolation.
    Guarantees default ENV is 'testing' for each test, while allowing individual
    tests to monkeypatch or patch settings.ENV to 'development' or 'production'
    without leaking side-effects across test runs."""
    monkeypatch.setenv("ENV", "testing")
    monkeypatch.setattr(settings, "ENV", "testing")
    yield



from app.models import Base, Broker, Lead  # noqa: E402

# In-memory SQLite for fast isolated testing
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
        await session.rollback()
        
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def db(db_session: AsyncSession) -> AsyncSession:
    """Convenience alias for db_session fixture."""
    return db_session

@pytest_asyncio.fixture(scope="function")
async def test_broker(db_session: AsyncSession) -> Broker:
    broker = Broker(
        email="testbroker@example.com",
        phone="+919876543210",
        name="Test Broker",
        agency_name="Premier Properties",
        city="Bengaluru",
        whatsapp_number="+919876543210",
        subscription_status="trial"
    )
    db_session.add(broker)
    await db_session.commit()
    await db_session.refresh(broker)
    return broker

@pytest_asyncio.fixture(scope="function")
async def test_lead(db_session: AsyncSession, test_broker: Broker) -> Lead:
    lead = Lead(
        broker_id=test_broker.id,
        phone="+919812345678",
        name="Test Lead",
        source="whatsapp_forward",
        score="hot",
        score_confidence=0.92,
        budget_min=5000000,
        budget_max=7500000,
        property_type="2bhk",
        transaction_type="buy",
        preferred_locations=["Indiranagar", "Koramangala"],
        timeline="1_month",
        loan_status="in_process",
        status="active",
        pipeline_stage="contacted"
    )
    db_session.add(lead)
    await db_session.commit()
    await db_session.refresh(lead)
    return lead
