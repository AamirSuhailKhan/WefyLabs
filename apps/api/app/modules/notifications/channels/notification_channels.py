from abc import ABC, abstractmethod
from typing import Optional, Dict, Any


class NotificationPayload:
    def __init__(
        self,
        recipient_id: str,
        title: str,
        body: Optional[str] = None,
        channel: str = "in_app",
        category: str = "system",
        action_url: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.recipient_id = recipient_id
        self.title = title
        self.body = body
        self.channel = channel
        self.category = category
        self.action_url = action_url
        self.metadata = metadata or {}


class INotificationChannel(ABC):
    """
    Abstract base for all notification delivery channels.
    Each channel (Email, WhatsApp, In-App, Telegram, SMS) implements this interface.
    """
    channel_name: str = "base"

    @abstractmethod
    async def send(self, payload: NotificationPayload) -> bool:
        """Send a notification. Returns True on success, False on failure."""
        pass


class InAppChannelAdapter(INotificationChannel):
    """In-App notification stored in DB and served via polling/WebSocket."""
    channel_name = "in_app"

    def __init__(self, db=None):
        self.db = db

    async def send(self, payload: NotificationPayload) -> bool:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[NOTIFY: in_app] → {payload.recipient_id}: {payload.title}")
        # Actual DB write handled by NotificationService.create_in_app()
        return True


class EmailChannelAdapter(INotificationChannel):
    """Email notification dispatch via SMTP or transactional email provider."""
    channel_name = "email"

    async def send(self, payload: NotificationPayload) -> bool:
        import logging
        import uuid
        from app.modules.communication.channel_manager.manager import get_channel_manager
        from app.modules.communication.provider_adapters.base_provider import OutboundMessageDTO

        logger = logging.getLogger(__name__)
        logger.info(f"[NOTIFY: email] → {payload.recipient_id}: {payload.title}")
        
        channel_mgr = get_channel_manager()
        try:
            email_provider = channel_mgr.get_provider("email")
            if not email_provider.is_configured():
                logger.info("[NOTIFY: email] SMTP provider unconfigured, skipping external email dispatch.")
                return True

            recipient = payload.recipient_id if "@" in payload.recipient_id else (payload.metadata or {}).get("email") or f"{payload.recipient_id}@notification.local"
            outbound_dto = OutboundMessageDTO(
                message_id=str(uuid.uuid4()),
                conversation_id=payload.recipient_id,
                organization_id=(payload.metadata or {}).get("organization_id", "system"),
                channel="email",
                provider_name=email_provider.provider_name,
                recipient_identifier=recipient,
                content=payload.body or payload.title,
                message_type="text",
                content_structured={"subject": payload.title},
                idempotency_key=f"notify:email:{payload.recipient_id}:{payload.title}",
            )
            resp = await email_provider.send(outbound_dto)
            return resp.success
        except Exception as e:
            logger.error(f"[NOTIFY: email] Failed to dispatch email notification: {e}")
            return False


class WhatsAppChannelAdapter(INotificationChannel):
    """WhatsApp Cloud API notification dispatch."""
    channel_name = "whatsapp"

    async def send(self, payload: NotificationPayload) -> bool:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[NOTIFY: whatsapp] → {payload.recipient_id}: {payload.title}")
        # TODO: call WhatsApp Cloud API via whatsapp_service
        return True


class TelegramChannelAdapter(INotificationChannel):
    """Telegram Bot API notification dispatch."""
    channel_name = "telegram"

    async def send(self, payload: NotificationPayload) -> bool:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[NOTIFY: telegram] → {payload.recipient_id}: {payload.title}")
        # TODO: call Telegram Bot API
        return True


class SMSChannelAdapter(INotificationChannel):
    """SMS notification via Twilio or custom provider."""
    channel_name = "sms"

    async def send(self, payload: NotificationPayload) -> bool:
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"[NOTIFY: sms] → {payload.recipient_id}: {payload.title}")
        # TODO: integrate Twilio or local SMS gateway
        return True
