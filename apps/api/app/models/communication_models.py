import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer, Text, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")

class UnifiedConversation(Base, TimestampMixin):
    """
    Omnichannel Unified Conversation model aggregating all customer messages
    (WhatsApp, Email, SMS, Calls, Internal Notes) for a single Lead.
    """
    __tablename__ = "unified_conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    assignee_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True, index=True)
    unread_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_channel: Mapped[str] = mapped_column(String(30), default="whatsapp", nullable=False)
    last_message_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    tags: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)
    is_snoozed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    snoozed_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # AI Intelligence Fields
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_sentiment: Mapped[str] = mapped_column(String(30), default="neutral", nullable=False)
    ai_urgency_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    ai_detected_objections: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)
    ai_next_best_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    messages: Mapped[List["UnifiedMessage"]] = relationship("UnifiedMessage", back_populates="conversation", cascade="all, delete-orphan")

class UnifiedMessage(Base, TimestampMixin):
    """
    Individual message entity supporting WhatsApp, Email, SMS, Voice Call logs, and Team Internal Notes.
    """
    __tablename__ = "unified_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("unified_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True) # whatsapp | email | sms | call | internal_note
    direction: Mapped[str] = mapped_column(String(20), nullable=False) # inbound | outbound
    sender_name: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="delivered", nullable=False)
    attachments: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)
    mentions: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)

    # Voice Call Detail Relation
    call_record: Mapped[Optional["CallDetailRecord"]] = relationship("CallDetailRecord", uselist=False, back_populates="message")
    conversation: Mapped["UnifiedConversation"] = relationship("UnifiedConversation", back_populates="messages")

class CallDetailRecord(Base, TimestampMixin):
    """Voice Call recording, transcript, and AI summary record."""
    __tablename__ = "call_detail_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("unified_messages.id", ondelete="CASCADE"), nullable=False, index=True)
    recording_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    message: Mapped["UnifiedMessage"] = relationship("UnifiedMessage", back_populates="call_record")
