"""
Part 28 — Real End-to-End Scenario Verification
==============================================
Tests the complete end-to-end Property CRM lifecycle:
Organization
→ Property created
→ Media attached
→ Agent assigned
→ Lead interest linked
→ Site visit scheduled
→ Visit completed & outcome recorded
→ Property status updated to SOLD
→ Audit log verified across all events
"""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.models import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing, PropertyMedia, PropertyPriceHistory, LeadPropertyInterest
from app.models.crm_models import Task, Meeting, Activity
from app.models.audit_log import AuditLog
from app.modules.properties.service import PropertyService

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session():
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_full_property_crm_lifecycle_real_e2e(db_session: AsyncSession):
    """
    Real E2E:
    Organization created
    → Property created with canonical attributes
    → Media attached
    → Agent assigned
    → Lead interest linked
    → Site visit scheduled (Meeting + Task + Activity)
    → Visit outcome recorded (Attended & Interested)
    → Property reserved then marked SOLD
    → Complete audit history verified
    """
    service = PropertyService(db_session)

    # 1. Organization / Broker Setup
    broker = Broker(
        id=uuid.uuid4(),
        email="director@bangaloreprime.com",
        name="Vikram Malhotra",
        agency_name="Bangalore Prime Properties",
        subscription_status="active",
        onboarding_status="ONBOARDED"
    )
    db_session.add(broker)

    # Agent in the same organization
    agent = Broker(
        id=uuid.uuid4(),
        email="agent.priya@bangaloreprime.com",
        name="Priya Sen",
        agency_name="Bangalore Prime Properties",
        subscription_status="active",
        onboarding_status="ONBOARDED"
    )
    db_session.add(agent)
    await db_session.commit()

    # 2. Property Created
    prop = await service.create_property(
        broker=broker,
        data={
            "title": "Sobha Windsor Luxury 3BHK",
            "property_type": "apartment",
            "property_category": "residential",
            "price": 18500000.0,
            "built_up_area_sqft": 1950.0,
            "bedrooms": 3,
            "bathrooms": 3,
            "locality": "Whitefield",
            "city": "Bengaluru",
            "project_name": "Sobha Windsor",
            "unit_number": "W-804",
            "owner_name": "Deepak Rao",
            "owner_phone": "+919888777666",
            "commission_amount": 370000.0,
            "commission_percentage": 2.0,
            "internal_notes": "All title documents verified by legal counsel."
        }
    )
    assert prop.id is not None
    assert prop.property_code.startswith("PROP-")
    assert prop.status == "available"

    # 3. Media Attached
    photo = PropertyMedia(
        property_id=prop.id,
        media_type="photo",
        url="https://storage.beetlelabs.com/properties/sobha-windsor-living.jpg",
        title="Living Room & Balcony View",
        is_primary=True,
        sort_order=1
    )
    floorplan = PropertyMedia(
        property_id=prop.id,
        media_type="floorplan",
        url="https://storage.beetlelabs.com/properties/sobha-windsor-3bhk-plan.pdf",
        title="Approved Floor Plan",
        is_primary=False,
        sort_order=2
    )
    db_session.add(photo)
    db_session.add(floorplan)
    await db_session.commit()

    # 4. Agent Assigned
    updated_prop = await service.update_property(
        property_id=prop.id,
        broker=broker,
        updates={"assigned_agent_id": str(agent.id)}
    )
    assert str(updated_prop.assigned_agent_id) == str(agent.id)

    # 5. Lead Created & Expresses Interest
    lead = Lead(
        id=uuid.uuid4(),
        broker_id=broker.id,
        name="Ananya Roy",
        phone="+919777888999",
        score="hot",
        budget_min=15000000,
        budget_max=20000000,
        property_type="apartment",
        preferred_locations=["Whitefield"],
        status="active"
    )
    db_session.add(lead)
    await db_session.commit()

    interest = await service.link_lead_property(
        lead_id=lead.id,
        property_id=prop.id,
        broker=broker,
        status="INTERESTED",
        interest_level="high",
        notes="Buyer looking for ready-to-move unit in Whitefield with clubhouse."
    )
    assert interest.status == "INTERESTED"

    # 6. Site Visit Scheduled
    visit_time = datetime.now(timezone.utc) + timedelta(days=1, hours=2)
    visit_res = await service.schedule_site_visit(
        lead_id=lead.id,
        property_id=prop.id,
        broker=broker,
        scheduled_at=visit_time,
        notes="Agent Priya will meet buyer at clubhouse reception."
    )
    assert visit_res["status"] == "success"
    meeting_id = visit_res["meeting_id"]

    # Verify Meeting & Task exist
    meeting = (await db_session.execute(select(Meeting).where(Meeting.id == meeting_id))).scalar_one()
    assert meeting.status == "scheduled"
    assert meeting.meeting_type == "site_visit"

    task = (await db_session.execute(select(Task).where(Task.lead_id == lead.id))).scalar_one()
    assert task.status == "pending"

    # 7. Visit Outcome Recorded (Attended & Shortlisted)
    outcome_res = await service.record_visit_outcome(
        meeting_id=meeting_id,
        broker=broker,
        outcome="attended",
        feedback="Client loved sunlight exposure and construction quality. Making token offer.",
        next_action="Draft formal purchase agreement"
    )
    assert outcome_res["status"] == "success"

    # 8. Property Reserved & Then Marked Sold
    reserved_prop = await service.reserve_property(
        property_id=prop.id,
        broker=broker,
        lead_id=lead.id
    )
    assert reserved_prop.status == "reserved"

    sold_prop = await service.update_property(
        property_id=prop.id,
        broker=broker,
        updates={"status": "sold"}
    )
    assert sold_prop.status == "sold"

    # 9. Audit Log Verification
    audit_stmt = select(AuditLog).where(
        AuditLog.resource_id == str(prop.id)
    ).order_by(AuditLog.created_at.asc())
    audit_logs = (await db_session.execute(audit_stmt)).scalars().all()

    actions = [a.action for a in audit_logs]
    assert "property.create" in actions
    assert "property.update" in actions
    assert "property.reserve" in actions

    # 10. Public share sanitization check
    public_view = await service.get_public_share(prop.share_token)
    assert public_view["title"] == "Sobha Windsor Luxury 3BHK"
    assert "owner_name" not in public_view
    assert "owner_phone" not in public_view
    assert "commission_amount" not in public_view
    assert "internal_notes" not in public_view
