"""
Channel Gateway — normalises inbound messages from all communication channels
into a uniform IncomingMessage DTO.

Supported channels:
  web          → Direct REST POST (already in IncomingMessage format)
  whatsapp     → WhatsApp Business API webhook payload
  telegram     → Telegram Bot API Update payload
  email        → Parsed email body + sender metadata
  messenger    → Facebook Messenger webhook entry
  voice        → Future: STT transcript with call metadata
  sms          → Future: raw SMS body

Every channel adapter:
  1. Parses the raw channel payload
  2. Identifies lead_id from phone/email via Identity Resolution
  3. Returns a normalized IncomingMessage
  4. Returns an OutgoingChannelMessage helper for the response

The same ConversationManager engine handles ALL channels.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
import logging

logger = logging.getLogger("beetlelabs.ai_agent.channel_gateway")


# ─── Raw Channel Payloads (typed) ─────────────────────────────────────────────

@dataclass
class WhatsAppInboundPayload:
    from_number: str          # E.164 format: +971501234567
    message_body: str
    message_id: str
    timestamp: str
    wa_id: str               # WhatsApp Business Account ID
    organization_id: str


@dataclass
class TelegramInboundPayload:
    chat_id: int
    username: Optional[str]
    first_name: Optional[str]
    text: str
    message_id: int
    organization_id: str


@dataclass
class EmailInboundPayload:
    from_email: str
    from_name: Optional[str]
    subject: str
    body: str
    thread_id: Optional[str]
    organization_id: str


@dataclass
class WebChatInboundPayload:
    session_token: str
    content: str
    lead_id: Optional[str]
    organization_id: str
    metadata: Optional[Dict[str, Any]] = None


# ─── Channel Adapters ──────────────────────────────────────────────────────────

class WhatsAppChannelAdapter:
    """Converts WhatsApp Business webhook payload → IncomingMessage."""

    async def parse(
        self,
        payload: WhatsAppInboundPayload,
        lead_id: Optional[str] = None,
    ):
        from app.modules.ai_agent.conversation_manager.manager import IncomingMessage
        # If lead_id is unknown, Identity Resolution should resolve phone → lead
        resolved_lead_id = lead_id or f"whatsapp_{payload.from_number.replace('+', '')}"
        return IncomingMessage(
            lead_id=resolved_lead_id,
            organization_id=payload.organization_id,
            channel="whatsapp",
            content=payload.message_body,
            sender_phone=payload.from_number,
            metadata={
                "wa_message_id": payload.message_id,
                "wa_timestamp": payload.timestamp,
                "wa_id": payload.wa_id,
            },
        )

    def format_response(self, content: str, to_number: str) -> Dict[str, Any]:
        """Format agent response as WhatsApp message payload."""
        return {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": content},
        }


class TelegramChannelAdapter:
    """Converts Telegram Bot Update → IncomingMessage."""

    async def parse(
        self,
        payload: TelegramInboundPayload,
        lead_id: Optional[str] = None,
    ):
        from app.modules.ai_agent.conversation_manager.manager import IncomingMessage
        resolved_lead_id = lead_id or f"telegram_{payload.chat_id}"
        sender_name = None
        if payload.first_name or payload.username:
            sender_name = payload.first_name or payload.username
        return IncomingMessage(
            lead_id=resolved_lead_id,
            organization_id=payload.organization_id,
            channel="telegram",
            content=payload.text,
            sender_name=sender_name,
            metadata={
                "telegram_chat_id": payload.chat_id,
                "telegram_message_id": payload.message_id,
            },
        )

    def format_response(self, content: str, chat_id: int) -> Dict[str, Any]:
        return {"chat_id": chat_id, "text": content, "parse_mode": "Markdown"}


class EmailChannelAdapter:
    """Converts email payload → IncomingMessage."""

    async def parse(
        self,
        payload: EmailInboundPayload,
        lead_id: Optional[str] = None,
    ):
        from app.modules.ai_agent.conversation_manager.manager import IncomingMessage
        resolved_lead_id = lead_id or f"email_{payload.from_email.replace('@', '_at_')}"
        return IncomingMessage(
            lead_id=resolved_lead_id,
            organization_id=payload.organization_id,
            channel="email",
            content=payload.body,
            sender_name=payload.from_name,
            metadata={
                "email_from": payload.from_email,
                "email_subject": payload.subject,
                "email_thread_id": payload.thread_id,
            },
        )

    def format_response(self, content: str, to_email: str, subject: str = "Re: Your Property Enquiry") -> Dict[str, Any]:
        return {"to": to_email, "subject": subject, "body": content}


class WebChatChannelAdapter:
    """Converts web chat POST → IncomingMessage (direct passthrough)."""

    async def parse(
        self,
        payload: WebChatInboundPayload,
        lead_id: Optional[str] = None,
    ):
        from app.modules.ai_agent.conversation_manager.manager import IncomingMessage
        resolved_lead_id = lead_id or payload.lead_id or f"webchat_{payload.session_token[:16]}"
        return IncomingMessage(
            lead_id=resolved_lead_id,
            organization_id=payload.organization_id,
            channel="web",
            content=payload.content,
            metadata=payload.metadata,
        )


# ─── Channel Gateway ──────────────────────────────────────────────────────────

class ChannelGateway:
    """
    Entry point for all inbound channel messages.
    Routes channel-specific payloads to the appropriate adapter,
    then passes the normalized IncomingMessage to ConversationManager.
    """

    def __init__(self):
        self.whatsapp = WhatsAppChannelAdapter()
        self.telegram = TelegramChannelAdapter()
        self.email = EmailChannelAdapter()
        self.web = WebChatChannelAdapter()

    def get_adapter(self, channel: str):
        adapters = {
            "whatsapp": self.whatsapp,
            "telegram": self.telegram,
            "email": self.email,
            "web": self.web,
        }
        adapter = adapters.get(channel)
        if not adapter:
            raise ValueError(f"Unsupported channel: {channel}. Supported: {list(adapters.keys())}")
        return adapter

    def get_channel_max_length(self, channel: str) -> int:
        """Return max response character length for channel."""
        return {
            "whatsapp": 1000,
            "telegram": 4096,
            "email": 8000,
            "web": 3000,
        }.get(channel, 1500)
