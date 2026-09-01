"""
Volume 2 PART 2 — Enrichment Validator
"""
from typing import Dict, Any, List, Tuple


class EnrichmentValidator:
    @staticmethod
    def validate_canonical_input(lead_dto: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors = []
        if not lead_dto.get("id"):
            errors.append("Missing lead_id")
        if not lead_dto.get("organization_id") and not lead_dto.get("broker_id"):
            errors.append("Missing organization_id or broker_id")
        if not lead_dto.get("phone"):
            errors.append("Missing phone number")

        return len(errors) == 0, errors

    @staticmethod
    def validate_enriched_output(enrichment_profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
        warnings = []
        financial = enrichment_profile.get("financial_profile", {})
        location = enrichment_profile.get("location_profile", {})

        if not financial.get("amount_aed"):
            warnings.append("Missing canonical AED budget")
        if not location.get("country"):
            warnings.append("Missing location country")

        return True, warnings
