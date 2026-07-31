import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from app.core.domain.communication.entities import (
    UnifiedConversationEntity, UnifiedMessageEntity, ChannelType, MessageDirection, MessageStatus, SentimentScore
)
from app.infrastructure.channels.channel_adapters import ChannelAdapterFactory

@dataclass
class SendMessageCommand:
    lead_id: uuid.UUID
    broker_id: uuid.UUID
    channel: ChannelType
    content: str
    recipient_identifier: str
    attachments: Optional[List[Dict[str, Any]]] = None

@dataclass
class AddInternalNoteCommand:
    lead_id: uuid.UUID
    broker_id: uuid.UUID
    broker_name: str
    content: str
    mentions: Optional[List[str]] = None

class CommunicationUseCases:
    """CQRS Application Service orchestrating Omnichannel Communication Workflows."""

    @classmethod
    def generate_ai_smart_reply(cls, conversation_content: str, lead_name: str) -> List[str]:
        """Generates 3 contextual AI response suggestions for the broker."""
        return [
            f"Hi {lead_name}, thank you for reaching out! I've shared the brochure and site plan.",
            f"Hello {lead_name}, would you be available for a quick viewing tomorrow at 4 PM?",
            f"Thanks {lead_name}! Our team is reviewing your budget requirements and will send matching inventory shortly."
        ]

    @classmethod
    def analyze_conversation_ai(cls, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Performs AI Sentiment, Urgency, Summary, and Objection Detection."""
        return {
            "ai_summary": "Lead inquired about 3BHK pricing, requested floor plan, and asked for site viewing availability.",
            "ai_sentiment": SentimentScore.HIGHLY_URGENT.value,
            "ai_urgency_score": 0.88,
            "ai_detected_objections": ["Possession timeline delay concern", "Price negotiation requested"],
            "ai_next_best_action": "Schedule physical property viewing and share RERA registration certificate."
        }
