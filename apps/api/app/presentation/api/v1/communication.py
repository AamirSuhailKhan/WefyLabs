import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.core.domain.communication.entities import ChannelType
from app.core.application.communication.use_cases import CommunicationUseCases, SendMessageCommand, AddInternalNoteCommand

router = APIRouter(prefix="/communication", tags=["Omnichannel Communication Hub"])

@router.get("/inbox")
async def list_inbox_conversations(
    channel: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    is_unassigned: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_broker: Broker = Depends(get_current_broker)
):
    """Mock Inbox Conversations endpoint for testing unified timeline UI."""
    return {
        "total": 3,
        "page": page,
        "limit": limit,
        "items": [
          {
            "id": "11111111-1111-1111-1111-111111111111",
            "lead_id": "22222222-2222-2222-2222-222222222222",
            "lead_name": "Rahul Sharma",
            "lead_phone": "+91 98765 43210",
            "unread_count": 2,
            "last_channel": "whatsapp",
            "last_message_content": "Looking for 3BHK ready to move in DLF Phase 5.",
            "last_message_at": "2026-07-30T15:30:00Z",
            "tags": ["Hot", "3BHK", "DLF"],
            "ai_sentiment": "highly_urgent",
            "ai_urgency_score": 0.92,
            "ai_summary": "Lead inquired for 3BHK in DLF Phase 5, budget 2.5 Cr.",
            "ai_next_best_action": "Schedule site visit for tomorrow 4 PM."
          },
          {
            "id": "33333333-3333-3333-3333-333333333333",
            "lead_id": "44444444-4444-4444-4444-444444444444",
            "lead_name": "Tariq Al-Mansoor",
            "lead_phone": "+971 50 123 4567",
            "unread_count": 0,
            "last_channel": "email",
            "last_message_content": "Please send the Golden Visa eligible villa brochure.",
            "last_message_at": "2026-07-30T14:15:00Z",
            "tags": ["UAE", "Offplan", "GoldenVisa"],
            "ai_sentiment": "positive",
            "ai_urgency_score": 0.78,
            "ai_summary": "Inquired for 2M+ AED Dubai Marina villa for Golden Visa.",
            "ai_next_best_action": "Send PDF brochure via WhatsApp."
          }
        ]
    }

@router.get("/conversations/{lead_id}/timeline")
async def get_customer_timeline(
    lead_id: uuid.UUID,
    current_broker: Broker = Depends(get_current_broker)
):
    """Returns unified omnichannel timeline (WhatsApp, Email, SMS, Calls, Internal Notes)."""
    return {
        "lead_id": str(lead_id),
        "messages": [
            {
                "id": str(uuid.uuid4()),
                "channel": "whatsapp",
                "direction": "inbound",
                "sender_name": "Rahul Sharma",
                "content": "Hi, I saw your listing for DLF Phase 5 3BHK. Is it available?",
                "status": "read",
                "created_at": "2026-07-30T15:00:00Z"
            },
            {
                "id": str(uuid.uuid4()),
                "channel": "internal_note",
                "direction": "outbound",
                "sender_name": current_broker.name or "Agent",
                "content": "@Aamir Spoke to lead on WhatsApp. High intent buyer, cash funding.",
                "mentions": ["Aamir"],
                "created_at": "2026-07-30T15:05:00Z"
            },
            {
                "id": str(uuid.uuid4()),
                "channel": "call",
                "direction": "outbound",
                "sender_name": current_broker.name or "Agent",
                "content": "Outbound Call Completed (3m 45s)",
                "call_record": {
                    "recording_url": "https://cdn.wefylabs.com/audio/sample_call.mp3",
                    "duration_seconds": 225,
                    "transcript": "Agent confirmed 3BHK availability. Buyer requested site visit tomorrow at 4 PM.",
                    "ai_summary": "Confirmed site visit for DLF Phase 5 tomorrow 4 PM."
                },
                "created_at": "2026-07-30T15:20:00Z"
            }
        ]
    }

@router.post("/send", status_code=status.HTTP_201_CREATED)
async def send_message_endpoint(
    lead_id: uuid.UUID,
    channel: str,
    content: str,
    recipient_identifier: str,
    current_broker: Broker = Depends(get_current_broker)
):
    channel_enum = ChannelType(channel.lower())
    return {
        "status": "success",
        "message_id": str(uuid.uuid4()),
        "channel": channel_enum.value,
        "recipient": recipient_identifier,
        "content": content
    }

@router.post("/ai/smart-reply")
async def generate_smart_reply_endpoint(
    lead_name: str = Query("Customer"),
    conversation_context: str = Query(""),
    current_broker: Broker = Depends(get_current_broker)
):
    suggestions = CommunicationUseCases.generate_ai_smart_reply(conversation_context, lead_name)
    return {"suggestions": suggestions}
