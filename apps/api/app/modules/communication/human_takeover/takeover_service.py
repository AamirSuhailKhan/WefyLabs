"""
Human Takeover Service
========================
Handles seamless AI ↔ Human control transitions.

Pause AI:  ConversationControl.mode → 'human'
Resume AI: ConversationControl.mode → 'ai'

AI Agent checks control_mode before processing any message.
Human takeover creates an AI briefing to help the human agent understand context.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.communication_models import (
    OmnichannelConversation, ConversationControl, ChannelMessage
)
from app.modules.communication.events.comm_events import HumanTakeoverEvent, AITakeoverEvent

logger = logging.getLogger(__name__)


class HumanTakeoverService:
    """
    Manages control mode transitions between AI and human agents.

    Thread-safe: control_mode is a DB-backed flag read before each AI turn.
    """

    async def pause_ai(
        self,
        conversation: OmnichannelConversation,
        taken_over_by: str,
        db: AsyncSession,
        reason: Optional[str] = None,
        agent_name: Optional[str] = None,
    ) -> HumanTakeoverEvent:
        """
        Transition conversation from AI mode to human mode.
        Generates AI briefing for the incoming human agent.
        """
        control = await self._get_or_create_control(db, conversation)

        # Generate AI briefing from recent conversation context
        ai_briefing = await self._generate_briefing(db, conversation)

        control.control_mode = "human"
        control.assigned_agent_id = taken_over_by
        control.assigned_agent_name = agent_name
        control.takeover_reason = reason
        control.takeover_at = datetime.now(timezone.utc)
        control.takeover_by = taken_over_by
        control.ai_briefing = ai_briefing

        # Update parent conversation
        conversation.control_mode = "human"
        conversation.assigned_agent_id = taken_over_by

        await db.flush()

        event = HumanTakeoverEvent(
            conversation_id=conversation.id,
            organization_id=conversation.organization_id,
            lead_id=conversation.lead_id,
            takeover_by=taken_over_by,
            takeover_reason=reason,
            ai_briefing=ai_briefing,
        )

        logger.info(
            f"[HumanTakeover] AI paused for conversation_id={conversation.id} "
            f"agent={taken_over_by} reason={reason}"
        )
        return event

    async def resume_ai(
        self,
        conversation: OmnichannelConversation,
        resumed_by: str,
        db: AsyncSession,
    ) -> AITakeoverEvent:
        """
        Transition conversation back from human to AI mode.
        AI resumes with full conversation context.
        """
        control = await self._get_or_create_control(db, conversation)
        previous_mode = control.control_mode

        control.control_mode = "ai"
        control.resumed_at = datetime.now(timezone.utc)
        control.resumed_by = resumed_by
        # Clear human assignment (AI takes over)
        control.assigned_agent_id = None
        control.assigned_agent_name = None

        # Update parent conversation
        conversation.control_mode = "ai"
        conversation.assigned_agent_id = None

        await db.flush()

        event = AITakeoverEvent(
            conversation_id=conversation.id,
            organization_id=conversation.organization_id,
            lead_id=conversation.lead_id,
            resumed_by=resumed_by,
            previous_control_mode=previous_mode,
        )

        logger.info(
            f"[HumanTakeover] AI resumed conversation_id={conversation.id} "
            f"by={resumed_by}"
        )
        return event

    async def is_ai_active(
        self, conversation: OmnichannelConversation, db: AsyncSession
    ) -> bool:
        """
        Check if AI is currently in control of this conversation.
        AI Agent calls this before processing any message.
        """
        control = await self._get_control(db, conversation.id)
        if control is None:
            return True  # Default: AI active if no control record
        return control.control_mode == "ai"

    async def get_control_status(
        self, conversation_id: str, db: AsyncSession
    ) -> Optional[dict]:
        """Return current control status for a conversation."""
        control = await self._get_control(db, conversation_id)
        if not control:
            return {"mode": "ai", "assigned_agent": None}
        return {
            "mode": control.control_mode,
            "assigned_agent_id": control.assigned_agent_id,
            "assigned_agent_name": control.assigned_agent_name,
            "takeover_reason": control.takeover_reason,
            "takeover_at": control.takeover_at.isoformat() if control.takeover_at else None,
            "ai_briefing": control.ai_briefing,
        }

    async def assign_agent(
        self,
        conversation: OmnichannelConversation,
        agent_id: str,
        db: AsyncSession,
        agent_name: Optional[str] = None,
    ) -> None:
        """Assign a specific human agent to a conversation (without changing mode)."""
        control = await self._get_or_create_control(db, conversation)
        control.assigned_agent_id = agent_id
        control.assigned_agent_name = agent_name
        conversation.assigned_agent_id = agent_id
        await db.flush()

    async def transfer_agent(
        self,
        conversation: OmnichannelConversation,
        new_agent_id: str,
        db: AsyncSession,
        new_agent_name: Optional[str] = None,
    ) -> None:
        """Transfer conversation from one human agent to another."""
        control = await self._get_or_create_control(db, conversation)
        control.assigned_agent_id = new_agent_id
        control.assigned_agent_name = new_agent_name
        conversation.assigned_agent_id = new_agent_id
        await db.flush()
        logger.info(f"[HumanTakeover] Transfer to agent={new_agent_id} conv={conversation.id}")

    # ─── Internal Helpers ─────────────────────────────────────────────────────

    async def _get_control(
        self, db: AsyncSession, conversation_id: str
    ) -> Optional[ConversationControl]:
        stmt = select(ConversationControl).where(
            ConversationControl.conversation_id == conversation_id
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def _get_or_create_control(
        self, db: AsyncSession, conversation: OmnichannelConversation
    ) -> ConversationControl:
        control = await self._get_control(db, conversation.id)
        if not control:
            control = ConversationControl(
                conversation_id=conversation.id,
                organization_id=conversation.organization_id,
                control_mode=conversation.control_mode or "ai",
            )
            db.add(control)
            await db.flush()
        return control

    async def _generate_briefing(
        self, db: AsyncSession, conversation: OmnichannelConversation
    ) -> str:
        """Generate context briefing for incoming human agent from recent messages."""
        stmt = (
            select(ChannelMessage)
            .where(ChannelMessage.conversation_id == conversation.id)
            .order_by(ChannelMessage.created_at.desc())
            .limit(5)
        )
        result = await db.execute(stmt)
        recent = list(reversed(result.scalars().all()))

        lines = [
            f"=== AI HANDOFF BRIEFING ===",
            f"Lead ID: {conversation.lead_id}",
            f"AI Sentiment: {conversation.ai_sentiment}",
            f"AI Summary: {conversation.ai_summary or 'No summary yet'}",
            f"Next Best Action: {conversation.ai_next_best_action or 'None'}",
            f"Last Channel: {conversation.last_channel}",
            "",
            "Recent Messages:",
        ]
        for msg in recent:
            direction = "←" if msg.direction == "inbound" else "→"
            lines.append(f"  [{msg.channel.upper()}] {direction} {msg.content[:120]}")

        return "\n".join(lines)
