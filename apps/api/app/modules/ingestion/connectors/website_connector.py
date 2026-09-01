from typing import Dict, Any
from app.modules.ingestion.connectors.base_connector import ILeadConnector
from app.modules.ingestion.dto.canonical_lead_dto import CanonicalLeadDTO


class WebsiteFormConnector(ILeadConnector):
    """Adapter for website contact forms, landing page inquiries, and web chat widgets."""
    source_name = "website"

    def validate_raw(self, payload: Dict[str, Any]) -> bool:
        phone = payload.get("phone") or payload.get("mobile") or payload.get("telephone")
        return bool(phone)

    def parse_to_canonical(self, payload: Dict[str, Any]) -> CanonicalLeadDTO:
        name = payload.get("name") or payload.get("full_name") or f"Guest {payload.get('phone', '')[-4:]}"
        phone = payload.get("phone") or payload.get("mobile") or ""
        email = payload.get("email")
        notes = [payload["message"]] if "message" in payload else []

        return CanonicalLeadDTO(
            name=name,
            email=email,
            phone=phone,
            source=payload.get("source") or "website_contact_form",
            campaign=payload.get("utm_campaign"),
            city=payload.get("city"),
            property_type=payload.get("property_type"),
            budget_min=float(payload["budget_min"]) if "budget_min" in payload else None,
            budget_max=float(payload["budget_max"]) if "budget_max" in payload else None,
            notes=notes,
            tags=["website", payload.get("form_id", "contact_form")],
            metadata={"ip": payload.get("ip"), "user_agent": payload.get("user_agent")},
        )
