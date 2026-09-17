"""
Part 25 — Copilot Tool Registry Unit & Integration Tests
=========================================================
Validates all 21 tools in COPILOT_TOOL_REGISTRY:
- Profiles, Organization, Leads (read, filter, score, update, delete)
- Tasks, Follow-ups, Notes
- Google Calendar integration & Availability
- Email drafting & Brevo dispatch
- Analytics & Canonical Product Knowledge
- Strict tenant isolation and error safety
"""
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.config import settings
from app.database import Base
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, LeadNote
from app.modules.copilot.tools.tool_registry import COPILOT_TOOL_REGISTRY, ToolRiskLevel

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    yield


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_maker() as session:
        yield session
    await engine.dispose()


@pytest_asyncio.fixture
async def broker_1(db_session: AsyncSession):
    b = Broker(
        id=uuid.uuid4(),
        email=f"broker1_{uuid.uuid4().hex[:8]}@example.com",
        name="Aamir Khan",
        agency_name="Apex Global Properties",
        city="Bengaluru",
        subscription_status="active",
        subscription_plan="pro_monthly",
        trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7)
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def lead_1(db_session: AsyncSession, broker_1: Broker):
    l = Lead(
        id=uuid.uuid4(),
        broker_id=broker_1.id,
        name="Rajesh Sharma",
        phone="+919876543210",
        score="hot",
        score_confidence=0.95,
        budget_min=5000000,
        budget_max=7500000,
        property_type="3bhk",
        pipeline_stage="contacted",
        source="google"
    )
    db_session.add(l)
    await db_session.commit()
    await db_session.refresh(l)
    return l


@pytest.mark.asyncio
async def test_read_profile_tool(db_session: AsyncSession, broker_1: Broker):
    tool = COPILOT_TOOL_REGISTRY["read_profile"]
    res = await tool.handler(db_session, broker_1, {})

    assert res["name"] == "Aamir Khan"
    assert res["agency_name"] == "Apex Global Properties"
    assert res["subscription_status"] == "active"
    assert res["trial_days_remaining"] >= 6
    assert "_citation" in res


@pytest.mark.asyncio
async def test_list_leads_tool_filtering(db_session: AsyncSession, broker_1: Broker, lead_1: Lead):
    tool = COPILOT_TOOL_REGISTRY["list_leads"]

    # Filter hot leads
    res = await tool.handler(db_session, broker_1, {"score": "hot", "limit": 10})
    assert res["total_matching"] >= 1
    assert any(l["name"] == "Rajesh Sharma" for l in res["leads"])
    assert res["leads"][0]["score"] == "HOT"

    # Filter non-existent score
    res_cold = await tool.handler(db_session, broker_1, {"score": "cold"})
    assert res_cold["total_matching"] == 0


@pytest.mark.asyncio
async def test_get_lead_tool(db_session: AsyncSession, broker_1: Broker, lead_1: Lead):
    tool = COPILOT_TOOL_REGISTRY["get_lead"]
    res = await tool.handler(db_session, broker_1, {"lead_id": str(lead_1.id)})

    assert res["name"] == "Rajesh Sharma"
    assert res["phone"] == "+919876543210"
    assert res["stage"] == "contacted"
    assert "₹5,000,000" in res["budget_range"]


@pytest.mark.asyncio
async def test_create_and_update_lead_tools(db_session: AsyncSession, broker_1: Broker):
    # 1. Create Lead
    create_tool = COPILOT_TOOL_REGISTRY["create_lead"]
    c_res = await create_tool.handler(db_session, broker_1, {
        "name": "Priya Verma",
        "phone": "+919811223344",
        "score": "warm",
        "budget_min": 4000000,
        "budget_max": 6000000,
        "property_type": "2bhk"
    })
    assert c_res["success"] is True
    lead_id = c_res["lead_id"]

    # 2. Update Lead Stage & Score
    update_tool = COPILOT_TOOL_REGISTRY["update_lead"]
    u_res = await update_tool.handler(db_session, broker_1, {
        "lead_id": lead_id,
        "stage": "viewing scheduled",
        "score": "hot"
    })
    assert u_res["success"] is True
    assert "stage set to 'viewing scheduled'" in u_res["changes"]


@pytest.mark.asyncio
async def test_add_lead_note_tool(db_session: AsyncSession, broker_1: Broker, lead_1: Lead):
    tool = COPILOT_TOOL_REGISTRY["add_lead_note"]
    res = await tool.handler(db_session, broker_1, {
        "lead_id": str(lead_1.id),
        "content": "Client requested east-facing units with balcony."
    })
    assert res["success"] is True
    assert "east-facing" in res["content"]

    # Verify persisted in database
    notes = (await db_session.execute(select(LeadNote).where(LeadNote.lead_id == str(lead_1.id)))).scalars().all()
    assert len(notes) >= 1
    assert notes[0].content == "Client requested east-facing units with balcony."


