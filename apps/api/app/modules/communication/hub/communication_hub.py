"""
Part 12 — Communication Hub
============================
One canonical transport entry point for every outbound and inbound message.

The Hub does NOT re-implement transport. It is a thin, policy-enforcing facade
over the existing engine:

    outbound:  Hub → ChannelGate → DeliveryEngine → ChannelManager → Provider
    inbound:   Hub → ConversationRouter → MessageNormalizer → ChannelMessage

Domain services (AI workforce, follow-up, appointment, Revenue Autopilot,
notifications) should depend on this facade instead of reaching into providers
directly, so there is exactly one place where:
  * channel authorization is enforced,
  * idempotency is applied,
  * delivery state is recorded,
  * the unified timeline is written.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communication_models import (
    ChannelMessage,
    OmnichannelConversation,
)
from app.modules.communication.channels.enums import (
    Channel,
    MessageActorType,
    POLICY_DISABLED_CHANNELS,
)
from app.modules.communication.channels.gate import (
    ChannelNotSendableError,
    ensure_channel_sendable,
)
from app.modules.communication.channels.status import (
    ChannelStatus,
    ChannelStatusService,
    provider_key_for,
)
from app.modules.communication.channel_manager.manager import (
    ChannelManager,
    get_channel_manager,
)
from app.modules.communication.conversation_router.router import ConversationRouter
from app.modules.communication.delivery_engine.engine import DeliveryEngine
from app.modules.communication.normalizer.message_normalizer import MessageNormalizer
from app.modules.communication.provider_adapters.base_provider import InboundMessageDTO

logger = logging.getLogger("wefylabs.communication.hub")


@dataclass
class SendResult:
    """Stable result returned by every outbound send."""

    message_id: str
    conversation_id: str
    channel: str
    delivery_status: str
    provider_name: str
    queued: bool = True
    duplicate: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "conversation_id": self.conversation_id,
            "channel": self.channel,
            "delivery_status": self.delivery_status,
            "provider_name": self.provider_name,
            "queued": self.queued,
            "duplicate": self.duplicate,
        }


@dataclass
class InboundResult:
    """Stable result returned by inbound ingestion."""

    conversation_id: str
    message_id: Optional[str]
    channel: str
    is_new_conversation: bool
    duplicate: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "message_id": self.message_id,
            "channel": self.channel,
            "is_new_conversation": self.is_new_conversation,
            "duplicate": self.duplicate,
        }


class CommunicationHub:
    """Canonical, provider-independent communication transport."""

    def __init__(
        self,
        channel_manager: Optional[ChannelManager] = None,
        status_service: Optional[ChannelStatusService] = None,
    ):
        self.channel_manager = channel_manager or get_channel_manager()
        self.status_service = status_service or ChannelStatusService(self.channel_manager)
        self._engine = DeliveryEngine(self.channel_manager)
        self._router = ConversationRouter()
        self._normalizer = MessageNormalizer()

    # ─── Channel introspection ────────────────────────────────────────────────

    async def get_channel_status(self, channel: Union[str, Channel]) -> ChannelStatus:
        canonical = channel if isinstance(channel, Channel) else Channel.normalize(channel)
        return await self.status_service.get_status(canonical)

    async def get_channel_summary(self) -> Dict[str, Any]:
        return await self.status_service.get_public_summary()

    # ─── Conversation resolution ──────────────────────────────────────────────

    async def resolve_conversation(
        self,
        db: AsyncSession,
        organization_id: str,
        lead_id: str,
        channel: Union[str, Channel],
        channel_identifier: str,
    ) -> OmnichannelConversation:
        """Find or create the logical conversation for a customer/channel pair.

        Cross-channel continuity is preserved: if the lead already has an active
        conversation on another channel, this channel is linked to it rather than
        creating a duplicate conversation.
        """
        canonical = channel if isinstance(channel, Channel) else Channel.normalize(channel)
        dto = InboundMessageDTO(
            provider_name="hub",
            channel=canonical.value,
            provider_message_id="",
            idempotency_key="",
            sender_identifier=channel_identifier,
            sender_name="",
            content="",
            organization_id=organization_id,
        )
        conversation, _ = await self._router.route(dto, organization_id, lead_id, db)
        return conversation

    # ─── Outbound ─────────────────────────────────────────────────────────────

    async def send_message(
        self,
        db: AsyncSession,
        organization_id: str,
        lead_id: str,
        channel: Union[str, Channel],
        content: str,
        recipient_identifier: str,
        actor_type: MessageActorType = MessageActorType.HUMAN,
        actor_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        message_type: str = "text",
        template_id: Optional[str] = None,
        template_variables: Optional[Dict[str, str]] = None,
        content_structured: Optional[Dict[str, Any]] = None,
        priority: int = 5,
        idempotency_key: Optional[str] = None,
    ) -> SendResult:
        """The one supported way to send an outbound message.

        ``idempotency_key`` — deterministic send de-duplication. Callers that may
        retry (Celery tasks, scheduled dispatchers, webhook replays) should pass a
        stable key (e.g. ``followup:{execution_id}``) so a retry returns the
        existing message instead of sending twice.

        Raises:
            ChannelNotSendableError: channel is disabled/unavailable.
            ValueError: content is empty or recipient is missing.
        """
        if not content or not content.strip():
            raise ValueError("Message content must not be empty.")
        if not recipient_identifier:
            raise ValueError("recipient_identifier is required.")

        canonical = channel if isinstance(channel, Channel) else Channel.normalize(channel)
        # Gate: enforce enablement/readiness before any persistence or dispatch.
        await ensure_channel_sendable(canonical, self.status_service)

        provider_key = provider_key_for(canonical)
        if provider_key is None:
            raise ChannelNotSendableError(
                canonical.value,
                (await self.status_service.get_status(canonical)).state,
                "No provider is registered for this channel.",
            )

        conversation = await self._resolve_conversation_for_send(
            db, organization_id, lead_id, canonical, recipient_identifier, conversation_id
        )

        # Deterministic de-duplication: an existing message with this key is reused.
        existing: Optional[ChannelMessage] = None
        if idempotency_key:
            from sqlalchemy import select
            stmt = select(ChannelMessage).where(
                ChannelMessage.organization_id == organization_id,
                ChannelMessage.idempotency_key == idempotency_key,
            )
            existing = (await db.execute(stmt)).scalars().first()
            if existing is not None:
                logger.info(
                    "[CommunicationHub] Idempotent send hit key=%s msg_id=%s",
                    idempotency_key, existing.id,
                )
                return SendResult(
                    message_id=existing.id,
                    conversation_id=existing.conversation_id,
                    channel=canonical.value,
                    delivery_status=existing.delivery_status,
                    provider_name=existing.provider_name,
                    queued=False,
                    duplicate=True,
                )

        sent_by_ai = actor_type == MessageActorType.AI_AGENT
        msg: ChannelMessage = await self._engine.enqueue(
            conversation=conversation,
            content=content,
            channel=provider_key,
            recipient_identifier=recipient_identifier,
            db=db,
            message_type=message_type,
            sent_by_ai=sent_by_ai,
            sent_by_agent_id=actor_id if actor_type == MessageActorType.HUMAN else None,
            template_id=template_id,
            template_variables=template_variables,
            content_structured=content_structured,
            priority=priority,
            idempotency_key=idempotency_key,
        )
        # Record the canonical actor + channel on the message.
        msg.sender_type = actor_type.value
        msg.channel = canonical.value

        return SendResult(
            message_id=msg.id,
            conversation_id=conversation.id,
            channel=canonical.value,
            delivery_status=msg.delivery_status,
            provider_name=msg.provider_name,
            queued=True,
        )

    # ─── Inbound ──────────────────────────────────────────────────────────────

    async def ingest_inbound(
        self,
        db: AsyncSession,
        dto: InboundMessageDTO,
        organization_id: str,
        lead_id: str,
    ) -> InboundResult:
        """Normalize and persist an inbound message from any channel.

        Idempotent: duplicate webhooks (same idempotency_key) do not create a
        second message or a second conversation.
        """
        canonical = Channel.normalize(dto.channel)
        if canonical in POLICY_DISABLED_CHANNELS:
            raise ChannelNotSendableError(
                canonical.value,
                (await self.status_service.get_status(canonical)).state,
                "Inbound is not accepted for disabled channels.",
            )

        # Normalize the channel on the DTO so stored records use canonical values.
        dto.channel = canonical.value

        conversation, is_new = await self._router.route(dto, organization_id, lead_id, db)
        msg = await self._normalizer.normalize(dto, conversation, db)

        return InboundResult(
            conversation_id=conversation.id,
            message_id=msg.id if msg else None,
            channel=canonical.value,
            is_new_conversation=is_new,
            duplicate=msg is None,
        )

    # ─── Internal helpers ─────────────────────────────────────────────────────

    async def _resolve_conversation_for_send(
        self,
        db: AsyncSession,
        organization_id: str,
        lead_id: str,
        canonical: Channel,
        recipient_identifier: str,
        conversation_id: Optional[str],
    ) -> OmnichannelConversation:
        if conversation_id:
            from sqlalchemy import select
            stmt = select(OmnichannelConversation).where(
                OmnichannelConversation.id == conversation_id,
                OmnichannelConversation.organization_id == organization_id,
            )
            conv = (await db.execute(stmt)).scalars().first()
            if not conv:
                raise ValueError("Conversation not found in this organization.")
            return conv
        return await self.resolve_conversation(
            db, organization_id, lead_id, canonical, recipient_identifier
        )


__all__ = ["CommunicationHub", "SendResult", "InboundResult"]
