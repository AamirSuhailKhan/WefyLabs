import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer, Text, Boolean, Float, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")


# ─── Legacy Models (preserved for backward compatibility) ─────────────────────

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


# ═══════════════════════════════════════════════════════════════════════════════
# PART 6 — Enterprise Omnichannel Communication Engine Models
# ═══════════════════════════════════════════════════════════════════════════════

def _gen_uuid() -> str:
    return str(uuid.uuid4())


# ─── 1. OmnichannelConversation ───────────────────────────────────────────────

class OmnichannelConversation(Base):
    """
    The central unified conversation record for one customer, independent of
    which channel they used. One customer → one OmnichannelConversation.

    All channels (WhatsApp, Email, Telegram, WebChat) reference this via
    ConversationChannelLink. The AI Agent and human inbox both operate on this.
    """
    __tablename__ = "omnichannel_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Control: who is currently handling this conversation
    # ai | human | bot | paused
    control_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="ai", index=True)
    assigned_agent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Primary channel for outbound when not specified
    preferred_channel: Mapped[str] = mapped_column(String(30), nullable=False, default="whatsapp")

    # Aggregate stats
    total_messages: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unread_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_channel: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    last_message_preview: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # AI Intelligence
    ai_sentiment: Mapped[str] = mapped_column(String(30), nullable=False, default="neutral")
    ai_urgency_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ai_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ai_next_best_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    # active | resolved | archived | snoozed

    tags: Mapped[Optional[dict]] = mapped_column(JSONBType, default=list, nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONBType, default=dict, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    channel_links: Mapped[List["ConversationChannelLink"]] = relationship(
        "ConversationChannelLink", back_populates="conversation", cascade="all, delete-orphan"
    )
    messages: Mapped[List["ChannelMessage"]] = relationship(
        "ChannelMessage", back_populates="conversation", cascade="all, delete-orphan"
    )
    control: Mapped[Optional["ConversationControl"]] = relationship(
        "ConversationControl", back_populates="conversation", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_omni_conv_org_lead", "organization_id", "lead_id"),
        Index("ix_omni_conv_org_status", "organization_id", "status"),
        Index("ix_omni_conv_org_mode", "organization_id", "control_mode"),
    )


# ─── 2. ConversationChannelLink ───────────────────────────────────────────────

class ConversationChannelLink(Base):
    """
    Maps a specific channel identity (e.g., WhatsApp +91-98765, Email user@x.com)
    to an OmnichannelConversation. Enables cross-channel unification.

    One OmnichannelConversation → Many ConversationChannelLinks.
    """
    __tablename__ = "conversation_channel_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("omnichannel_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Channel identity
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # whatsapp | telegram | email | webchat | sms | instagram | messenger | voice

    channel_identifier: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    # e.g. phone number for WhatsApp, email for Email, chat_id for Telegram

    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    # meta_cloud | telegram | smtp | webchat | twilio

    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    conversation: Mapped["OmnichannelConversation"] = relationship(
        "OmnichannelConversation", back_populates="channel_links"
    )

    __table_args__ = (
        # One channel identity maps to exactly one conversation per org
        UniqueConstraint("organization_id", "channel", "channel_identifier",
                         name="uq_channel_link_org_channel_id"),
        Index("ix_channel_link_conv", "conversation_id"),
    )


# ─── 3. ConversationControl ───────────────────────────────────────────────────

class ConversationControl(Base):
    """
    Real-time control record for a conversation: who owns it right now?
    AI Agent checks this BEFORE processing any message.

    control_mode = 'ai'     → AI Agent processes
    control_mode = 'human'  → AI Agent pauses, human inbox takes over
    control_mode = 'paused' → Nobody processes (snoozed)
    """
    __tablename__ = "conversation_controls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("omnichannel_conversations.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    control_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="ai")
    # ai | human | paused | bot

    assigned_agent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    assigned_agent_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Human takeover context
    takeover_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    takeover_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    takeover_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # AI resume context
    resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resumed_by: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # AI briefing for human takeover
    ai_briefing: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    conversation: Mapped["OmnichannelConversation"] = relationship(
        "OmnichannelConversation", back_populates="control"
    )


# ─── 4. ChannelMessage ────────────────────────────────────────────────────────