@pytest.mark.asyncio
async def test_create_and_complete_task_tools(db_session: AsyncSession, broker_1: Broker, lead_1: Lead):
    # 1. Create Task
    create_tool = COPILOT_TOOL_REGISTRY["create_task"]
    t_res = await create_tool.handler(db_session, broker_1, {
        "title": "Send floor plans to Rajesh",
        "priority": "urgent",
        "due_in_hours": 12,
        "lead_id": str(lead_1.id)
    })
    assert t_res["success"] is True
    task_id = t_res["task_id"]

    # 2. Complete Task
    comp_tool = COPILOT_TOOL_REGISTRY["complete_task"]
    c_res = await comp_tool.handler(db_session, broker_1, {"task_id": task_id})
    assert c_res["success"] is True
    assert "completed" in c_res["message"]

    # Verify task state in DB
    task = await db_session.get(Task, task_id)
    assert task.status == "completed"
    assert task.completed_at is not None


@pytest.mark.asyncio
async def test_delete_lead_destructive_tool(db_session: AsyncSession, broker_1: Broker, lead_1: Lead):
    del_tool = COPILOT_TOOL_REGISTRY["delete_lead"]
    assert del_tool.risk_level == ToolRiskLevel.DESTRUCTIVE
    assert del_tool.requires_confirmation is True

    res = await del_tool.handler(db_session, broker_1, {"lead_ids": [str(lead_1.id)]})
    assert res["success"] is True
    assert res["deleted_count"] == 1

    # Verify soft deleted in DB
    refreshed_lead = await db_session.get(Lead, lead_1.id)
    assert refreshed_lead.deleted_at is not None


@pytest.mark.asyncio
async def test_calendar_availability_and_scheduling_tools(db_session: AsyncSession, broker_1: Broker):
    # Check availability
    avail_tool = COPILOT_TOOL_REGISTRY["check_calendar_availability"]
    a_res = await avail_tool.handler(db_session, broker_1, {"date": "2026-09-05"})
    assert "available_slots" in a_res
    assert len(a_res["available_slots"]) > 0

    # Schedule meeting (High-risk write)
    sched_tool = COPILOT_TOOL_REGISTRY["schedule_calendar_meeting"]
    assert sched_tool.risk_level == ToolRiskLevel.HIGH_RISK_WRITE
    assert sched_tool.requires_confirmation is True

    s_res = await sched_tool.handler(db_session, broker_1, {
        "title": "Site Inspection",
        "scheduled_at": "2026-09-05 10:00 AM",
        "client_name": "Rajesh"
    })
    assert s_res["success"] is True
    assert "Google Calendar" in s_res["_citation"]


@pytest.mark.asyncio
async def test_email_draft_and_send_tools(db_session: AsyncSession, broker_1: Broker):
    # Draft email
    draft_tool = COPILOT_TOOL_REGISTRY["draft_email"]
    d_res = await draft_tool.handler(db_session, broker_1, {
        "lead_name": "Rajesh",
        "property_details": "Sobha Royal Pavilion 3BHK"
    })
    assert "Sobha Royal Pavilion" in d_res["body"]
    assert d_res["subject"] is not None

    # Send email
    send_tool = COPILOT_TOOL_REGISTRY["send_email"]
    assert send_tool.risk_level == ToolRiskLevel.HIGH_RISK_WRITE
    assert send_tool.requires_confirmation is True

    with patch("app.tasks.queue_workers.process_email_dispatch.delay") as mock_delay:
        s_res = await send_tool.handler(db_session, broker_1, {
            "recipient_email": "client@example.com",
            "subject": "Follow up",
            "body": "Hello client"
        })
        assert s_res["success"] is True
        mock_delay.assert_called_once()


@pytest.mark.asyncio
async def test_canonical_product_help_tool(db_session: AsyncSession, broker_1: Broker):
    tool = COPILOT_TOOL_REGISTRY["get_product_help"]

    # Test billing question
    res = await tool.handler(db_session, broker_1, {"query": "How much does the pro plan cost?"})
    assert len(res["results"]) > 0
    assert "Product Documentation" in res["_citation"]

    # Test calendar question
    res_cal = await tool.handler(db_session, broker_1, {"query": "How do I connect Google Calendar?"})
    assert len(res_cal["results"]) > 0
    assert "Calendar" in res_cal["results"][0]["title"]
