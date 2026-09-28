import re
from typing import Optional, Dict, Any, List

class DuplicateDetectionService:
    """
    Automated Lead Deduplication Service normalizing phone numbers to E.164
    and matching fuzzy emails and phone numbers across database records.
    """

    @classmethod
    def normalize_phone_e164(cls, phone: str, default_country_code: str = "+91") -> str:
        """Normalizes raw phone strings to E.164 format (+919876543210, +14155552671)."""
        if not phone:
            return ""
        from app.modules.lead_acquisition.services.normalization_service import normalize_phone
        res, _ = normalize_phone(phone, default_country_code=default_country_code)
        return res or ""

    @classmethod
    def find_duplicate_match(
        cls,
        target_phone: str,
        target_email: Optional[str],
        existing_leads: List[Dict[str, Any]],
        default_country_code: str = "+91"
    ) -> Optional[Dict[str, Any]]:
        norm_target_phone = cls.normalize_phone_e164(target_phone, default_country_code)
        norm_target_email = target_email.lower().strip() if target_email else None

        for lead in existing_leads:
            lead_phone = cls.normalize_phone_e164(lead.get("phone", ""), default_country_code)
            if lead_phone and lead_phone == norm_target_phone:
                return lead

            lead_email = (lead.get("email") or "").lower().strip()
            if norm_target_email and lead_email and norm_target_email == lead_email:
                return lead

        return None
