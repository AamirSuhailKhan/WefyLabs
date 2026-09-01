"""
Part 6 — Omnichannel Communication Engine: Domain Events
=========================================================
11 Pydantic DTOs published to the EventBus on significant communication events.
All subscribers (AI Agent, Timeline, Workflow Engine) listen to these.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


class MessageReceived(BaseModel):
    """Published when an inbound message arrives from any channel."""
    event_type: str = "message_received"
    conversation_id: str
    message_id: str
    organization_id: str
    lead_id: str
    channel: str
    provider_name: str
    direction: str = "inbound"
    content: str
    message_type: str = "text"
    sender_identifier: str
    sender_name: str
    has_attachments: bool = False
    idempotency_key: str
    received_at: datetime = Field(default_factory=_now)


class MessageSent(BaseModel):
    """Published when an outbound message is enqueued for delivery."""
    event_type: str = "message_sent"
    conversation_id: str
    message_id: str
    organization_id: str
    lead_id: str
    channel: str
    provider_name: str
    direction: str = "outbound"
    content: str
    sent_by_ai: bool = False
    sent_by_agent_id: Optional[str] = None
    recipient_identifier: str
    sent_at: datetime = Field(default_factory=_now)


class MessageDelivered(BaseModel):
    """Published when provider confirms message delivery."""
    event_type: str = "message_delivered"
    message_id: str
    conversation_id: str
    organization_id: str
    provider_message_id: str
    channel: str
    delivered_at: datetime = Field(default_factory=_now)
    latency_ms: Optional[int] = None


class MessageRead(BaseModel):
    """Published when recipient marks message as read."""
    event_type: str = "message_read"
    message_id: str
    conversation_id: str
    organization_id: str
    channel: str
    read_at: datetime = Field(default_factory=_now)


class MessageFailed(BaseModel):
    """Published when message delivery fails after all retries."""
    event_type: str = "message_failed"
    message_id: str
    conversation_id: str
    organization_id: str
    channel: str
    provider_name: str
    error_code: Optional[str] = None
    error_message: str
    retry_count: int
    failed_at: datetime = Field(default_factory=_now)


class ConversationAssigned(BaseModel):
    """Published when a conversation is assigned to a human agent."""
    event_type: str = "conversation_assigned"
    conversation_id: str
    organization_id: str
    lead_id: str
    assigned_agent_id: str
    assigned_agent_name: Optional[str] = None
    assigned_at: datetime = Field(default_factory=_now)
    reason: Optional[str] = None


class AITakeoverEvent(BaseModel):
    """Published when AI resumes control of a conversation from human."""
    event_type: str = "ai_takeover"
    conversation_id: str
    organization_id: str
    lead_id: str
    resumed_by: Optional[str] = None
    resumed_at: datetime = Field(default_factory=_now)
    previous_control_mode: str = "human"


class HumanTakeoverEvent(BaseModel):
    """Published when a human agent takes over from AI."""
    event_type: str = "human_takeover"
    conversation_id: str
    organization_id: str
    lead_id: str
    takeover_by: str
    takeover_reason: Optional[str] = None
    ai_briefing: Optional[str] = None
    takeover_at: datetime = Field(default_factory=_now)


class AttachmentUploaded(BaseModel):
    """Published when a media attachment is uploaded and stored."""
    event_type: str = "attachment_uploaded"
    attachment_id: str
    message_id: str
    conversation_id: str
    organization_id: str
    file_name: str
    file_type: str
    mime_type: str
    file_size_bytes: int
    public_url: Optional[str] = None
    uploaded_at: datetime = Field(default_factory=_now)


class TemplateUsed(BaseModel):
    """Published when a message template is used to send a message."""
    event_type: str = "template_used"
    template_id: str
    template_name: str
    message_id: str
    conversation_id: str
    organization_id: str
    channel: str
    language: str
    used_at: datetime = Field(default_factory=_now)


class DeliveryRetried(BaseModel):
    """Published when a failed message delivery is retried."""
    event_type: str = "delivery_retried"
    message_id: str
    queue_id: str
    conversation_id: str
    organization_id: str
    channel: str
    provider_name: str
    retry_count: int
    next_attempt_at: Optional[datetime] = None
    retried_at: datetime = Field(default_factory=_now)


# All event types for subscriber registration
COMM_EVENT_TYPES = [
    "message_received", "message_sent", "message_delivered", "message_read",
    "message_failed", "conversation_assigned", "ai_takeover", "human_takeover",
    "attachment_uploaded", "template_used", "delivery_retried",
]
