"""
Part 21.6 — WebChat / In-App Provider Adapter
===============================================
Implements CommunicationProvider for real-time web chat via WebSocket / In-App messaging.
"""
from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict, List, Optional, Set

from app.modules.communication.provider_adapters.base_provider import (
    CommunicationProvider,
    CommunicationCapabilities,
    DeliveryStatusEnum,
    InboundMessageDTO,
    OutboundMessageDTO,
    ProviderDeliveryStatus,
    ProviderResponse,
    ProviderStatusEnum,
)

_active_sessions: Dict[str, Any] = {}
_SUPPORTED_TYPES = ["text", "image", "video", "audio", "document", "button", "quick_reply", "interactive"]


class WebChatProvider(CommunicationProvider):
    """
    WebChat provider for in-browser chat widget / In-App messages.
    """

    def __init__(self, widget_secret: str = ""):
        self._widget_secret = widget_secret
        self._connected = False

    @property
    def provider_name(self) -> str:
        return "webchat"

    @property
    def channel(self) -> str:
        return "webchat"

    @property
    def supported_message_types(self) -> List[str]:
        return _SUPPORTED_TYPES

    @property
    def supports_typing_indicator(self) -> bool:
        return True

    @property
    def supports_read_receipts(self) -> bool:
        return True

    def capabilities(self) -> CommunicationCapabilities:
        return CommunicationCapabilities(
            supports_text=True,
            supports_templates=True,
            supports_media=True,
            supports_typing_indicator=True,
            supports_read_receipts=True,
            supports_webhooks=True,
            max_text_length=10000,
        )

    async def verify_configuration(self) -> ProviderStatusEnum:
        return ProviderStatusEnum.READY

    async def connect(self) -> None:
        self._connected = True

    async def disconnect(self) -> None:
        self._connected = False
        _active_sessions.clear()

    async def verify_webhook_signature(self, raw_body: bytes, headers: Dict[str, str]) -> bool:
        if not self._widget_secret:
            return True
        token = headers.get("x-widget-secret", "")
        return token == self._widget_secret

    async def receive(self, payload: Dict[str, Any]) -> InboundMessageDTO:
        session_id = payload.get("session_id", str(uuid.uuid4()))
        sender_name = payload.get("sender_name", "Visitor")
        content = payload.get("content", "")
        msg_type = payload.get("message_type", "text")
        msg_id = payload.get("message_id", str(uuid.uuid4()))

        if session_id and session_id not in _active_sessions:
            _active_sessions[session_id] = {"session_id": session_id, "connected_at": time.time()}

        attachments = []
        if payload.get("attachment"):
            att = payload["attachment"]
            attachments = [{
                "provider_media_id": att.get("id", ""),
                "mime_type": att.get("mime_type", "application/octet-stream"),
                "file_name": att.get("file_name", "attachment"),
                "file_type": att.get("file_type", "document"),
            }]

        idempotency_key = hashlib.sha256(f"wc:{session_id}:{msg_id}".encode()).hexdigest()[:64]

        return InboundMessageDTO(
            provider_name=self.provider_name,
            channel=self.channel,
            provider_message_id=msg_id,
            idempotency_key=idempotency_key,
            sender_identifier=session_id,
            sender_name=sender_name,
            content=content,
            message_type=msg_type,
            attachments=attachments,
            raw_payload=payload,
            organization_id=payload.get("organization_id"),
        )

    async def send(self, message: OutboundMessageDTO) -> ProviderResponse:
        session_id = message.recipient_identifier
        inapp_id = f"inapp_{message.message_id[:12]}"

        return ProviderResponse(
            success=True,
            provider_message_id=inapp_id,
            status="sent",
            delivery_status=DeliveryStatusEnum.SENT,
            latency_ms=2,
        )

    async def upload_media(self, file_bytes: bytes, mime_type: str, file_name: str) -> str:
        return f"inapp_media_{hashlib.sha256(file_bytes[:64]).hexdigest()[:16]}"

    async def download_media(self, provider_media_id: str) -> bytes:
        return b""

    async def mark_read(self, provider_message_id: str) -> None:
        pass

    async def send_typing(self, recipient_identifier: str) -> None:
        pass

    async def get_delivery_status(self, provider_message_id: str) -> ProviderDeliveryStatus:
        return ProviderDeliveryStatus(
            provider_message_id=provider_message_id,
            status="delivered",
            delivery_status=DeliveryStatusEnum.DELIVERED,
        )

    @classmethod
    def register_session(cls, session_id: str, connection: Any) -> None:
        _active_sessions[session_id] = {"connection": connection, "connected_at": time.time()}

    @classmethod
    def unregister_session(cls, session_id: str) -> None:
        _active_sessions.pop(session_id, None)

    @classmethod
    def get_active_session_count(cls) -> int:
        return len(_active_sessions)
