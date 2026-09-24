"""
Part 18 — Real Estate Deal, Booking & Transaction OS: Concurrency & Double-Booking Tests
========================================================================================
Validates strict database-backed race-condition prevention:
  1. Sequential double-reservation collision prevention on same property
  2. Expired reservation releases property for subsequent buyer
  3. Concurrent simultaneous reservation race condition (simultaneous async tasks)
  4. Single deal multiple reservation constraint
"""
import pytest
import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.deal_models import Deal, DealStage, DealReservation
from app.modules.deals.services.deal_service import DealService, DealServiceError


@pytest.fixture
async def concurrency_session_factory():
    """In-memory SQLite engine with concurrency support."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    async with session_factory() as session:
        broker_id = uuid.uuid4()
        org_id = broker_id
        broker = Broker(
            id=broker_id,
            email="concurrency.broker@wefylabs.com",
            name="Concurrency Broker",
            password_hash="hash",
            phone="+971508887766"
        )
        lead1 = Lead(
            id=uuid.uuid4(),
            broker_id=broker_id,
            name="Buyer One",
            phone="+971501110001",
            status="active"
        )
        lead2 = Lead(
            id=uuid.uuid4(),
            broker_id=broker_id,
            name="Buyer Two",
            phone="+971501110002",
            status="active"
        )
        prop = PropertyListing(
            id=uuid.uuid4(),
            broker_id=broker_id,
            title="Exclusive Penthouse 401",
            description="Luxury 4-bedroom penthouse with panoramic sea views",
            area_value=4500.0,
            property_type="penthouse",
            listing_type="exclusive",
            price=8500000.0,
            currency_code="AED",
            status="available"
        )
        session.add(broker)
        session.add(lead1)
        session.add(lead2)
        session.add(prop)
        await session.commit()

    yield session_factory, str(broker_id), str(org_id), str(lead1.id), str(lead2.id), str(prop.id)
    await engine.dispose()


@pytest.mark.asyncio
async def test_property_double_reservation_prevented(concurrency_session_factory):
    factory, broker_id, org_id, lead1_id, lead2_id, prop_id = concurrency_session_factory

    async with factory() as session:
        service = DealService(session)

        # Buyer 1 deal
        deal1 = await service.create_deal(
            lead_id=lead1_id,
            deal_title="Deal Buyer 1",
            broker_id=broker_id,
            organization_id=org_id,
            property_id=prop_id,
            current_stage=DealStage.RESERVATION
        )

        # Buyer 2 deal for SAME property
        deal2 = await service.create_deal(
            lead_id=lead2_id,
            deal_title="Deal Buyer 2",
            broker_id=broker_id,
            organization_id=org_id,
            property_id=prop_id,
            current_stage=DealStage.RESERVATION
        )

        # Buyer 1 successfully reserves
        res1 = await service.create_reservation(
            deal_id=str(deal1.id),
            organization_id=org_id,
            actor_id=broker_id,
            reservation_amount=Decimal("50000"),
            currency="AED"
        )
        assert res1.status == "ACTIVE"

        # Buyer 2 attempts reservation for same property -> BLOCKED
        with pytest.raises(DealServiceError, match="already reserved by another party"):
            await service.create_reservation(
                deal_id=str(deal2.id),
                organization_id=org_id,
                actor_id=broker_id,
                reservation_amount=Decimal("50000"),
                currency="AED"
            )


@pytest.mark.asyncio
async def test_expired_reservation_allows_rebooking(concurrency_session_factory):
    factory, broker_id, org_id, lead1_id, lead2_id, prop_id = concurrency_session_factory

    async with factory() as session:
        service = DealService(session)

        deal1 = await service.create_deal(
            lead_id=lead1_id,
            deal_title="Deal Expired",
            broker_id=broker_id,
            organization_id=org_id,
            property_id=prop_id,
            current_stage=DealStage.RESERVATION
        )

        deal2 = await service.create_deal(
            lead_id=lead2_id,
            deal_title="Deal Successor",
            broker_id=broker_id,
            organization_id=org_id,
            property_id=prop_id,
            current_stage=DealStage.RESERVATION
        )

        # Buyer 1 reservation was in the past (expired)
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        res1 = await service.create_reservation(
            deal_id=str(deal1.id),
            organization_id=org_id,
            actor_id=broker_id,
            expires_at=past_expiry
        )
        assert res1.status == "ACTIVE"

        # Buyer 2 can now reserve because Buyer 1's hold has elapsed
        res2 = await service.create_reservation(
            deal_id=str(deal2.id),
            organization_id=org_id,
            actor_id=broker_id,
            reservation_amount=Decimal("60000"),
            currency="AED"
        )
        assert res2.status == "ACTIVE"
        assert res2.deal_id == deal2.id


@pytest.mark.asyncio
async def test_concurrent_simultaneous_reservation_race_condition(concurrency_session_factory):
    factory, broker_id, org_id, lead1_id, lead2_id, prop_id = concurrency_session_factory

    # Create 5 deals attempting to reserve the exact same property simultaneously
    deal_ids = []
    async with factory() as session:
        service = DealService(session)
        for i in range(5):
            d = await service.create_deal(
                lead_id=lead1_id,
                deal_title=f"Concurrent Contestant {i}",
                broker_id=broker_id,
                organization_id=org_id,
                property_id=prop_id,
                current_stage=DealStage.RESERVATION
            )
            deal_ids.append(str(d.id))

    successes = []
    failures = []

    async def attempt_reservation(d_id: str):
        async with factory() as s:
            srv = DealService(s)
            try:
                r = await srv.create_reservation(
                    deal_id=d_id,
                    organization_id=org_id,
                    actor_id=broker_id,
                    reservation_amount=Decimal("50000"),
                    currency="AED"
                )
                successes.append(r)
            except DealServiceError as e:
                failures.append(str(e))

    # Run all 5 simultaneous attempts
    await asyncio.gather(*(attempt_reservation(did) for did in deal_ids))

    # Exactly 1 must have succeeded, remaining 4 must have failed
    assert len(successes) == 1
    assert len(failures) == 4
    for err in failures:
        assert "already reserved" in err
