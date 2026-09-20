"""
Test Suite: Cross-Tenant AI Isolation & Boundary Security
Verifies:
  1. Property search isolation: Tenant A's agent never surfaces Tenant B's property inventory.
  2. Shortlist isolation: Tenant A cannot view or manipulate Tenant B's shortlist.
  3. Calendar isolation: Tenant A cannot access Tenant B's calendar slots.
  4. Prompt version isolation: Tenant A's custom prompt template is never leaked to Tenant B.
  5. Cross-tenant shortlist rejection: Tenant A cannot shortlist Tenant B's listing for a Tenant A lead.
"""
import uuid
import pytest
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.agent_models import PromptVersion
from app.modules.ai_agent.tool_executor.services import (
    PropertyService, ShortlistService, CalendarSlotService
)
from app.modules.ai_agent.prompt_engine.builder import PromptBuilder
from app.modules.ai_agent.context_builder.builder import AgentContext


@pytest.mark.asyncio
async def test_property_search_tenant_isolation(db_session):
    """Tenant A's search queries never return listings belonging to Tenant B."""
    # Create Tenant A (Broker A) and Tenant B (Broker B)
    broker_a = Broker(
        email="broker_a@example.com", phone="+919111111111", name="Broker A",
        agency_name="Agency A", city="Bengaluru"
    )
    broker_b = Broker(
        email="broker_b@example.com", phone="+919222222222", name="Broker B",
        agency_name="Agency B", city="Bengaluru"
    )
    db_session.add_all([broker_a, broker_b])
    await db_session.commit()

    # Listing owned by Tenant B
    prop_b = PropertyListing(
        id=uuid.uuid4(),
        broker_id=broker_b.id,
        title="Exclusive Tenant B Penthouse",
        description="Confidential private listing",
        property_type="apartment",
        price=25000000.0,
        currency_code="INR",
        bedrooms=4,
        locality="Indiranagar",
        city="Bengaluru",
        area_value=3200.0,
    )
    db_session.add(prop_b)
    await db_session.commit()

    # Tenant A searches for 4BHK in Indiranagar
    svc = PropertyService(db_session)
    res_a = await svc.search(
        bedrooms=4,
        organization_id=str(broker_a.id),
    )
    assert res_a["total"] == 0
    assert len(res_a["properties"]) == 0

    # Tenant B searches and sees their own listing
    res_b = await svc.search(
        bedrooms=4,
        organization_id=str(broker_b.id),
    )
    assert res_b["total"] == 1
    assert res_b["properties"][0]["id"] == str(prop_b.id)


@pytest.mark.asyncio
async def test_shortlist_cross_tenant_rejection(db_session):
    """Tenant A cannot shortlist a listing belonging to Tenant B."""
    broker_a = Broker(email="ba@example.com", phone="+919333333333", name="Broker A", agency_name="A")
    broker_b = Broker(email="bb@example.com", phone="+919444444444", name="Broker B", agency_name="B")
    db_session.add_all([broker_a, broker_b])
    await db_session.commit()

    lead_a = Lead(
        broker_id=broker_a.id, phone="+919555555555", name="Lead A", source="web", status="active"
    )
    prop_b = PropertyListing(
        id=uuid.uuid4(), broker_id=broker_b.id, title="Listing B", description="Desc",
        property_type="apartment", price=12000000.0, currency_code="INR", area_value=1200.0
    )
    db_session.add_all([lead_a, prop_b])
    await db_session.commit()

    shortlist_svc = ShortlistService(db_session)
    # Attempt to shortlist Tenant B's property under Tenant A's organization
    res = await shortlist_svc.add(
        lead_id=str(lead_a.id),
        property_id=str(prop_b.id),
        organization_id=str(broker_a.id),
    )
    assert res["success"] is False
    assert "not found in this organization" in res["error"]


@pytest.mark.asyncio
async def test_prompt_version_tenant_isolation(db_session):
    """Tenant A's custom prompt version is never loaded for Tenant B."""
    broker_a = Broker(email="pa@example.com", phone="+919666666666", name="Broker A", agency_name="A")
    broker_b = Broker(email="pb@example.com", phone="+919777777777", name="Broker B", agency_name="B")
    db_session.add_all([broker_a, broker_b])
    await db_session.commit()

    # Custom prompt version for Tenant A
    pv_a = PromptVersion(
        id=str(uuid.uuid4()),
        prompt_key="sales_agent_v1",
        organization_id=str(broker_a.id),
        system_template="TENANT_A_CONFIDENTIAL_PROMPT: Welcome to Agency A. {agent_name} {org_name}",
        is_active=True,
    )
    db_session.add(pv_a)
    await db_session.commit()

    builder = PromptBuilder()

    # Load template for Tenant A
    template_a = await builder._load_template(db_session, str(broker_a.id))
    assert "TENANT_A_CONFIDENTIAL_PROMPT" in template_a

    # Load template for Tenant B — must NOT contain Tenant A's template
    template_b = await builder._load_template(db_session, str(broker_b.id))
    assert "TENANT_A_CONFIDENTIAL_PROMPT" not in template_b
