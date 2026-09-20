"""Regression tests for the lightweight FastAPI RBAC dependency."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.infrastructure.errors.exceptions import ForbiddenException
from app.infrastructure.security.rbac import Permission, Role, get_current_role, require_permission
from app.models.broker import Broker
from app.dependencies import TenantContext


def _broker() -> Broker:
    return Broker(id=uuid.uuid4(), email="rbac@example.com", name="RBAC Broker")


@pytest.mark.asyncio
async def test_role_is_resolved_from_membership_not_a_default():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = "manager"
    db.execute.return_value = result

    assert await get_current_role(
        current_broker=_broker(),
        db=db,
        tenant=TenantContext(organization_id=str(uuid.uuid4())),
    ) is Role.MANAGER


@pytest.mark.asyncio
async def test_missing_membership_is_denied():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = None
    db.execute.return_value = result

    with pytest.raises(ForbiddenException) as exc_info:
        await get_current_role(
            current_broker=_broker(),
            db=db,
            tenant=TenantContext(organization_id=str(uuid.uuid4())),
        )
    assert exc_info.value.code == "ORGANIZATION_MEMBERSHIP_REQUIRED"


@pytest.mark.asyncio
async def test_unknown_membership_role_is_denied():
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.first.return_value = "super_admin"
    db.execute.return_value = result

    with pytest.raises(ForbiddenException) as exc_info:
        await get_current_role(
            current_broker=_broker(),
            db=db,
            tenant=TenantContext(organization_id=str(uuid.uuid4())),
        )
    assert exc_info.value.code == "INVALID_ORGANIZATION_ROLE"


@pytest.mark.asyncio
async def test_agent_cannot_pass_an_organization_management_guard():
    guard = require_permission(Permission.ORG_MANAGE)
    with pytest.raises(ForbiddenException):
        await guard(current_role=Role.AGENT)


@pytest.mark.asyncio
async def test_role_is_bound_to_the_selected_tenant(db_session):
    """A high-privilege role in one tenant cannot bleed into another tenant."""
    from app.models.organization import Organization, OrganizationMember

    broker = _broker()
    owner_org = Organization(id=uuid.uuid4(), name="Owner Org", slug="owner-org")
    agent_org = Organization(id=uuid.uuid4(), name="Agent Org", slug="agent-org")
    db_session.add_all([
        broker,
        owner_org,
        agent_org,
        OrganizationMember(organization_id=owner_org.id, broker_id=broker.id, role="owner"),
        OrganizationMember(organization_id=agent_org.id, broker_id=broker.id, role="agent"),
    ])
    await db_session.commit()

    agent_role = await get_current_role(
        current_broker=broker,
        db=db_session,
        tenant=TenantContext(organization_id=str(agent_org.id)),
    )
    owner_role = await get_current_role(
        current_broker=broker,
        db=db_session,
        tenant=TenantContext(organization_id=str(owner_org.id)),
    )

    assert agent_role is Role.AGENT
    assert owner_role is Role.OWNER
