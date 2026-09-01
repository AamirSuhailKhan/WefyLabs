from typing import Dict, Any
from app.modules.ingestion.connectors.base_connector import ILeadConnector
from app.modules.ingestion.dto.canonical_lead_dto import CanonicalLeadDTO


class EmailParserConnector(ILeadConnector):
    """Adapter for incoming email leads (SendGrid / Mailgun / Postmark inbound webhooks)."""
    source_name = "email"

    def validate_raw(self, payload: Dict[str, Any]) -> bool:
        return bool(payload.get("from_email") or payload.get("sender"))

    def parse_to_canonical(self, payload: Dict[str, Any]) -> CanonicalLeadDTO:
        sender_email = payload.get("from_email") or payload.get("sender") or ""
        sender_name = payload.get("from_name") or sender_email.split("@")[0].title()
        phone = payload.get("phone") or payload.get("contact_phone") or "0000000000"
        subject = payload.get("subject", "")
        body = payload.get("body_plain") or payload.get("text") or ""

        return CanonicalLeadDTO(
            name=sender_name,
            email=sender_email,
            phone=phone,
            source="email_parser",
            notes=[f"Subject: {subject}", body] if body else [f"Subject: {subject}"],
            tags=["email", "inbound"],
            metadata={"subject": subject},
        )


class FileImportConnector(ILeadConnector):
    """Adapter for CSV & Excel batch row imports."""
    source_name = "file_import"

    def validate_raw(self, payload: Dict[str, Any]) -> bool:
        phone = payload.get("phone") or payload.get("mobile") or payload.get("Phone")
        name = payload.get("name") or payload.get("Name") or payload.get("Full Name")
        return bool(phone or name)

    def parse_to_canonical(self, payload: Dict[str, Any]) -> CanonicalLeadDTO:
        # Case-insensitive field resolution
        p_lower = {str(k).lower().strip(): v for k, v in payload.items()}
        name = p_lower.get("name") or p_lower.get("full name") or p_lower.get("lead name") or "Imported Lead"
        phone = p_lower.get("phone") or p_lower.get("mobile") or p_lower.get("telephone") or "0000000000"
        email = p_lower.get("email") or p_lower.get("email address")

        return CanonicalLeadDTO(
            name=str(name),
            email=str(email) if email else None,
            phone=str(phone),
            source=p_lower.get("source") or "csv_import",
            city=p_lower.get("city"),
            property_type=p_lower.get("property_type") or p_lower.get("type"),
            tags=["csv_import", "batch"],
            metadata={"raw_row": payload},
        )


class RestWebhookConnector(ILeadConnector):
    """Adapter for Meta Lead Ads, Google Lead Forms, Zapier, and generic REST Webhooks."""
    source_name = "webhook"

    def validate_raw(self, payload: Dict[str, Any]) -> bool:
        return bool(payload)

    def parse_to_canonical(self, payload: Dict[str, Any]) -> CanonicalLeadDTO:
        p_lower = {str(k).lower().strip(): v for k, v in payload.items()}
        name = p_lower.get("name") or p_lower.get("full_name") or p_lower.get("first_name") or "Webhook Lead"
        phone = p_lower.get("phone") or p_lower.get("phone_number") or p_lower.get("mobile") or "0000000000"
        email = p_lower.get("email") or p_lower.get("email_address")

        return CanonicalLeadDTO(
            name=str(name),
            email=str(email) if email else None,
            phone=str(phone),
            source=p_lower.get("source") or "rest_webhook",
            campaign=p_lower.get("campaign") or p_lower.get("ad_name"),
            tags=["webhook", p_lower.get("source", "generic")],
            metadata=payload,
        )
