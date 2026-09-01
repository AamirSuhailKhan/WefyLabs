"""
Conversation Router — Cross-Channel Unification
=================================================
Step 4 of the 13-step message lifecycle pipeline.

Resolves or creates the OmnichannelConversation for an incoming message.
Uses channel_identifier (phone/email/chat_id) to find existing conversation.
If found: returns existing (cross-channel continuity).
If not found: creates new conversation + ConversationChannelLink + ConversationControl.

Invariant: One customer → one OmnichannelConversation per organization.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.communication.provider_adapters.base_provider import InboundMessageDTO
from app.models.communication_models import (
    OmnichannelConversation, ConversationChannelLink, ConversationControl
)

logger = logging.getLogger(__name__)


class ConversationRouter:
    """
    Conversation lookup and creation service.

    Cross-channel unification logic:
    - Look up ConversationChannelLink by (org, channel, channel_identifier)
    - If found: return existing OmnichannelConversation
    - If not found: check if lead has an existing conversation from any other channel
    - If cross-channel match: add new ConversationChannelLink to existing conversation
    - If truly new: create OmnichannelConversation + ConversationChannelLink + ConversationControl
    """

    async def route(
        self,
        dto: InboundMessageDTO,
        organization_id: str,
        lead_id: str,
        db: AsyncSession,
    ) -> Tuple[OmnichannelConversation, bool]:
        """
        Route inbound message to the correct OmnichannelConversation.

        Returns:
            (OmnichannelConversation, is_new: bool)
        """
        # ─── Step 1: Find by channel identifier ──────────────────────────────
        conversation = await self._find_by_channel_identifier(
            db, organization_id, dto.channel, dto.sender_identifier
        )
        if conversation:
            logger.info(
                f"[ConvRouter] Existing conversation_id={conversation.id} "
                f"channel={dto.channel} sender={dto.sender_identifier}"
            )
            return conversation, False

        # ─── Step 2: Find any existing conversation for this lead ─────────────
        existing_for_lead = await self._find_by_lead(db, organization_id, lead_id)

        if existing_for_lead:
            # Cross-channel: link new channel to existing conversation
            await self._add_channel_link(db, existing_for_lead.id, organization_id,
                                         dto.channel, dto.sender_identifier,
                                         dto.provider_name)
            logger.info(
                f"[ConvRouter] Cross-channel link added conversation_id={existing_for_lead.id} "
                f"new_channel={dto.channel}"
            )
            return existing_for_lead, False

        # ─── Step 3: Create new conversation ─────────────────────────────────
        conversation = await self._create_conversation(
            db, organization_id, lead_id, dto
        )
        logger.info(
            f"[ConvRouter] New conversation created id={conversation.id} "
            f"channel={dto.channel} org={organization_id}"
        )
        return conversation, True

    async def _find_by_channel_identifier(
        self, db: AsyncSession, organization_id: str,
        channel: str, channel_identifier: str
    ) -> Optional[OmnichannelConversation]:
        """Look up conversation via ConversationChannelLink."""
        stmt = (
            select(OmnichannelConversation)
            .join(ConversationChannelLink,
                  ConversationChannelLink.conversation_id == OmnichannelConversation.id)
            .where(
                ConversationChannelLink.organization_id == organization_id,
                ConversationChannelLink.channel == channel,
                ConversationChannelLink.channel_identifier == channel_identifier,
                ConversationChannelLink.is_active == True,
                OmnichannelConversation.status != "archived",
            )
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def _find_by_lead(
        self, db: AsyncSession, organization_id: str, lead_id: str
    ) -> Optional[OmnichannelConversation]:
        """Find any active conversation for this lead (cross-channel check)."""
        stmt = (
            select(OmnichannelConversation)
            .where(
                OmnichannelConversation.organization_id == organization_id,
                OmnichannelConversation.lead_id == lead_id,
                OmnichannelConversation.status == "active",
            )
            .order_by(OmnichannelConversation.created_at.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def _add_channel_link(
        self, db: AsyncSession, conversation_id: str, organization_id: str,
        channel: str, channel_identifier: str, provider_name: str
    ) -> ConversationChannelLink:
        """Add a new channel link to an existing conversation."""
        link = ConversationChannelLink(
            conversation_id=conversation_id,
            organization_id=organization_id,
            channel=channel,
            channel_identifier=channel_identifier,
            provider_name=provider_name,
            is_active=True,
            last_activity_at=datetime.now(timezone.utc),
        )
        db.add(link)
        await db.flush()
        return link

    async def _create_conversation(
        self, db: AsyncSession, organization_id: str, lead_id: str,
        dto: InboundMessageDTO
    ) -> OmnichannelConversation:
        """Create a brand new OmnichannelConversation with its first channel link and control record."""
        conversation = OmnichannelConversation(
            organization_id=organization_id,
            lead_id=lead_id,
            control_mode="ai",
            preferred_channel=dto.channel,
            status="active",
            last_channel=dto.channel,
        )
        db.add(conversation)
        await db.flush()

        # Create channel link
        link = ConversationChannelLink(
            conversation_id=conversation.id,
            organization_id=organization_id,
            channel=dto.channel,
            channel_identifier=dto.sender_identifier,
            provider_name=dto.provider_name,
            is_active=True,
            last_activity_at=datetime.now(timezone.utc),
        )
        db.add(link)

        # Create control record (AI mode by default)
        control = ConversationControl(
            conversation_id=conversation.id,
            organization_id=organization_id,
            control_mode="ai",
        )
        db.add(control)

        await db.flush()
        return conversation
