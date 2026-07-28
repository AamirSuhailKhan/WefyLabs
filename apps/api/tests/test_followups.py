import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.config import settings
from app.dependencies import get_db, clear_rate_limits
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.follow_up import FollowUp
from app.services.followup_service import schedule_followup_sequence, cancel_pending_followups
from app.tasks.followup_tasks import async_send_follow_up, async_check_and_schedule_followups
from app.modules.leads.service import update_lead_stage, update_lead_status
from app.modules.auth.service import create_access_token

@pytest.fixture(autouse=True)
def setup_test_env():
    settings.ENV = "testing"
    clear_rate_limits()
    yield
    clear_rate_limits()

@pytest.mark.asyncio
async def test_followup_sequence_creation_and_api(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Schedule sequence (T+24h, T+48h, T+72h)
    followups = await schedule_followup_sequence(db_session, test_lead)
    assert len(followups) == 3
    assert followups[0].sequence_number == 1
    assert followups[0].status == "scheduled"
    assert followups[1].sequence_number == 2
    assert followups[2].sequence_number == 3

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 2. GET /api/v1/leads/{lead_id}/follow-ups
        res_get = await ac.get(f"/api/v1/leads/{test_lead.id}/follow-ups", headers=headers)
        assert res_get.status_code == 200
        items = res_get.json()
        assert len(items) == 3
        assert items[0]["sequence_number"] == 1
        assert items[0]["status"] == "scheduled"

        # 3. POST /api/v1/leads/{lead_id}/follow-ups/cancel
        res_cancel = await ac.post(f"/api/v1/leads/{test_lead.id}/follow-ups/cancel", headers=headers)
        assert res_cancel.status_code == 200
        assert res_cancel.json()["cancelled_count"] == 3

        # Verify status in DB updated to cancelled
        res_get_after = await ac.get(f"/api/v1/leads/{test_lead.id}/follow-ups", headers=headers)
        assert res_get_after.json()[0]["status"] == "cancelled"

    app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_auto_cancel_on_stage_update(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    # Schedule follow-ups
    await schedule_followup_sequence(db_session, test_lead)

    # Move stage to closed_won
    await update_lead_stage(db_session, test_lead.id, test_broker.id, "closed_won")

    # Verify all follow-ups cancelled
    stmt = select(FollowUp).where(FollowUp.lead_id == test_lead.id, FollowUp.status == "scheduled")
    pending = (await db_session.execute(stmt)).scalars().all()
    assert len(pending) == 0

@pytest.mark.asyncio
async def test_celery_task_dispatch(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    # Create due follow-up (scheduled in the past)
    due_followup = FollowUp(
        lead_id=test_lead.id,
        sequence_number=1,
        scheduled_at=datetime.now(timezone.utc) - timedelta(hours=1),
        status="scheduled",
        message="Test due follow-up message"
    )
    db_session.add(due_followup)
    await db_session.commit()
    await db_session.refresh(due_followup)

    # Execute async send follow-up helper directly with session context
    success = await async_send_follow_up(str(due_followup.id), session=db_session)
    assert success is True

    await db_session.refresh(due_followup)
    assert due_followup.status == "sent"
    assert due_followup.sent_at is not None
