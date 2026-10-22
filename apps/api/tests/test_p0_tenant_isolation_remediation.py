"""
P0 Tenant Isolation Security Remediation Tests
===============================================
Comprehensive verification test suite proving:
1. All lead endpoints reject unauthenticated requests with 401.
2. Cross-organization IDOR attempts return 404 (no existence leak) or 403.
3. Standalone brokers with 0 memberships cannot spoof X-WefyLabs-Organization-Id (403 Forbidden).
4. get_or_create_default_broker() is completely eliminated and cannot be invoked.
5. Multi-organization members must explicitly scope via header (409 on ambiguity, 403 on non-membership).
6. Legitimate single-tenant and multi-tenant workflows function with complete data boundary integrity.
"""
import uuid
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.dependencies import get_db, clear_rate_limits
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.organization import Organization, OrganizationMember
from app.modules.auth.service import create_access_token


@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    clear_rate_limits()
    from app.dependencies import current_tenant_ctx
    token = current_tenant_ctx.set(None)
    yield
    current_tenant_ctx.reset(token)
    clear_rate_limits()


@pytest.mark.asyncio
async def test_unauthenticated_requests_rejected(db_session: AsyncSession):
    """Scenario 1: Unauthenticated requests to any lead endpoint are strictly rejected with 401."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    fake_id = uuid.uuid4()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_list = await ac.get("/api/v1/leads")
        assert res_list.status_code == 401

        res_create = await ac.post("/api/v1/leads", json={"phone": "+919999999999", "name": "Hacker"})
        assert res_create.status_code == 401

        res_detail = await ac.get(f"/api/v1/leads/{fake_id}")
        assert res_detail.status_code == 401

        res_patch = await ac.patch(f"/api/v1/leads/{fake_id}/status", json={"status": "qualified"})
        assert res_patch.status_code == 401

        res_delete = await ac.delete(f"/api/v1/leads/{fake_id}")
        assert res_delete.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cross_organization_lead_isolation(db_session: AsyncSession):
    """Scenario 2 & 4: Broker from Org A cannot read, update, or delete leads belonging to Org B."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Create Organization A and Broker A
    org_a = Organization(id=uuid.uuid4(), name="Org Alpha", slug=f"org-alpha-{uuid.uuid4().hex[:6]}")
    broker_a = Broker(
        id=uuid.uuid4(),
        email="broker_a@alpha.com",
        name="Broker Alpha",
        phone="+919100000001",
        whatsapp_number="+919100000001"
    )
    db_session.add_all([org_a, broker_a])
    await db_session.flush()

    mem_a = OrganizationMember(organization_id=org_a.id, broker_id=broker_a.id, role="owner")
    db_session.add(mem_a)

    # Create Organization B and Broker B
    org_b = Organization(id=uuid.uuid4(), name="Org Beta", slug=f"org-beta-{uuid.uuid4().hex[:6]}")
    broker_b = Broker(
        id=uuid.uuid4(),
        email="broker_b@beta.com",
        name="Broker Beta",
        phone="+919200000002",
        whatsapp_number="+919200000002"
    )
    db_session.add_all([org_b, broker_b])
    await db_session.flush()

    mem_b = OrganizationMember(organization_id=org_b.id, broker_id=broker_b.id, role="owner")
    db_session.add(mem_b)

    # Lead belonging to Org A
    lead_a = Lead(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        broker_id=broker_a.id,
        phone="+919111111111",
        name="Confidential Client Alpha",
        source="manual",
        status="pending"
    )
    db_session.add(lead_a)
    await db_session.commit()

    token_b = create_access_token({"sub": broker_b.email, "email": broker_b.email})
    headers_b = {"Authorization": f"Bearer {token_b}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Broker B calls list leads — must NOT see Lead A
        res_list = await ac.get("/api/v1/leads", headers=headers_b)
        assert res_list.status_code == 200
        items = res_list.json()["data"]
        assert len(items) == 0

        # Broker B attempts to read Lead A directly via IDOR -> 404 Not Found
        res_get = await ac.get(f"/api/v1/leads/{lead_a.id}", headers=headers_b)
        assert res_get.status_code == 404

        # Broker B attempts to mutate Lead A status -> 404 Not Found
        res_patch = await ac.patch(
            f"/api/v1/leads/{lead_a.id}/status",
            json={"status": "lost"},
            headers=headers_b
        )
        assert res_patch.status_code == 404

        # Broker B attempts to delete Lead A -> 404 Not Found
        res_del = await ac.delete(f"/api/v1/leads/{lead_a.id}", headers=headers_b)
        assert res_del.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_standalone_broker_cannot_spoof_organization_header(db_session: AsyncSession):
    """Scenario 3: A broker with 0 organization memberships cannot access an org by spoofing the header."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Organization Victim
    org_victim = Organization(id=uuid.uuid4(), name="Victim Org", slug=f"victim-{uuid.uuid4().hex[:6]}")
    broker_owner = Broker(
        id=uuid.uuid4(),
        email="owner@victim.com",
        name="Victim Owner",
        phone="+919300000003",
        whatsapp_number="+919300000003"
    )
    db_session.add_all([org_victim, broker_owner])
    await db_session.flush()

    mem_victim = OrganizationMember(organization_id=org_victim.id, broker_id=broker_owner.id, role="owner")
    db_session.add(mem_victim)

    lead_victim = Lead(
        id=uuid.uuid4(),
        organization_id=org_victim.id,
        broker_id=broker_owner.id,
        phone="+919400000004",
        name="Victim Lead",
        source="manual",
        status="pending"
    )
    db_session.add(lead_victim)

    # Standalone Broker (has NO OrganizationMember rows)
    broker_rogue = Broker(
        id=uuid.uuid4(),
        email="rogue@standalone.com",
        name="Rogue Broker",
        phone="+919500000005",
        whatsapp_number="+919500000005"
    )
    db_session.add(broker_rogue)
    await db_session.commit()

    token_rogue = create_access_token({"sub": broker_rogue.email, "email": broker_rogue.email})
    headers_rogue_spoofed = {
        "Authorization": f"Bearer {token_rogue}",
        "X-WefyLabs-Organization-Id": str(org_victim.id)
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Rogue broker attempting to query victim org via header -> REJECTED with 403 Forbidden
        res = await ac.get("/api/v1/leads", headers=headers_rogue_spoofed)
        assert res.status_code == 403
        data = res.json()
        assert "ORGANIZATION_ACCESS_DENIED" in str(data)

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_multi_organization_switching_and_scoping(db_session: AsyncSession):
    """Scenario 5: Multi-org broker must supply valid header; data strictly isolated per org."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Multi-org Broker
    broker_multi = Broker(
        id=uuid.uuid4(),
        email="multi@broker.com",
        name="Multi Broker",
        phone="+919600000006",
        whatsapp_number="+919600000006"
    )
    org_1 = Organization(id=uuid.uuid4(), name="Agency One", slug=f"agency-one-{uuid.uuid4().hex[:6]}")
    org_2 = Organization(id=uuid.uuid4(), name="Agency Two", slug=f"agency-two-{uuid.uuid4().hex[:6]}")
    org_3 = Organization(id=uuid.uuid4(), name="Agency Three", slug=f"agency-three-{uuid.uuid4().hex[:6]}")
    db_session.add_all([broker_multi, org_1, org_2, org_3])
    await db_session.flush()

    # Member of Org 1 and Org 2, NOT Org 3
    mem1 = OrganizationMember(organization_id=org_1.id, broker_id=broker_multi.id, role="agent")
    mem2 = OrganizationMember(organization_id=org_2.id, broker_id=broker_multi.id, role="agent")
    db_session.add_all([mem1, mem2])

    lead_org1 = Lead(
        id=uuid.uuid4(),
        organization_id=org_1.id,
        broker_id=broker_multi.id,
        phone="+919700000007",
        name="Lead in Org 1",
        source="manual",
        status="pending"
    )
    lead_org2 = Lead(
        id=uuid.uuid4(),
        organization_id=org_2.id,
        broker_id=broker_multi.id,
        phone="+919800000008",
        name="Lead in Org 2",
        source="manual",
        status="pending"
    )
    db_session.add_all([lead_org1, lead_org2])
    await db_session.commit()

    token_multi = create_access_token({"sub": broker_multi.email, "email": broker_multi.email})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. No header with multiple orgs -> 409 Conflict (Context Required)
        res_no_header = await ac.get(
            "/api/v1/leads",
            headers={"Authorization": f"Bearer {token_multi}"}
        )
        assert res_no_header.status_code == 409

        # 2. Scope to Org 1 -> Only Lead in Org 1 returned
        res_org1 = await ac.get(
            "/api/v1/leads",
            headers={
                "Authorization": f"Bearer {token_multi}",
                "X-WefyLabs-Organization-Id": str(org_1.id)
            }
        )
        assert res_org1.status_code == 200
        data1 = res_org1.json()["data"]
        assert len(data1) == 1
        assert data1[0]["name"] == "Lead in Org 1"

        # 3. Scope to Org 2 -> Only Lead in Org 2 returned
        res_org2 = await ac.get(
            "/api/v1/leads",
            headers={
                "Authorization": f"Bearer {token_multi}",
                "X-WefyLabs-Organization-Id": str(org_2.id)
            }
        )
        assert res_org2.status_code == 200
        data2 = res_org2.json()["data"]
        assert len(data2) == 1
        assert data2[0]["name"] == "Lead in Org 2"

        # 4. Scope to un-enrolled Org 3 -> 403 Forbidden
        res_org3 = await ac.get(
            "/api/v1/leads",
            headers={
                "Authorization": f"Bearer {token_multi}",
                "X-WefyLabs-Organization-Id": str(org_3.id)
            }
        )
        assert res_org3.status_code == 403

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_or_create_default_broker_does_not_exist():
    """Scenario 6: Verify get_or_create_default_broker is eliminated from legacy module."""
    import app.routers.leads as legacy_leads
    assert not hasattr(legacy_leads, "get_or_create_default_broker")


@pytest.mark.asyncio
async def test_cross_organization_property_isolation(db_session: AsyncSession):
    """Scenario 7: Broker in Org B cannot read, update, or delete property in Org A."""
    from app.models.property_models import PropertyListing

    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    org_a = Organization(id=uuid.uuid4(), name="Prop Org A", slug=f"prop-org-a-{uuid.uuid4().hex[:6]}")
    broker_a = Broker(
        id=uuid.uuid4(),
        email="prop_a@agency.com",
        name="Prop Broker A",
        phone="+919800000010",
        whatsapp_number="+919800000010"
    )
    org_b = Organization(id=uuid.uuid4(), name="Prop Org B", slug=f"prop-org-b-{uuid.uuid4().hex[:6]}")
    broker_b = Broker(
        id=uuid.uuid4(),
        email="prop_b@agency.com",
        name="Prop Broker B",
        phone="+919800000020",
        whatsapp_number="+919800000020"
    )
    db_session.add_all([org_a, broker_a, org_b, broker_b])
    await db_session.flush()

    mem_a = OrganizationMember(organization_id=org_a.id, broker_id=broker_a.id, role="owner")
    mem_b = OrganizationMember(organization_id=org_b.id, broker_id=broker_b.id, role="owner")
    db_session.add_all([mem_a, mem_b])

    # Property belonging to Org A
    prop_a = PropertyListing(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        broker_id=broker_a.id,
        title="Luxury Penthouse Alpha",
        description="Exclusive penthouse in Indiranagar",
        property_category="residential",
        property_type="apartment",
        transaction_category="resale",
        price=15000000.0,
        area_value=3200.0,
        bedrooms=4,
        bathrooms=4,
        status="available"
    )
    db_session.add(prop_a)
    await db_session.commit()

    token_b = create_access_token({"sub": broker_b.email, "email": broker_b.email})
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-WefyLabs-Organization-Id": str(org_b.id)
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Broker B cannot get Property A -> 404
        res_get = await ac.get(f"/api/v1/properties/{prop_a.id}", headers=headers_b)
        assert res_get.status_code == 404

        # 2. Broker B cannot update Property A -> 404
        res_put = await ac.put(
            f"/api/v1/properties/{prop_a.id}",
            json={"title": "Hacked Penthouse"},
            headers=headers_b
        )
        assert res_put.status_code == 404

        # 3. Broker B cannot delete Property A -> 404
        res_del = await ac.delete(f"/api/v1/properties/{prop_a.id}", headers=headers_b)
        assert res_del.status_code == 404

        # 4. Property A not in Broker B inventory list
        res_list = await ac.get("/api/v1/properties", headers=headers_b)
        assert res_list.status_code == 200
        prop_ids = [p["id"] for p in res_list.json().get("items", [])]
        assert str(prop_a.id) not in prop_ids

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cross_tenant_conversation_and_followup_isolation(db_session: AsyncSession):
    """Scenario 8: Cross-tenant access to conversations and follow-ups returns 404."""
    from app.models.conversation import Conversation
    from app.models.follow_up import FollowUp
    from datetime import datetime, timezone

    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    broker_x = Broker(
        id=uuid.uuid4(),
        email="broker_x@org.com",
        name="Broker X",
        phone="+919800000030",
        whatsapp_number="+919800000030"
    )
    broker_y = Broker(
        id=uuid.uuid4(),
        email="broker_y@org.com",
        name="Broker Y",
        phone="+919800000040",
        whatsapp_number="+919800000040"
    )
    db_session.add_all([broker_x, broker_y])
    await db_session.flush()

    lead_x = Lead(
        id=uuid.uuid4(),
        broker_id=broker_x.id,
        phone="+919800000050",
        name="Secret Lead X",
        source="manual",
        status="pending"
    )
    db_session.add(lead_x)
    await db_session.flush()

    conv_x = Conversation(
        lead_id=lead_x.id,
        direction="inbound",
        sender_type="lead",
        message="Sensitive client budget is 5 Crores"
    )
    followup_x = FollowUp(
        lead_id=lead_x.id,
        sequence_number=1,
        scheduled_at=datetime.now(timezone.utc),
        status="scheduled",
        message="Follow up on 5 Crore budget"
    )
    db_session.add_all([conv_x, followup_x])
    await db_session.commit()

    token_y = create_access_token({"sub": broker_y.email, "email": broker_y.email})
    headers_y = {"Authorization": f"Bearer {token_y}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Broker Y attempts to read Broker X's conversations -> 404 Not Found
        res_conv = await ac.get(f"/api/v1/conversations/{lead_x.id}", headers=headers_y)
        assert res_conv.status_code == 404

        # Broker Y attempts to read Broker X's follow-ups -> 404 Not Found
        res_follow = await ac.get(f"/api/v1/leads/{lead_x.id}/follow-ups", headers=headers_y)
        assert res_follow.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_cross_tenant_scoring_and_crm_services_isolation(db_session: AsyncSession):
    """Scenario 9: Cross-tenant isolation and IDOR protection in scoring and CRM services."""
    from datetime import datetime, timezone
    from sqlalchemy import select

    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    # Create Org A and Broker A
    org_a = Organization(id=uuid.uuid4(), name="Agency Alpha", slug=f"alpha-{uuid.uuid4().hex[:6]}")
    broker_a = Broker(
        id=uuid.uuid4(),
        email="agent_a@alpha.com",
        name="Agent Alpha",
        phone="+919811111111",
        whatsapp_number="+919811111111"
    )
    # Create Org B and Broker B
    org_b = Organization(id=uuid.uuid4(), name="Agency Beta", slug=f"beta-{uuid.uuid4().hex[:6]}")
    broker_b = Broker(
        id=uuid.uuid4(),
        email="agent_b@beta.com",
        name="Agent Beta",
        phone="+919822222222",
        whatsapp_number="+919822222222"
    )
    db_session.add_all([org_a, broker_a, org_b, broker_b])
    await db_session.flush()

    mem_a = OrganizationMember(organization_id=org_a.id, broker_id=broker_a.id, role="admin")
    mem_b = OrganizationMember(organization_id=org_b.id, broker_id=broker_b.id, role="admin")
    db_session.add_all([mem_a, mem_b])

    # Lead belonging to Org A
    lead_a = Lead(
        id=uuid.uuid4(),
        organization_id=org_a.id,
        broker_id=broker_a.id,
        phone="+919833333333",
        name="Alpha High Value Lead",
        source="manual",
        status="pending"
    )
    db_session.add(lead_a)
    await db_session.commit()

    token_b = create_access_token({"sub": broker_b.email, "email": broker_b.email})
    headers_b = {
        "Authorization": f"Bearer {token_b}",
        "X-WefyLabs-Organization-Id": str(org_b.id)
    }

    token_a = create_access_token({"sub": broker_a.email, "email": broker_a.email})
    headers_a = {
        "Authorization": f"Bearer {token_a}",
        "X-WefyLabs-Organization-Id": str(org_a.id)
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Broker B attempts to qualify Broker A's lead -> 404 Not Found
        res_score = await ac.post(
            "/api/v1/scoring/qualify",
            json={"lead_id": str(lead_a.id), "force": True},
            headers=headers_b
        )
        assert res_score.status_code == 404
        assert "not found" in res_score.json().get("detail", "").lower()

        # 2. Broker B attempts to attach a Task to Broker A's lead -> 404 Not Found
        res_task = await ac.post(
            "/api/v1/crm/services/tasks",
            json={"lead_id": str(lead_a.id), "title": "Injected Task", "priority": "high"},
            headers=headers_b
        )
        assert res_task.status_code == 404
        assert "not found" in res_task.json().get("detail", "").lower()

        # 3. Broker B attempts to book a Meeting on Broker A's lead -> 404 Not Found
        res_meet = await ac.post(
            "/api/v1/crm/services/meetings",
            json={
                "lead_id": str(lead_a.id),
                "title": "Injected Site Visit",
                "meeting_type": "site_visit",
                "scheduled_at": "2026-11-01T10:00:00Z",
                "duration_minutes": 60
            },
            headers=headers_b
        )
        assert res_meet.status_code == 404
        assert "not found" in res_meet.json().get("detail", "").lower()

        # 4. Broker A creates a lead via /crm/services/leads -> organization_id stamped correctly
        res_create_lead = await ac.post(
            "/api/v1/crm/services/leads",
            json={"phone": "+919844444444", "name": "Created Lead Alpha", "source": "manual"},
            headers=headers_a
        )
        assert res_create_lead.status_code == 201
        new_lead_id = res_create_lead.json()["id"]

        # Verify persisted lead has organization_id stamped
        db_lead = (await db_session.execute(select(Lead).where(Lead.id == uuid.UUID(str(new_lead_id))))).scalars().first()
        assert db_lead is not None
        assert db_lead.organization_id == org_a.id

    app.dependency_overrides.clear()


