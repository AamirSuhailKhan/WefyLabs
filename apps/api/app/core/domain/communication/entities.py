import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

class ChannelType(str, Enum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    SMS = "sms"
    CALL = "call"
    INTERNAL_NOTE = "internal_note"

class MessageDirection(str, Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"

class MessageStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"

class SentimentScore(str, Enum):
    VERY_POSITIVE = "very_positive"
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    HIGHLY_URGENT = "highly_urgent"

@dataclass
class CallDetailRecordEntity:
    id: uuid.UUID
    recording_url: Optional[str]
    duration_seconds: int
    transcript: Optional[str]
    ai_summary: Optional[str]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class UnifiedMessageEntity:
    """Pure Domain Entity for a multi-channel message or internal team note."""
    id: uuid.UUID
    conversation_id: uuid.UUID
    lead_id: uuid.UUID
    broker_id: uuid.UUID
    channel: ChannelType
    direction: MessageDirection
    sender_name: str
    sender_identifier: str # phone / email / broker_name
    content: str
    status: MessageStatus = MessageStatus.DELIVERED
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    call_record: Optional[CallDetailRecordEntity] = None
    mentions: List[str] = field(default_factory=list) # @broker_ids
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

@dataclass
class UnifiedConversationEntity:
    """Pure Domain Entity for a Lead's Omnichannel Timeline."""
    id: uuid.UUID
    lead_id: uuid.UUID
    broker_id: uuid.UUID
    organization_id: Optional[uuid.UUID]
    assignee_id: Optional[uuid.UUID]
    unread_count: int = 0
    last_channel: ChannelType = ChannelType.WHATSAPP
    last_message_content: Optional[str] = None
    last_message_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: List[str] = field(default_factory=list)
    is_snoozed: bool = False
    snoozed_until: Optional[datetime] = None
    ai_summary: Optional[str] = None
    ai_sentiment: SentimentScore = SentimentScore.NEUTRAL
    ai_urgency_score: float = 0.0 # 0.0 to 1.0
    ai_detected_objections: List[str] = field(default_factory=list)
    ai_next_best_action: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
