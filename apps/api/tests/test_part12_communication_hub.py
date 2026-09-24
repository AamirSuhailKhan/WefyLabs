"""
Part 12 — Communication Hub Test Suite
======================================
Covers the canonical channel layer and the Communication Hub facade:

  * Canonical channel vocabulary + normalization
  * Truthful channel status derivation (never "adapter exists == live")
  * Outbound send gate (fail-closed on disabled/unavailable channels)
  * Communication Hub outbound persistence + queueing
  * Inbound idempotency (duplicate webhook does not duplicate messages)
  * Cross-channel conversation continuity (one customer, one conversation)
  * WhatsApp hard block (never active; never fabricated delivery)
  * Tenant isolation of outbound sends
"""
from __future__ import annotations

import uuid

import pytest

from app.config import settings
from app.models.communication_models import (
    ChannelMessage,
    ConversationChannelLink,
    OmnichannelConversation,
    OutboundQueue,
)
from app.modules.communication.channels import (
    Channel,
    ChannelEnablementState,
    ChannelNotSendableError,
    ChannelStatusService,
    ensure_channel_sendable,
)
from app.modules.communication.channels.status import provider_key_for
from app.modules.communication.hub import CommunicationHub
from app.modules.communication.provider_adapters.base_provider import (
    DeliveryStatusEnum,
    InboundMessageDTO,
    OutboundMessageDTO,
)
from app.modules.communication.provider_adapters.whatsapp_provider import (
    WhatsAppCloudProvider,
)

# NOTE: pytest-asyncio runs in "auto" mode (see pyproject.toml), so async tests
# are collected without an explicit asyncio mark.


# ─── 1. Canonical channel vocabulary ──────────────────────────────────────────

def test_channel_normalization_maps_legacy_strings():
    assert Channel.normalize("webchat") is Channel.WEB
    assert Channel.normalize("WEB") is Channel.WEB
    assert Channel.normalize("in_app") is Channel.WEB
    assert Channel.normalize("whatsapp_cloud") is Channel.WHATSAPP
    assert Channel.normalize("smtp") is Channel.EMAIL
    assert Channel.normalize(None) is Channel.OTHER
    assert Channel.normalize("totally-unknown") is Channel.OTHER


def test_every_sendable_channel_has_a_provider_key_or_is_internal():
    for ch in (Channel.WEB, Channel.EMAIL, Channel.SMS):
        assert provider_key_for(ch) is not None
    # WhatsApp has a provider key but is deliberately blocked by the Hub.
    assert provider_key_for(Channel.VOICE) is None


# ─── 2. Truthful channel status ───────────────────────────────────────────────

async def test_web_channel_is_enabled_and_sendable():
    svc = ChannelStatusService()
    status = await svc.get_status(Channel.WEB)
    assert status.state == ChannelEnablementState.ENABLED
    assert status.implemented is True
    await ensure_channel_sendable(Channel.WEB)  # must not raise


async def test_whatsapp_is_always_disabled():
    svc = ChannelStatusService()
    status = await svc.get_status(Channel.WHATSAPP)
    assert status.state == ChannelEnablementState.DISABLED
    assert status.enabled is False
    assert status.implemented is False
    with pytest.raises(ChannelNotSendableError) as exc:
        await ensure_channel_sendable(Channel.WHATSAPP)
    assert exc.value.state == ChannelEnablementState.DISABLED


async def test_future_channels_are_disabled():
    svc = ChannelStatusService()
    for ch in (Channel.VOICE, Channel.INSTAGRAM, Channel.FACEBOOK):
        status = await svc.get_status(ch)
        assert status.state == ChannelEnablementState.DISABLED
        assert status.implemented is False


async def test_status_summary_excludes_whatsapp_from_sendable():
    summary = await ChannelStatusService().get_public_summary()
    assert "web" in summary["sendable_channels"]
    assert "whatsapp" not in summary["sendable_channels"]
    assert summary["channels"]["whatsapp"]["state"] == "DISABLED"


# ─── 3. WhatsApp hard block (never fake delivery) ─────────────────────────────

async def test_whatsapp_provider_kill_switch_blocks_send():
    provider = WhatsAppCloudProvider(
        access_token="real_looking_token",
        phone_number_id="1234567890",
        enabled=False,
    )
    dto = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="c1",
        organization_id="org1",
        channel="whatsapp",
        provider_name="whatsapp_cloud",
        recipient_identifier="+919876543210",
        content="hello",
    )
    resp = await provider.send(dto)
    assert resp.success is False
    assert resp.delivery_status == DeliveryStatusEnum.BLOCKED
    assert resp.error_code == "CHANNEL_DISABLED"

    from app.modules.communication.provider_adapters.base_provider import ProviderStatusEnum
    assert await provider.verify_configuration() == ProviderStatusEnum.DISABLED


async def test_whatsapp_provider_unconfigured_is_truthful():
    provider = WhatsAppCloudProvider()  # no creds, not gated (legacy direct use)
    dto = OutboundMessageDTO(
        message_id=str(uuid.uuid4()),
        conversation_id="c1",
        organization_id="org1",
        channel="whatsapp",
        provider_name="whatsapp_cloud",
        recipient_identifier="+919876543210",
        content="hello",
    )
    resp = await provider.send(dto)
    assert resp.success is False
    assert resp.delivery_status == DeliveryStatusEnum.CONFIGURATION_REQUIRED
    assert resp.provider_message_id is None  # no fabricated wamid


