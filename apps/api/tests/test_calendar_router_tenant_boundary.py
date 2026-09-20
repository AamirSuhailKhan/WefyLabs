"""Object-level authorization regression tests for Calendar routes."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient

from app.dependencies import TenantContext, get_current_broker, get_current_tenant, get_db
from app.main import app
from app.models.broker import Broker
from app.models.calendar_models import Meeting
from app.models.organization import Organization, OrganizationMember
from app.modules.calendar.router import get_booking_details_endpoint


def _broker(email: str) -> Broker:
    return Broker(id=uuid.uuid4(), email=email, name=email.split("@")[0])


def _meeting(organization_id: str) -> Meeting:
    start = datetime.now(timezone.utc) + timedelta(days=1)
    return Meeting(
        id=str(uuid.uuid4()),
        organization_id=organization_id,
        broker_id=uuid.uuid4(),
        title="Site visit",
        start_utc=start,
        end_utc=start + timedelta(hours=1),
        customer_timezone="Asia/Kolkata",
        broker_timezone="Asia/Kolkata",
    )


@pytest.mark.asyncio
async def test_booking_details_are_scoped_to_authenticated_tenant(db_session):
    broker_a = _broker("a@agency.test")
    broker_b = _broker("b@agency.test")
    org_a = Organization(id=uuid.uuid4(), name="Agency A", slug="agency-a")
    org_b = Organization(id=uuid.uuid4(), name="Agency B", slug="agency-b")
    own_meeting = _meeting(str(org_a.id))
    foreign_meeting = _meeting(str(org_b.id))
    db_session.add_all([
        broker_a,
        broker_b,
        org_a,
        org_b,
        OrganizationMember(organization_id=org_a.id, broker_id=broker_a.id, role="owner"),
        OrganizationMember(organization_id=org_b.id, broker_id=broker_b.id, role="owner"),
        own_meeting,
        foreign_meeting,
    ])
    await db_session.commit()
    tenant_a = TenantContext(organization_id=str(org_a.id))

    response = await get_booking_details_endpoint(own_meeting.id, db_session, broker_a, tenant_a)
    assert str(response.id) == own_meeting.id

    with pytest.raises(HTTPException) as exc_info:
        await get_booking_details_endpoint(foreign_meeting.id, db_session, broker_a, tenant_a)
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Meeting not found."


@pytest.mark.asyncio
async def test_requested_organization_must_be_one_of_the_brokers_memberships(db_session):
    broker = _broker("agent@agency.test")
    own_org = Organization(id=uuid.uuid4(), name="Own Agency", slug="own-agency")
    foreign_org = Organization(id=uuid.uuid4(), name="Foreign Agency", slug="foreign-agency")
    db_session.add_all([
        broker,
        own_org,
        foreign_org,
        OrganizationMember(organization_id=own_org.id, broker_id=broker.id, role="agent"),
    ])
    await db_session.commit()

    tenant = await get_current_tenant(
        current_broker=broker,
        db=db_session,
        requested_organization_id=str(own_org.id),
    )
    assert tenant.organization_id == str(own_org.id)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_tenant(
            current_broker=broker,
            db=db_session,
            requested_organization_id=str(foreign_org.id),
        )
    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "ORGANIZATION_ACCESS_DENIED"


@pytest.mark.asyncio
async def test_calendar_api_uses_membership_tenant_not_legacy_broker_alias(db_session):
    broker = _broker("owner@agency.test")
    org = Organization(id=uuid.uuid4(), name="Actual Agency", slug="actual-agency")
    meeting = _meeting(str(org.id))
    db_session.add_all([
        broker,
        org,
        OrganizationMember(organization_id=org.id, broker_id=broker.id, role="owner"),
        meeting,
    ])
    await db_session.commit()

    async def override_get_db():
        yield db_session

    async def override_current_broker():
        return broker

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_broker] = override_current_broker
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(f"/api/v1/calendar/bookings/{meeting.id}")
        assert response.status_code == 200
        assert response.json()["id"] == meeting.id
    finally:
        app.dependency_overrides.clear()
