"""
Part 12 — Follow-Up ↔ Communication Hub Integration Tests
=========================================================
Covers:
  * Follow-up execution dispatch routed through the Communication Hub
    (never calling providers directly), including idempotency and a disabled-channel block.
  * Truthful per-channel status exposed on the follow-up policy API.
  * Sales-action engine default channel resolved from availability (never WhatsApp).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db, get_current_broker
from app.models.follow_up_models import FollowUpExecution
from app.models.communication_models import ChannelMessage, OutboundQueue
from app.modules.communication.channels import ChannelNotSendableError
from app.modules.sales_action.taxonomies import CommunicationChannel
from app.modules.sales_action.service import SalesActionDomainService


def _org(broker) -> str:
    return str(broker.organization_id or broker.id)


async def _make_execution(db_session, broker, lead, channel: str, body: str = "Hello there") -> FollowUpExecution:
    execution = FollowUpExecution(
        id=str(uuid.uuid4()),
        lead_id=str(lead.id),
        organization_id=_org(broker),
        broker_id=str(lead.broker_id),
        channel=channel,
        reason_type="UNANSWERED_INQUIRY",
        status="SCHEDULED",
        scheduled_for_utc=datetime.now(timezone.utc),
        recipient_identifier=lead.phone or lead.email or "customer",
        message_body=body,
    )
    db_session.add(execution)
    await db_session.commit()
    return execution


# ─── 1. Dispatch through the Communication Hub ────────────────────────────────

async def test_dispatch_execution_via_hub(db_session, test_broker, test_lead):
    from app.modules.follow_up.service import FollowUpOrchestratorService

    execution = await _make_execution(db_session, test_broker, test_lead, channel="WEB")
    service = FollowUpOrchestratorService(db_session)

    result = await service.dispatch_execution(execution.id, _org(test_broker))

    assert result["status"] == "dispatched"
    assert result["message_id"]
    assert result["channel"] == "web"

    # A canonical ChannelMessage + queued outbound item must exist (Hub path, not provider).
    msg = (await db_session.execute(
        select(ChannelMessage).where(ChannelMessage.id == result["message_id"])
    )).scalars().first()
    assert msg is not None
    assert msg.channel == "web"
    assert msg.direction == "outbound"

    queue_item = (await db_session.execute(
        select(OutboundQueue).where(OutboundQueue.message_id == result["message_id"])
    )).scalars().first()
    assert queue_item is not None
    assert queue_item.status == "pending"

    refreshed = (await db_session.execute(
        select(FollowUpExecution).where(FollowUpExecution.id == execution.id)
    )).scalars().first()
    assert refreshed.status == "DISPATCHED"
    assert refreshed.executed_at is not None


async def test_dispatch_is_idempotent(db_session, test_broker, test_lead):
    from app.modules.follow_up.service import FollowUpOrchestratorService

    execution = await _make_execution(db_session, test_broker, test_lead, channel="WEB")
    service = FollowUpOrchestratorService(db_session)

    first = await service.dispatch_execution(execution.id, _org(test_broker))
    second = await service.dispatch_execution(execution.id, _org(test_broker))

    assert first["status"] == "dispatched"
    assert second["status"] == "already_dispatched"
    assert second["message_id"] is None

    # Only one outbound message must exist for this execution.
    msgs = (await db_session.execute(
        select(ChannelMessage).where(ChannelMessage.lead_id == str(test_lead.id))
    )).scalars().all()
    assert len(msgs) == 1


async def test_dispatch_rejects_disabled_channel(db_session, test_broker, test_lead):
    from app.modules.follow_up.service import FollowUpOrchestratorService

    execution = await _make_execution(db_session, test_broker, test_lead, channel="WHATSAPP")
    service = FollowUpOrchestratorService(db_session)

    with pytest.raises(ChannelNotSendableError):
        await service.dispatch_execution(execution.id, _org(test_broker))


# ─── 2. Per-channel status on the policy API ──────────────────────────────────

async def test_get_channel_status_reports_whatsapp_disabled(db_session):
    from app.modules.follow_up.service import FollowUpOrchestratorService

    summary = await FollowUpOrchestratorService(db_session).get_channel_status()
    assert summary["channels"]["whatsapp"]["state"] == "DISABLED"
    assert summary["channels"]["web"]["state"] == "ENABLED"
    assert "whatsapp" not in summary["sendable_channels"]


async def test_policy_api_exposes_channel_status(db_session, test_broker):
    async def override_get_db():
        yield db_session

    async def override_get_broker():
        return test_broker

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_broker] = override_get_broker
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/v1/followups/policies")
            assert resp.status_code == 200
            data = resp.json()
            assert data["channel_status"] is not None
            assert data["channel_status"]["channels"]["whatsapp"]["state"] == "DISABLED"

            ch_resp = await client.get("/api/v1/v1/followups/channels/status")
            assert ch_resp.status_code == 200
            assert ch_resp.json()["channels"]["web"]["state"] == "ENABLED"
    finally:
        app.dependency_overrides.clear()


# ─── 3. Sales-action availability default ─────────────────────────────────────

async def test_sales_action_default_channel_is_not_disabled_whatsapp(db_session, test_broker):
    service = SalesActionDomainService(db_session)
    policy = await service.get_or_create_policy(_org(test_broker))

    channel = await service._resolve_default_channel(policy)

    assert channel != CommunicationChannel.WHATSAPP
    assert channel in (CommunicationChannel.EMAIL, CommunicationChannel.IN_APP, CommunicationChannel.SMS)