# ─── 4. Hub outbound ──────────────────────────────────────────────────────────

async def test_hub_send_on_enabled_channel_persists_and_queues(db_session, test_broker, test_lead):
    hub = CommunicationHub()
    org_id = str(test_broker.organization_id or test_broker.id)

    result = await hub.send_message(
        db=db_session,
        organization_id=org_id,
        lead_id=str(test_lead.id),
        channel=Channel.WEB,
        content="Hello from the hub",
        recipient_identifier="session-abc",
    )

    assert result.queued is True
    assert result.channel == "web"
    assert result.delivery_status == "queued"

    # ChannelMessage persisted with canonical channel + actor type
    msg = (await db_session.get(ChannelMessage, result.message_id))
    assert msg is not None
    assert msg.channel == "web"
    assert msg.direction == "outbound"
    assert msg.sender_type == "HUMAN"

    # OutboundQueue entry created
    from sqlalchemy import select
    q = (await db_session.execute(
        select(OutboundQueue).where(OutboundQueue.message_id == result.message_id)
    )).scalars().first()
    assert q is not None
    assert q.status == "pending"
    assert q.channel == "webchat"  # provider key


async def test_hub_send_rejects_disabled_channel(db_session, test_broker, test_lead):
    hub = CommunicationHub()
    org_id = str(test_broker.organization_id or test_broker.id)
    with pytest.raises(ChannelNotSendableError):
        await hub.send_message(
            db=db_session,
            organization_id=org_id,
            lead_id=str(test_lead.id),
            channel=Channel.WHATSAPP,
            content="should never send",
            recipient_identifier="+919876543210",
        )


async def test_hub_send_rejects_empty_content(db_session, test_broker, test_lead):
    hub = CommunicationHub()
    org_id = str(test_broker.organization_id or test_broker.id)
    with pytest.raises(ValueError):
        await hub.send_message(
            db=db_session,
            organization_id=org_id,
            lead_id=str(test_lead.id),
            channel=Channel.WEB,
            content="   ",
            recipient_identifier="session-abc",
        )


async def test_hub_send_cross_tenant_conversation_rejected(db_session, test_broker, test_lead):
    hub = CommunicationHub()
    org_id = str(test_broker.organization_id or test_broker.id)
    other_org = str(uuid.uuid4())

    # Create a conversation in the *other* tenant.
    other_conv = OmnichannelConversation(
        organization_id=other_org,
        lead_id=str(uuid.uuid4()),
        control_mode="ai",
        status="active",
    )
    db_session.add(other_conv)
    await db_session.flush()

    with pytest.raises(ValueError):
        await hub.send_message(
            db=db_session,
            organization_id=org_id,
            lead_id=str(test_lead.id),
            channel=Channel.WEB,
            content="hi",
            recipient_identifier="session-abc",
            conversation_id=other_conv.id,
        )


# ─── 5. Hub inbound + idempotency + continuity ────────────────────────────────

def _inbound(key: str, sender: str = "session-xyz") -> InboundMessageDTO:
    return InboundMessageDTO(
        provider_name="webchat",
        channel="web",
        provider_message_id=key,
        idempotency_key=key,
        sender_identifier=sender,
        sender_name="Visitor",
        content="Looking for a 3BHK",
    )


async def test_hub_inbound_is_idempotent(db_session, test_broker, test_lead):
    hub = CommunicationHub()
    org_id = str(test_broker.organization_id or test_broker.id)

    first = await hub.ingest_inbound(db_session, _inbound("dup-key-1"), org_id, str(test_lead.id))
    assert first.duplicate is False
    assert first.message_id is not None

    second = await hub.ingest_inbound(db_session, _inbound("dup-key-1"), org_id, str(test_lead.id))
    assert second.duplicate is True
    assert second.message_id is None
    assert second.conversation_id == first.conversation_id


async def test_hub_cross_channel_continuity(db_session, test_broker, test_lead):
    hub = CommunicationHub()
    org_id = str(test_broker.organization_id or test_broker.id)

    web = await hub.ingest_inbound(db_session, _inbound("web-1", "session-1"), org_id, str(test_lead.id))
    email_dto = InboundMessageDTO(
        provider_name="email",
        channel="email",
        provider_message_id="email-1",
        idempotency_key="email-key-1",
        sender_identifier="customer@example.com",
        sender_name="Customer",
        content="Also emailing about the 3BHK",
    )
    email = await hub.ingest_inbound(db_session, email_dto, org_id, str(test_lead.id))

    # Same logical conversation across channels — no duplicate conversation.
    assert email.conversation_id == web.conversation_id

    from sqlalchemy import select
    links = (await db_session.execute(
        select(ConversationChannelLink).where(
            ConversationChannelLink.conversation_id == web.conversation_id
        )
    )).scalars().all()
    channels = {l.channel for l in links}
    assert {"web", "email"}.issubset(channels)
