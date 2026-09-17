"""
Part 25 — Copilot Agent Multi-Turn Conversation & Confirmation Tests
====================================================================
Tests:
- Persistent conversation memory across multiple turns
- Multi-turn conversational flow with pronoun / context resolution
- Action preview generation on destructive/high-risk actions
- Action confirmation lifecycle and verification
- Conversation endpoints (list, get, rename, delete)
"""
import uuid
import pytest
import pytest_asyncio
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy import select

from app.config import settings
from app.database import Base, get_db
from app.dependencies import clear_rate_limits
from app.main import app
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.copilot_models import CopilotConversation, CopilotMessage
from app.modules.auth.service import create_access_token
from app.modules.copilot.engine.copilot_agent import CopilotAgentEngine

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    clear_rate_limits()
    yield
    clear_rate_limits()
    app.dependency_overrides.clear()


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
async def broker_agent(db_session: AsyncSession):
    b = Broker(
        id=uuid.uuid4(),
        email=f"agent_{uuid.uuid4().hex[:8]}@example.com",
        name="Aamir Khan",
        agency_name="Apex Realty",
        city="Bengaluru",
        subscription_status="active",
        subscription_plan="pro_monthly"
    )
    db_session.add(b)
    await db_session.commit()
    await db_session.refresh(b)
    return b


@pytest_asyncio.fixture
async def sample_leads(db_session: AsyncSession, broker_agent: Broker):
    leads = [
        Lead(
            id=uuid.uuid4(),
            broker_id=broker_agent.id,
            name=f"Lead {i}",
            phone=f"+91980000000{i}",
            score="hot" if i <= 3 else "warm",
            score_confidence=0.95,
            budget_min=5000000,
            budget_max=8000000,
            pipeline_stage="new"
        )
        for i in range(1, 6)
    ]
    for l in leads:
        db_session.add(l)
    await db_session.commit()
    return leads


@pytest_asyncio.fixture
async def auth_client(db_session: AsyncSession, broker_agent: Broker):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token(broker_agent.id)
    headers = {"Authorization": f"Bearer {token}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=headers) as ac:
        yield ac


@pytest.mark.asyncio
async def test_multi_turn_conversation_flow(db_session: AsyncSession, broker_agent: Broker, sample_leads: list[Lead]):
    # Turn 1: "How many leads do I have?"
    turn_1 = await CopilotAgentEngine.run_copilot_turn(
        db=db_session,
        broker=broker_agent,
        query="How many leads do I have?",
        route_path="/dashboard/leads"
    )
    assert "5" in turn_1["answer_markdown"]
    conv_id = turn_1["conversation_id"]
    assert conv_id is not None

    # Turn 2: "Show me the hottest 5." using conversation_id
    turn_2 = await CopilotAgentEngine.run_copilot_turn(
        db=db_session,
        broker=broker_agent,
        query="Show me the hottest 5.",
        route_path="/dashboard/leads",
        conversation_id=conv_id
    )
    assert "HOT" in turn_2["answer_markdown"]
    assert turn_2["conversation_id"] == conv_id

    # Turn 3: "Create a follow-up for them tomorrow at 10 AM."
    turn_3 = await CopilotAgentEngine.run_copilot_turn(
        db=db_session,
        broker=broker_agent,
        query="Create a follow-up for them tomorrow at 10 AM.",
        route_path="/dashboard/leads",
        conversation_id=conv_id
    )
    assert "created the task" in turn_3["answer_markdown"].lower()

    # Verify persistent messages stored in DB
    conv = await db_session.get(CopilotConversation, uuid.UUID(conv_id))
    assert conv is not None
    stmt_msgs = select(CopilotMessage).where(CopilotMessage.conversation_id == conv.id)
    msgs = (await db_session.execute(stmt_msgs)).scalars().all()
    # 3 turns = 6 messages (3 user + 3 copilot)
    assert len(msgs) == 6


@pytest.mark.asyncio
async def test_action_preview_and_confirmation_lifecycle(db_session: AsyncSession, broker_agent: Broker, sample_leads: list[Lead]):
    # Step 1: Request destructive operation
    preview_turn = await CopilotAgentEngine.run_copilot_turn(
        db=db_session,
        broker=broker_agent,
        query="Delete all my leads.",
        route_path="/dashboard/leads"
    )
    assert preview_turn["action_preview"] is not None
    assert preview_turn["action_preview"]["is_destructive"] is True
    assert preview_turn["action_preview"]["tool_name"] == "delete_lead"
    token = preview_turn["action_preview"]["confirmation_token"]
    assert "Action Confirmation Required" in preview_turn["answer_markdown"]

    # Leads should NOT be deleted yet
    active_leads_stmt = select(Lead).where(Lead.broker_id == broker_agent.id, Lead.deleted_at.is_(None))
    leads_before = (await db_session.execute(active_leads_stmt)).scalars().all()
    assert len(leads_before) == 5

    # Step 2: Confirm action
    confirm_turn = await CopilotAgentEngine.run_copilot_turn(
        db=db_session,
        broker=broker_agent,
        query="Confirm",
        confirmed_action={
            "tool_name": "delete_lead",
            "arguments": preview_turn["action_preview"]["arguments"],
            "confirmation_token": token
        }
    )
    assert "Action Confirmed & Executed" in confirm_turn["answer_markdown"]

    # Leads should now be deleted
    leads_after = (await db_session.execute(active_leads_stmt)).scalars().all()
    assert len(leads_after) == 0


@pytest.mark.asyncio
async def test_copilot_conversation_api_endpoints(auth_client: AsyncClient, broker_agent: Broker):
    # 1. Create conversation
    create_res = await auth_client.post("/api/v1/copilot/conversations", json={
        "title": "Leads Consultation",
        "route_context": "/dashboard/leads"
    })
    assert create_res.status_code == 201
    c_data = create_res.json()
    conv_id = c_data["id"]

    # 2. Query in this conversation
    q_res = await auth_client.post("/api/v1/copilot/query", json={
        "query": "Give me my profile details.",
        "route_path": "/dashboard/leads",
        "conversation_id": conv_id
    })
    assert q_res.status_code == 200
    q_data = q_res.json()
    assert "Aamir Khan" in q_data["answer_markdown"]

    # 3. Retrieve messages
    msg_res = await auth_client.get(f"/api/v1/copilot/conversations/{conv_id}")
    assert msg_res.status_code == 200
    messages = msg_res.json()["messages"]
    assert len(messages) >= 2  # user + copilot

    # 4. Rename conversation
    rename_res = await auth_client.patch(f"/api/v1/copilot/conversations/{conv_id}", json={
        "title": "Renamed Consultation"
    })
    assert rename_res.status_code == 200
    assert rename_res.json()["title"] == "Renamed Consultation"

    # 5. List conversations
    list_res = await auth_client.get("/api/v1/copilot/conversations")
    assert list_res.status_code == 200
    assert any(c["id"] == conv_id for c in list_res.json())

    # 6. Delete conversation
    del_res = await auth_client.delete(f"/api/v1/copilot/conversations/{conv_id}")
    assert del_res.status_code == 200
    assert del_res.json()["success"] is True
