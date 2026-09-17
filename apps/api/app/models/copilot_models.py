"""
Volume 2 PART 25 — Copilot Conversation & Message Models
=========================================================
SQLAlchemy 2.0 models for persistent AI Copilot conversation sessions:
- CopilotConversation: Tracks multi-turn dialog sessions per broker and tenant
- CopilotMessage: Stores user prompts, assistant answers, tool calls, tool results,
  citations, reasoning, and pending action previews.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, ForeignKey, Index, func, Uuid, JSON
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")
UUIDType = Uuid(as_uuid=True)


def _gen_uuid() -> uuid.UUID:
    return uuid.uuid4()


class CopilotConversation(Base, TimestampMixin):
    """
    Persistent conversation session for the authenticated user and organization.
    Ensures multi-turn conversational context survives browser refresh and navigation.
    """
    __tablename__ = "copilot_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        primary_key=True,
        default=_gen_uuid
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    title: Mapped[str] = mapped_column(String(255), default="New Conversation", nullable=False)
    route_context: Mapped[Optional[str]] = mapped_column(String(100), default="/dashboard", nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    messages: Mapped[List["CopilotMessage"]] = relationship(
        "CopilotMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="CopilotMessage.created_at"
    )

    __table_args__ = (
        Index("ix_copilot_conversations_broker_updated", "broker_id", "updated_at"),
        Index("ix_copilot_conversations_org_created", "organization_id", "created_at"),
    )


class CopilotMessage(Base):
    """
    Individual turn within a Copilot conversation.
    Stores raw user prompts, assistant markdown responses, structured tool invocations,
    tool execution results, provenance citations, and action previews.
    """
    __tablename__ = "copilot_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        primary_key=True,
        default=_gen_uuid
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("copilot_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    sender: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" | "copilot" | "system"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    thought_reasoning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tool_calls: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONBType, nullable=True)
    tool_results: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONBType, nullable=True)
    citations: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(JSONBType, nullable=True)
    action_preview: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, nullable=True)
    confidence_score: Mapped[float] = mapped_column(default=0.98, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True
    )

    conversation: Mapped["CopilotConversation"] = relationship(
        "CopilotConversation",
        back_populates="messages"
    )
