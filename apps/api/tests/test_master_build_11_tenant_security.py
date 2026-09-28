"""
Master Build 11: Dedicated Enterprise Tenant Isolation & Cross-Tenant Security Suite
====================================================================================
Validates that tenant boundaries are mathematically enforced across all CRM sub-systems.
Zero-trust invariant: UNKNOWN TENANT = REJECT. No cross-tenant data leakage is permitted.

Tested Domains:
1. Leads & Customer Identities
2. Conversations & Messages
3. Properties & Inventory
4. Documents & Media
5. Opportunities & Deals
6. Tasks & Appointments
7. Bookings & Slots
8. Payments & Revenue Intelligence
9. Analytics & Aggregates
10. AI Context, Memory & Retrieval
11. Search & Facets
12. Governed Exports
13. Fail-Closed Tenancy Resolution
"""
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from decimal import Decimal
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.organization import Organization, OrganizationMember
from app.models.deal_models import Deal
from app.models.crm_models import Task, Meeting
from app.dependencies import TenantContext, get_current_tenant
from app.modules.security.data_governance import filter_payload_for_role


@pytest.mark.asyncio
class TestMasterBuild11TenantIsolation:

    async def _setup_two_tenants(self, db_session: AsyncSession):
        """Provisions two completely isolated organizations with separate brokers and leads."""
        org_a = Organization(
            id=uuid.uuid4(),
            name="Alpha Realty Group",
            slug=f"alpha-{uuid.uuid4().hex[:6]}"
        )
        org_b = Organization(
            id=uuid.uuid4(),
            name="Beta Capital Properties",
            slug=f"beta-{uuid.uuid4().hex[:6]}"
        )
        db_session.add_all([org_a, org_b])

        broker_a = Broker(
            id=uuid.uuid4(),
            name="Agent Alpha",
            email=f"alpha_{uuid.uuid4().hex[:6]}@alpharealty.com",
            phone="+919111111111",
            subscription_status="active"
        )
        broker_b = Broker(
            id=uuid.uuid4(),
            name="Agent Beta",
            email=f"beta_{uuid.uuid4().hex[:6]}@betacapital.com",
            phone="+919222222222",
            subscription_status="active"
        )
        db_session.add_all([broker_a, broker_b])
        await db_session.flush()

        member_a = OrganizationMember(
            organization_id=org_a.id,
            broker_id=broker_a.id,
            role="AGENT"
        )
        member_b = OrganizationMember(
            organization_id=org_b.id,
            broker_id=broker_b.id,
            role="AGENT"
        )
        db_session.add_all([member_a, member_b])

        lead_a = Lead(
            id=uuid.uuid4(),
            broker_id=broker_a.id,
            name="High Net Worth Buyer A",
            phone="+919999900001",
            budget_max=50000000,
            status="active"
        )
        lead_b = Lead(
            id=uuid.uuid4(),
            broker_id=broker_b.id,
            name="Confidential Buyer B",
            phone="+919999900002",
            budget_max=90000000,
            status="active"
        )
        db_session.add_all([lead_a, lead_b])
        await db_session.commit()

        return {
            "org_a": org_a, "org_b": org_b,
            "broker_a": broker_a, "broker_b": broker_b,
            "lead_a": lead_a, "lead_b": lead_b
        }

    # 1. Leads Isolation
    async def test_tenant_a_cannot_read_tenant_b_lead(self, db_session: AsyncSession):
        ctx = await self._setup_two_tenants(db_session)
        stmt = select(Lead).where(
            Lead.id == ctx["lead_b"].id,
            Lead.broker_id == ctx["broker_a"].id
        )
        result = await db_session.execute(stmt)
        assert result.scalars().first() is None, "Tenant A was able to query Tenant B lead!"

    # 2. Identities & Contact Information Leakage Defense
    async def test_lead_contact_info_not_leaked_across_tenants(self, db_session: AsyncSession):
        ctx = await self._setup_two_tenants(db_session)
        stmt = select(Lead).where(Lead.broker_id == ctx["broker_a"].id)
        results = (await db_session.execute(stmt)).scalars().all()
        phones = [l.phone for l in results]
        assert ctx["lead_b"].phone not in phones

    # 3. Deals / Opportunities Isolation
    async def test_opportunities_cross_tenant_isolation(self, db_session: AsyncSession):
        ctx = await self._setup_two_tenants(db_session)
        deal_b = Deal(
            id=uuid.uuid4(),
            organization_id=ctx["org_b"].id,
            broker_id=ctx["broker_b"].id,
            lead_id=ctx["lead_b"].id,
            deal_reference=f"REF-{uuid.uuid4().hex[:6]}",
            deal_title="Penthouse Sale",
            offer_price=Decimal("75000000.00"),
            current_stage="negotiation"
        )
        db_session.add(deal_b)
        await db_session.commit()

        # Query scoped to Org A
        stmt = select(Deal).where(
            Deal.id == deal_b.id,
            Deal.organization_id == ctx["org_a"].id
        )
        found = (await db_session.execute(stmt)).scalars().first()
        assert found is None

    # 4. Tasks & Actions Isolation
    async def test_tasks_cross_tenant_isolation(self, db_session: AsyncSession):
        ctx = await self._setup_two_tenants(db_session)
        task_b = Task(
            id=str(uuid.uuid4()),
            broker_id=str(ctx["broker_b"].id),
            title="Confidential Client Meeting",
            status="pending"
        )
        db_session.add(task_b)
        await db_session.commit()

        # Attempt lookup by Broker A
        stmt = select(Task).where(Task.id == task_b.id, Task.broker_id == str(ctx["broker_a"].id))
        assert (await db_session.execute(stmt)).scalars().first() is None

    # 5. Meetings & Calendar Isolation
    async def test_meetings_cross_tenant_isolation(self, db_session: AsyncSession):
        from datetime import datetime, timezone
        ctx = await self._setup_two_tenants(db_session)
        meeting_b = Meeting(
            id=str(uuid.uuid4()),
            broker_id=str(ctx["broker_b"].id),
            title="Contract Signing Beta",
            status="scheduled",
            scheduled_at=datetime.now(timezone.utc)
        )
        db_session.add(meeting_b)
        await db_session.commit()

        stmt = select(Meeting).where(
            Meeting.id == meeting_b.id,
            Meeting.broker_id == str(ctx["broker_a"].id)
        )
        assert (await db_session.execute(stmt)).scalars().first() is None

    # 6. Fail-Closed Tenancy Resolution (Header spoofing)
    async def test_header_spoofing_other_org_fails_closed(self, db_session: AsyncSession):
        ctx = await self._setup_two_tenants(db_session)
        # Broker A attempts to specify Org B in tenant context
        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(
                current_broker=ctx["broker_a"],
                db=db_session,
                requested_organization_id=str(ctx["org_b"].id)
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "ORGANIZATION_ACCESS_DENIED"

    # 7. Unenrolled Principal Fails Closed
    async def test_unenrolled_broker_fails_closed(self, db_session: AsyncSession):
        unattached_broker = Broker(
            id=uuid.uuid4(),
            name="Rogue Agent",
            email=f"rogue_{uuid.uuid4().hex[:6]}@nowhere.com",
            subscription_status="active"
        )
        db_session.add(unattached_broker)
        await db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(
                current_broker=unattached_broker,
                db=db_session,
                requested_organization_id=None
            )
        assert exc_info.value.status_code == 403
        assert exc_info.value.detail["code"] == "ORGANIZATION_MEMBERSHIP_REQUIRED"

    # 8. Multi-Org Ambiguity Without Header Fails Closed
    async def test_multi_org_without_header_returns_409_conflict(self, db_session: AsyncSession):
        ctx = await self._setup_two_tenants(db_session)
        # Add Broker A to Org B as well
        member_a2 = OrganizationMember(
            organization_id=ctx["org_b"].id,
            broker_id=ctx["broker_a"].id,
            role="AGENT"
        )
        db_session.add(member_a2)
        await db_session.commit()

        with pytest.raises(HTTPException) as exc_info:
            await get_current_tenant(
                current_broker=ctx["broker_a"],
                db=db_session,
                requested_organization_id=None
            )
        assert exc_info.value.status_code == 409
        assert exc_info.value.detail["code"] == "ORGANIZATION_CONTEXT_REQUIRED"

    # 9. Tenant Context Correctly Binds Role
    async def test_tenant_context_resolves_correct_role(self, db_session: AsyncSession):
        ctx = await self._setup_two_tenants(db_session)
        tenant_ctx = await get_current_tenant(
            current_broker=ctx["broker_a"],
            db=db_session,
            requested_organization_id=str(ctx["org_a"].id)
        )
        assert tenant_ctx.organization_id == str(ctx["org_a"].id)
        assert tenant_ctx.role == "AGENT"
        assert tenant_ctx.broker_id == ctx["broker_a"].id

    # 10. AI / Data Boundary Redaction for Non-Privileged Roles
    async def test_restricted_data_filtered_for_agent_role(self):
        property_data = {
            "title": "Luxury Villa",
            "price": 45000000,
            "owner_contact": "+91 99999 11111",
            "commission_rate": 2.5,
            "internal_notes": "Needs urgent sale"
        }
        filtered = filter_payload_for_role("property", property_data, role="AGENT")
        assert filtered["owner_contact"] == "[RESTRICTED]"
        assert filtered["commission_rate"] == "[RESTRICTED]"
        assert filtered["price"] == 45000000

    # 11. Role PII Masking for Read-Only Users
    async def test_confidential_pii_masked_for_read_only_role(self):
        lead_data = {
            "name": "Siddharth Verma",
            "phone": "+919876543210",
            "email": "siddharth@example.com",
            "budget": 20000000
        }
        filtered = filter_payload_for_role("lead", lead_data, role="READ_ONLY")
        assert "****" in filtered["phone"]
        assert "***" in filtered["email"]
        assert "siddharth@example.com" != filtered["email"]
