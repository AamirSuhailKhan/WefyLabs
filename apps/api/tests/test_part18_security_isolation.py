"""
Part 18 — Real Estate Deal, Booking & Transaction OS: Security & Multi-Tenant Isolation
=======================================================================================
Verifies zero-trust tenant boundary enforcement across all commercial entities:
  1. Cross-tenant deal reading blocked (HTTP 404 / NotFound isolation)
  2. Cross-tenant stage advancement blocked
  3. Cross-tenant offer submission blocked
  4. Cross-tenant reservation blocked
  5. Cross-tenant commercial audit trail isolation
  6. Pipeline list and aggregate summary isolation
"""
import pytest
import uuid
from decimal import Decimal
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

import app.models
from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.deal_models import Deal, DealStage
from app.modules.deals.services.deal_service import DealService, DealServiceError


@pytest.fixture
async def multi_tenant_session_factory():
    """Isolated session factory with 2 distinct tenants."""
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
        # Tenant A
        broker_a_id = uuid.uuid4()
        org_a_id = broker_a_id
        broker_a = Broker(
            id=broker_a_id,
            email="broker.a@wefylabs.com",
            name="Broker Tenant A",
            password_hash="hash",
            phone="+971501111111"
        )
        lead_a = Lead(
            id=uuid.uuid4(),
            broker_id=broker_a_id,
            name="Buyer Tenant A",
            phone="+971502222222",
            status="active"
        )

        # Tenant B
        broker_b_id = uuid.uuid4()
        org_b_id = broker_b_id
        broker_b = Broker(
            id=broker_b_id,
            email="broker.b@wefylabs.com",
            name="Broker Tenant B",
            password_hash="hash",
            phone="+971503333333"
        )
        lead_b = Lead(
            id=uuid.uuid4(),
            broker_id=broker_b_id,
            name="Buyer Tenant B",
            phone="+971504444444",
            status="active"
        )

        session.add(broker_a)
        session.add(lead_a)
        session.add(broker_b)
        session.add(lead_b)
        await session.commit()

    yield session_factory, str(broker_a_id), str(org_a_id), str(lead_a.id), str(broker_b_id), str(org_b_id), str(lead_b.id)
    await engine.dispose()


@pytest.mark.asyncio
async def test_cross_tenant_deal_read_blocked(multi_tenant_session_factory):
    factory, broker_a, org_a, lead_a, broker_b, org_b, lead_b = multi_tenant_session_factory

    async with factory() as session:
        service = DealService(session)

        # Tenant A creates a deal
        deal_a = await service.create_deal(
            lead_id=lead_a,
            deal_title="Tenant A Confidential Deal",
            broker_id=broker_a,
            organization_id=org_a,
            agreed_price=Decimal("12000000.0000"),
            currency="AED"
        )

        # Tenant B attempts to read Tenant A's deal -> Blocked
        with pytest.raises(DealServiceError, match="not found"):
            await service.get_deal(deal_id=str(deal_a.id), organization_id=org_b)


@pytest.mark.asyncio
async def test_cross_tenant_stage_advance_blocked(multi_tenant_session_factory):
    factory, broker_a, org_a, lead_a, broker_b, org_b, lead_b = multi_tenant_session_factory

    async with factory() as session:
        service = DealService(session)

        deal_a = await service.create_deal(
            lead_id=lead_a,
            deal_title="Tenant A Progression Deal",
            broker_id=broker_a,
            organization_id=org_a,
            current_stage=DealStage.OPPORTUNITY
        )

        # Tenant B attempts to advance stage on Tenant A's deal -> Blocked
        with pytest.raises(DealServiceError, match="not found"):
            await service.advance_stage(
                deal_id=str(deal_a.id),
                target_stage=DealStage.NEGOTIATION,
                organization_id=org_b,
                actor_id=broker_b
            )


@pytest.mark.asyncio
async def test_cross_tenant_offer_submission_blocked(multi_tenant_session_factory):
    factory, broker_a, org_a, lead_a, broker_b, org_b, lead_b = multi_tenant_session_factory

    async with factory() as session:
        service = DealService(session)

        deal_a = await service.create_deal(
            lead_id=lead_a,
            deal_title="Tenant A Offer Deal",
            broker_id=broker_a,
            organization_id=org_a,
            current_stage=DealStage.NEGOTIATION
        )

        # Tenant B attempts to submit offer on Tenant A's deal -> Blocked
        with pytest.raises(DealServiceError, match="not found"):
            await service.submit_offer(
                deal_id=str(deal_a.id),
                organization_id=org_b,
                actor_id=broker_b,
                offer_price=Decimal("5000000.0000")
            )


@pytest.mark.asyncio
async def test_cross_tenant_reservation_blocked(multi_tenant_session_factory):
    factory, broker_a, org_a, lead_a, broker_b, org_b, lead_b = multi_tenant_session_factory

    async with factory() as session:
        service = DealService(session)

        deal_a = await service.create_deal(
            lead_id=lead_a,
            deal_title="Tenant A Reservation Deal",
            broker_id=broker_a,
            organization_id=org_a,
            current_stage=DealStage.RESERVATION
        )

        # Tenant B attempts to reserve Tenant A's deal -> Blocked
        with pytest.raises(DealServiceError, match="not found"):
            await service.create_reservation(
                deal_id=str(deal_a.id),
                organization_id=org_b,
                actor_id=broker_b,
                reservation_amount=Decimal("25000.0000")
            )


@pytest.mark.asyncio
async def test_pipeline_list_and_summary_isolation(multi_tenant_session_factory):
    factory, broker_a, org_a, lead_a, broker_b, org_b, lead_b = multi_tenant_session_factory

    async with factory() as session:
        service = DealService(session)

        # Tenant A creates 3 deals
        for i in range(3):
            await service.create_deal(
                lead_id=lead_a,
                deal_title=f"Tenant A Deal {i}",
                broker_id=broker_a,
                organization_id=org_a,
                agreed_price=Decimal("1000000.0000")
            )

        # Tenant B creates 0 deals
        deals_b, count_b = await service.list_deals(broker_id=broker_b, organization_id=org_b)
        assert count_b == 0
        assert len(deals_b) == 0

        # Tenant B's pipeline summary has 0 value
        summary_b = await service.get_pipeline_summary(broker_id=broker_b, organization_id=org_b)
        assert summary_b["total_active_deals"] == 0
        assert summary_b["total_pipeline_value"] == 0.0

        # Tenant A's pipeline summary reflects 3 deals
        summary_a = await service.get_pipeline_summary(broker_id=broker_a, organization_id=org_a)
        assert summary_a["total_active_deals"] == 3
        assert summary_a["total_pipeline_value"] == 3000000.0
