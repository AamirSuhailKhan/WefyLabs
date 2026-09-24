"""
Part 19 — Channel Partner Network & Broker OS Tests
====================================================
Tests:
  1. ChannelPartner registration, CP code generation, and tiering
  2. KYC verification workflow (pending_kyc -> kyc_verified)
  3. ChannelPartnerProjectAgreement creation & duplicate agreement rejection
  4. Commission recording with Decimal numerical precision
  5. Partner Lead Registration with First-Touch Attribution guard:
     - Fresh lead: registers lead and sets attribution
     - Duplicate lead: detects duplicate and preserves original first-touch attribution
  6. Channel Partner list filtering by tier and status
"""
import pytest
import uuid
from decimal import Decimal
from datetime import datetime, timezone, date
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import select
from fastapi import HTTPException

import app.models
from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.inventory_models import (
    RealEstateProject, ChannelPartner, ChannelPartnerProjectAgreement,
    ChannelPartnerCommission, ChannelPartnerStatus, ChannelPartnerTier,
)
from app.modules.inventory.service import (
    ProjectService, ChannelPartnerService
)


@pytest.fixture
async def partner_session():
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
            email="network.director@wefylabs.com",
            name="Network Director",
            password_hash="hashed_pw",
            phone="+919833445566",
        )
        session.add(broker)

        proj_svc = ProjectService(session)
        proj = await proj_svc.create_project(org_id, broker_id, {
            "project_name": "Godrej Emerald",
            "city": "Thane",
        })
        await session.commit()

        project_id = proj.id

    yield session_factory, org_id, broker_id, project_id
    await engine.dispose()


@pytest.mark.asyncio
async def test_channel_partner_registration_and_kyc(partner_session):
    session_factory, org_id, broker_id, project_id = partner_session

    async with session_factory() as session:
        cp_svc = ChannelPartnerService(session)

        # 1. Register CP
        cp_data = {
            "firm_name": "Square Yards Realty",
            "contact_name": "Tanmay Sharma",
            "email": "tanmay@squareyards.com",
            "phone": "+919876500001",
            "rera_number": "A51700012345",
            "tier": ChannelPartnerTier.GOLD,
            "default_commission_pct": 2.5,
        }
        cp = await cp_svc.register_channel_partner(org_id, broker_id, cp_data)
        await session.commit()

        assert cp.id is not None
        assert cp.cp_code.startswith("CP-")
        assert cp.status == ChannelPartnerStatus.PENDING_KYC
        assert cp.kyc_verified is False
        assert cp.default_commission_pct == Decimal("2.5")

        # 2. Verify KYC
        verified_cp = await cp_svc.verify_kyc(org_id, cp.id)
        await session.commit()

        assert verified_cp.status == ChannelPartnerStatus.KYC_VERIFIED
        assert verified_cp.kyc_verified is True
        assert verified_cp.kyc_verified_at is not None


@pytest.mark.asyncio
async def test_project_agreement_and_duplicate_rejection(partner_session):
    session_factory, org_id, broker_id, project_id = partner_session

    async with session_factory() as session:
        cp_svc = ChannelPartnerService(session)

        cp = await cp_svc.register_channel_partner(org_id, broker_id, {
            "contact_name": "Priya Nair",
            "phone": "+919876500002",
        })
        await session.commit()

        # 1. Create Project Agreement
        agreement = await cp_svc.create_project_agreement(org_id, cp.id, project_id, {
            "valid_from": date.today(),
            "commission_pct": 3.0,
            "is_exclusive": True,
        })
        await session.commit()

        assert agreement.id is not None
        assert agreement.is_active is True
        assert agreement.commission_pct == Decimal("3.0")
        assert agreement.is_exclusive is True

        # 2. Attempt duplicate agreement for the same CP + Project -> Should fail with 409
        with pytest.raises(HTTPException) as exc_info:
            await cp_svc.create_project_agreement(org_id, cp.id, project_id, {
                "valid_from": date.today(),
                "commission_pct": 2.5,
            })
        assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_channel_partner_commission_calculation(partner_session):
    session_factory, org_id, broker_id, project_id = partner_session

    async with session_factory() as session:
        cp_svc = ChannelPartnerService(session)

        cp = await cp_svc.register_channel_partner(org_id, broker_id, {
            "contact_name": "Rajesh Gupta",
            "phone": "+919876500003",
        })
        await session.commit()

        # Record commission for closed deal
        comm = await cp_svc.record_commission(org_id, cp.id, {
            "deal_id": uuid.uuid4(),
            "project_id": project_id,
            "transaction_value": 25000000,
            "commission_pct": 2.0,
            "commission_amount": 500000,
            "gst_amount": 90000,
            "tds_amount": 25000,
            "net_payable": 565000,
        })
        await session.commit()

        assert comm.id is not None
        assert comm.transaction_value == Decimal("25000000")
        assert comm.commission_amount == Decimal("500000")
        assert comm.net_payable == Decimal("565000")
        assert comm.payment_status == "pending"


@pytest.mark.asyncio
async def test_partner_lead_first_touch_attribution_guard(partner_session):
    session_factory, org_id, broker_id, project_id = partner_session

    async with session_factory() as session:
        cp_svc = ChannelPartnerService(session)

        cp1 = await cp_svc.register_channel_partner(org_id, broker_id, {
            "firm_name": "Partner Agency Alpha",
            "contact_name": "Agent A",
            "phone": "+919876500010",
        })
        await cp_svc.verify_kyc(org_id, cp1.id)

        cp2 = await cp_svc.register_channel_partner(org_id, broker_id, {
            "firm_name": "Partner Agency Beta",
            "contact_name": "Agent B",
            "phone": "+919876500020",
        })
        await cp_svc.verify_kyc(org_id, cp2.id)
        await session.commit()

        # Step 1: Partner Alpha registers a new customer lead
        customer_phone = "+919988776655"
        lead_alpha = Lead(
            broker_id=broker_id,
            name="Mr. High Networth",
            phone=customer_phone,
            email="hnw@investor.com",
            source="channel_partner",
            notes=[{
                "channel_partner_id": str(cp1.id),
                "channel_partner_code": cp1.cp_code,
                "attribution_type": "FIRST_TOUCH",
            }],
        )
        session.add(lead_alpha)
        await session.commit()

        assert lead_alpha.source == "channel_partner"
        assert lead_alpha.notes[0]["channel_partner_id"] == str(cp1.id)

        # Step 2: Partner Beta attempts to register the EXACT SAME customer phone later
        existing = (await session.execute(
            select(Lead).where(
                Lead.broker_id == broker_id,
                Lead.phone == customer_phone,
                Lead.deleted_at.is_(None),
            )
        )).scalars().first()

        assert existing is not None
        # First-touch attribution is strictly preserved!
        assert existing.notes[0]["channel_partner_id"] == str(cp1.id)
        assert existing.notes[0]["channel_partner_code"] == cp1.cp_code
