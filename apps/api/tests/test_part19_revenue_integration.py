"""
Part 19 — Real Estate Revenue Integration & Demand-to-Supply Journey
====================================================================
Tests the full unified real estate transaction OS lifecycle:
  1. Project + Unit created on Supply Side
  2. Lead arrives with Channel Partner attribution
  3. Lead converts to Deal OS transaction
  4. Unit reserved atomically:
     - ProjectUnit status transitions AVAILABLE -> RESERVED
     - Transactional Outbox emits 'inventory.unit.reserved'
  5. Booking confirmed:
     - ProjectUnit status transitions RESERVED -> BOOKED
     - Transactional Outbox emits 'inventory.unit.booked'
  6. Closing completed:
     - ProjectUnit status transitions BOOKED -> SOLD
     - Transactional Outbox emits 'inventory.unit.sold'
  7. Channel Partner Commission recorded in the revenue ledger
"""
import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select

import app.models
from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.deal_models import Deal, DealStage
from app.models.outbox_models import OutboxEvent
from app.models.inventory_models import (
    RealEstateProject, ProjectUnit, UnitInventoryStatus,
    ChannelPartner, ChannelPartnerCommission, ChannelPartnerTier
)
from app.modules.inventory.service import (
    ProjectService, UnitService, ChannelPartnerService
)


@pytest.fixture
async def e2e_session():
    """In-memory SQLite database session."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    async with session_factory() as session:
        broker_id = uuid.uuid4()
        org_id = broker_id
        broker = Broker(
            id=broker_id,
            email="revenue.director@wefylabs.com",
            name="Revenue Director",
            password_hash="pw_hash",
            phone="+919876549999",
        )
        session.add(broker)
        await session.commit()

    yield session_factory, org_id, broker_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_full_demand_to_supply_revenue_journey(e2e_session):
    session_factory, org_id, broker_id = e2e_session

    async with session_factory() as session:
        proj_svc = ProjectService(session)
        unit_svc = UnitService(session)
        cp_svc = ChannelPartnerService(session)

        # 1. Supply side: Project and Unit created
        proj = await proj_svc.create_project(org_id, broker_id, {
            "project_name": "DLF CyberCity Luxury Residences",
            "city": "Gurugram",
            "locality": "Sector 42",
        })
        unit = await unit_svc.create_unit(org_id, broker_id, {
            "project_id": proj.id,
            "unit_number": "T2-1502",
            "unit_type": "3 BHK",
            "floor_number": 15,
            "carpet_area": 2200,
            "base_price": 35000000,
            "total_price": 38000000,
        })
        await session.commit()
        assert unit.inventory_status == UnitInventoryStatus.AVAILABLE

        # 2. Channel Partner registered and accredited
        cp = await cp_svc.register_channel_partner(org_id, broker_id, {
            "firm_name": "Premier Wealth Advisors",
            "contact_name": "Karan Kapoor",
            "phone": "+919899001122",
            "tier": ChannelPartnerTier.PLATINUM,
            "default_commission_pct": 3.0,
        })
        await cp_svc.verify_kyc(org_id, cp.id)
        await cp_svc.create_project_agreement(org_id, cp.id, proj.id, {
            "valid_from": datetime.now(timezone.utc).date(),
            "commission_pct": 3.0,
        })
        await session.commit()

        # 3. Demand side: Customer Lead registered with Partner Attribution
        lead = Lead(
            broker_id=broker_id,
            name="Siddharth Mehra",
            phone="+919810998877",
            email="siddharth.mehra@enterprise.com",
            source="channel_partner",
            budget_max=40000000,
            property_type="3 BHK",
            notes=[{
                "channel_partner_id": str(cp.id),
                "channel_partner_code": cp.cp_code,
                "project_interest_id": str(proj.id),
                "attribution_type": "FIRST_TOUCH",
            }],
        )
        session.add(lead)
        await session.flush()

        # 4. Deal created in Deal OS
        deal = Deal(
            organization_id=org_id,
            broker_id=broker_id,
            lead_id=lead.id,
            deal_reference=f"DEAL-REV-{uuid.uuid4().hex[:6].upper()}",
            deal_title="Siddharth Mehra - T2-1502 Acquisition",
            current_stage=DealStage.RESERVATION,
            agreed_price=Decimal("38000000"),
            currency="INR",
            commission_percentage=Decimal("3.0"),
        )
        session.add(deal)
        await session.flush()

        # 5. Unit Reservation: AVAILABLE -> RESERVED
        unit = await unit_svc.transition_status(
            org_id=org_id,
            unit_id=unit.id,
            to_status=UnitInventoryStatus.RESERVED,
            deal_id=deal.id,
            channel_partner_id=cp.id,
            reason="Commercial token placed for deal",
        )
        await session.commit()

        # Verify unit status & outbox event
        assert unit.inventory_status == UnitInventoryStatus.RESERVED
        assert unit.reserved_by_deal_id == deal.id
        assert unit.channel_partner_id == cp.id

        outbox_res = (await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.event_type == "inventory.unit.reserved",
                OutboxEvent.aggregate_id == str(unit.id),
            )
        )).scalars().first()
        assert outbox_res is not None
        assert outbox_res.payload["to_status"] == "reserved"
        assert outbox_res.payload["deal_id"] == str(deal.id)

        # 6. Booking Confirmation: RESERVED -> BOOKED
        unit = await unit_svc.transition_status(
            org_id=org_id,
            unit_id=unit.id,
            to_status=UnitInventoryStatus.BOOKED,
            deal_id=deal.id,
            reason="10% booking token confirmed by broker",
        )
        await session.commit()

        assert unit.inventory_status == UnitInventoryStatus.BOOKED
        outbox_booked = (await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.event_type == "inventory.unit.booked",
                OutboxEvent.aggregate_id == str(unit.id),
            )
        )).scalars().first()
        assert outbox_booked is not None

        # 7. Closing & Handover: BOOKED -> SOLD
        unit = await unit_svc.transition_status(
            org_id=org_id,
            unit_id=unit.id,
            to_status=UnitInventoryStatus.SOLD,
            deal_id=deal.id,
            reason="Land registry title deed transferred",
        )
        await session.commit()

        assert unit.inventory_status == UnitInventoryStatus.SOLD
        assert unit.sold_at is not None

        outbox_sold = (await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.event_type == "inventory.unit.sold",
                OutboxEvent.aggregate_id == str(unit.id),
            )
        )).scalars().first()
        assert outbox_sold is not None

        # 8. Record Partner Commission
        comm = await cp_svc.record_commission(org_id, cp.id, {
            "deal_id": deal.id,
            "unit_id": unit.id,
            "project_id": proj.id,
            "transaction_value": 38000000,
            "commission_pct": 3.0,
            "commission_amount": 1140000,
            "net_payable": 1140000,
        })
        await session.commit()

        assert comm.id is not None
        assert comm.deal_id == deal.id
        assert comm.commission_amount == Decimal("1140000")
        assert comm.transaction_value == Decimal("38000000")