class ChannelMessage(Base):
    """
    Normalized message across all channels. Every inbound and outbound message
    is stored here after normalization — channel-agnostic unified timeline.

    The channel field records the source: 'whatsapp', 'email', 'telegram', etc.
    """
    __tablename__ = "channel_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("omnichannel_conversations.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # Channel metadata
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, default="unknown")
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)

    # Message direction
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    # inbound | outbound

    # Message type
    message_type: Mapped[str] = mapped_column(String(30), nullable=False, default="text")
    # text | image | video | audio | voice_note | document | location | contact
    # button | list | template | quick_reply | interactive | sticker

    # Content
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    content_structured: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    # For rich messages: buttons, list items, template params

    # Sender/Recipient
    sender_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    sender_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    sender_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    # phone / email / telegram_id / session_id

    recipient_identifier: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # AI / Agent context
    sent_by_ai: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_by_agent_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Template used
    template_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    # Idempotency
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)

    # Current delivery status (denormalized for fast query)
    delivery_status: Mapped[str] = mapped_column(String(30), nullable=False, default="sent")
    # queued | sent | delivered | read | failed | expired

    # Timestamps
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    conversation: Mapped["OmnichannelConversation"] = relationship(
        "OmnichannelConversation", back_populates="messages"
    )
    attachments: Mapped[List["MessageAttachment"]] = relationship(
        "MessageAttachment", back_populates="message", cascade="all, delete-orphan"
    )
    delivery_records: Mapped[List["DeliveryStatusRecord"]] = relationship(
        "DeliveryStatusRecord", back_populates="message", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_channel_msg_conv_created", "conversation_id", "created_at"),
        Index("ix_channel_msg_org_channel", "organization_id", "channel"),
        Index("ix_channel_msg_provider_id", "provider_message_id"),
    )


# ─── 5. MessageAttachment ─────────────────────────────────────────────────────

class MessageAttachment(Base):
    """
    Attachment metadata for any message. File is stored via storage abstraction
    (local / S3-compatible); only the reference URL is stored here.
    """
    __tablename__ = "message_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("channel_messages.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    # File metadata
    file_name: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    file_type: Mapped[str] = mapped_column(String(30), nullable=False, default="document")
    # image | video | audio | voice_note | document | pdf | floor_plan | brochure | zip

    # Storage reference
    storage_provider: Mapped[str] = mapped_column(String(30), nullable=False, default="mock")
    # mock | s3 | r2 | local
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    public_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Provider-side media ID (for WhatsApp re-download etc.)
    provider_media_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Security
    is_virus_scanned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_safe: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    message: Mapped["ChannelMessage"] = relationship("ChannelMessage", back_populates="attachments")


# ─── 6. DeliveryStatusRecord ──────────────────────────────────────────────────

class DeliveryStatusRecord(Base):
    """
    Immutable delivery status event log for every outbound message.
    Each status transition creates a new record (full audit trail).

    State machine: queued → sent → delivered → read | failed | expired | retry
    """
    __tablename__ = "delivery_status_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("channel_messages.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # queued | sent | delivered | read | failed | expired | retry

    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    provider_message_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_timestamp: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Error info
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Retry tracking
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Latency (milliseconds from send to this status)
    latency_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    message: Mapped["ChannelMessage"] = relationship("ChannelMessage", back_populates="delivery_records")

    __table_args__ = (
        Index("ix_delivery_status_msg", "message_id", "status"),
        Index("ix_delivery_status_org", "organization_id", "status"),
    )


# ─── 7. MessageTemplate ───────────────────────────────────────────────────────

class MessageTemplate(Base):
    """
    Versioned message templates for WhatsApp Business, Email, and SMS.
    WhatsApp templates require Meta approval before use.
    Templates support variable injection, localization, and A/B testing.
    """
    __tablename__ = "message_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Channel this template is for
    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # whatsapp | email | sms | telegram

    # Template category (WhatsApp-specific)
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="MARKETING")
    # MARKETING | UTILITY | AUTHENTICATION

    # Language / Localization
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")

    # Content
    body: Mapped[str] = mapped_column(Text, nullable=False)
    header: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    footer: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    buttons: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)

    # Versioning
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Approval status (WhatsApp requires approval)
    approval_status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    # draft | pending | approved | rejected

    provider_template_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # A/B testing
    ab_test_group: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)

    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    variables: Mapped[List["TemplateVariable"]] = relationship(
        "TemplateVariable", back_populates="template", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "name", "language", "version",
                         name="uq_template_org_name_lang_ver"),
        Index("ix_template_org_channel", "organization_id", "channel"),
    )


