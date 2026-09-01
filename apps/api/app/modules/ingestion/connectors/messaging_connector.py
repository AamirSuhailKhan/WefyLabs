from typing import Dict, Any
from app.modules.ingestion.connectors.base_connector import ILeadConnector
from app.modules.ingestion.dto.canonical_lead_dto import CanonicalLeadDTO


class MessagingConnector(ILeadConnector):
    """Adapter for WhatsApp Business, Telegram, and 360Dialog inbound webhooks."""
    source_name = "messaging"

    def validate_raw(self, payload: Dict[str, Any]) -> bool:
        phone = payload.get("from") or payload.get("phone") or payload.get("whatsapp_id")
        return bool(phone)

    def parse_to_canonical(self, payload: Dict[str, Any]) -> CanonicalLeadDTO:
        phone = payload.get("from") or payload.get("phone") or ""
        profile_name = payload.get("profile_name") or payload.get("sender_name") or f"WhatsApp {phone[-4:]}"
        text_body = payload.get("text") or payload.get("message") or ""

        return CanonicalLeadDTO(
            name=profile_name,
            phone=phone,
            whatsapp_number=phone,
            source="whatsapp_business",
            notes=[text_body] if text_body else [],
            tags=["whatsapp", "messaging"],
            metadata={"channel": payload.get("channel", "whatsapp"), "wa_id": payload.get("wa_id")},
        )
