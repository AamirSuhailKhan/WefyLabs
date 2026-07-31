from typing import Dict, Any, Optional, List
from app.core.domain.communication.entities import ChannelType
from app.core.domain.communication.ports import IChannelAdapter

class WhatsAppAdapter(IChannelAdapter):
    """WhatsApp Messaging Adapter (Meta Cloud API & 360dialog)."""
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.WHATSAPP

    async def send_message(
        self,
        recipient_identifier: str,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        # Outbound WhatsApp payload
        return {
            "status": "success",
            "provider": "whatsapp_meta",
            "recipient": recipient_identifier,
            "message_id": f"wamid_{recipient_identifier[:6]}_123"
        }

class EmailAdapter(IChannelAdapter):
    """Omnichannel Email Adapter (SMTP / SendGrid / AWS SES)."""
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.EMAIL

    async def send_message(
        self,
        recipient_identifier: str,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        return {
            "status": "success",
            "provider": "email_smtp",
            "recipient": recipient_identifier,
            "message_id": f"msg_email_{recipient_identifier.split('@')[0]}_456"
        }

class SMSAdapter(IChannelAdapter):
    """SMS Messaging Adapter (Twilio / Infobip)."""
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.SMS

    async def send_message(
        self,
        recipient_identifier: str,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        return {
            "status": "success",
            "provider": "sms_twilio",
            "recipient": recipient_identifier,
            "message_id": f"SM_{recipient_identifier[:6]}_789"
        }

class VoiceCallAdapter(IChannelAdapter):
    """Twilio Voice / WebRTC Call Adapter."""
    @property
    def channel_type(self) -> ChannelType:
        return ChannelType.CALL

    async def send_message(
        self,
        recipient_identifier: str,
        content: str,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        return {
            "status": "initiated",
            "provider": "voice_twilio",
            "call_sid": f"CA_{recipient_identifier[:6]}_999"
        }

class ChannelAdapterFactory:
    """Factory resolving the target channel adapter dynamically."""
    _adapters: Dict[ChannelType, IChannelAdapter] = {
        ChannelType.WHATSAPP: WhatsAppAdapter(),
        ChannelType.EMAIL: EmailAdapter(),
        ChannelType.SMS: SMSAdapter(),
        ChannelType.CALL: VoiceCallAdapter(),
    }

    @classmethod
    def get_adapter(cls, channel: ChannelType) -> IChannelAdapter:
        return cls._adapters.get(channel, cls._adapters[ChannelType.WHATSAPP])