# ─── 8. TemplateVariable ─────────────────────────────────────────────────────

class TemplateVariable(Base):
    """
    Variable definition for a message template.
    Example: {{1}} → customer_name, {{2}} → property_name
    """
    __tablename__ = "template_variables"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    template_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("message_templates.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)  # {{position}}
    variable_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # e.g. "customer_name", "property_name", "agent_phone"
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="lead")
    # lead | property | agent | static | custom
    source_field: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    template: Mapped["MessageTemplate"] = relationship("MessageTemplate", back_populates="variables")


# ─── 9. ProviderCredential ────────────────────────────────────────────────────

class ProviderCredential(Base):
    """
    Per-organization provider configuration and credentials.
    Credentials are encrypted at rest (symmetric encryption via crypto_service).
    Never store plaintext API keys.
    """
    __tablename__ = "provider_credentials"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    provider_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # meta_cloud | telegram | smtp | webchat | twilio | messagebird | vonage

    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # whatsapp | telegram | email | sms | webchat

    # Encrypted credential blob (JSON, encrypted with org-specific key)
    credentials_encrypted: Mapped[str] = mapped_column(Text, nullable=False)

    # Non-sensitive config (not encrypted)
    config: Mapped[Optional[dict]] = mapped_column(JSONBType, nullable=True)
    # e.g. {"phone_number_id": "...", "business_account_id": "..."}

    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "provider_name", "channel",
                         name="uq_provider_cred_org_provider_channel"),
    )


# ─── 10. OutboundQueue ────────────────────────────────────────────────────────

class OutboundQueue(Base):
    """
    DB-persisted outbound message queue. Survives server restarts.
    Workers poll this table and process pending items.

    State machine: pending → processing → sent | failed → retry → dead_letter
    """
    __tablename__ = "outbound_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("channel_messages.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", index=True)
    # pending | processing | sent | failed | retry | dead_letter

    # Provider routing
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    recipient_identifier: Mapped[str] = mapped_column(String(255), nullable=False)

    # Payload for provider
    payload: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)

    # Retry management
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    next_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    # Priority (lower = higher priority)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=5, index=True)

    # Idempotency
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_outbound_queue_pending", "status", "next_attempt_at"),
        Index("ix_outbound_queue_org_status", "organization_id", "status"),
    )


# ─── 11. InboundQueue ─────────────────────────────────────────────────────────

class InboundQueue(Base):
    """
    DB-persisted inbound message queue for replay protection and ordering.
    Webhooks write here first; workers process from queue.

    Idempotency key prevents duplicate webhook processing.
    """
    __tablename__ = "inbound_queue"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Unique key to prevent duplicate webhook replay
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)

    channel: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    provider_name: Mapped[str] = mapped_column(String(50), nullable=False)

    # Raw webhook payload (before normalization)
    raw_payload: Mapped[dict] = mapped_column(JSONBType, nullable=False, default=dict)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    # pending | processing | processed | failed

    processed_message_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_inbound_queue_pending", "status", "received_at"),
    )


# ─── 12. TypingEvent ──────────────────────────────────────────────────────────

class TypingEvent(Base):
    """
    Ephemeral typing/recording indicator events.
    Short-lived records; expired events are purged by a background job.
    """
    __tablename__ = "typing_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    conversation_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    actor_id: Mapped[str] = mapped_column(String(36), nullable=False)
    # Could be lead_id (customer typing) or agent_id (agent typing)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False, default="agent")
    # agent | ai | customer

    event_type: Mapped[str] = mapped_column(String(20), nullable=False, default="typing")
    # typing | recording | stopped

    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


# ─── 13. PresenceRecord ───────────────────────────────────────────────────────

class PresenceRecord(Base):
    """
    Online/offline presence for agents and leads per channel.
    Updated via heartbeat; stale records imply offline.
    """
    __tablename__ = "presence_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # agent | customer

    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="offline")
    # online | away | offline | busy

    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        UniqueConstraint("organization_id", "entity_id", "entity_type", "channel",
                         name="uq_presence_org_entity_channel"),
        Index("ix_presence_org_status", "organization_id", "status"),
    )
