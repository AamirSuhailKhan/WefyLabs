"""
Volume 2 PART 2 — Rule Extractor (Deterministic Business Rules)
"""
from typing import Dict, Any
from app.modules.enrichment.extractors.base_extractor import BaseExtractor
from app.modules.enrichment.normalizers.phone_normalizer import PhoneNormalizer

DEFAULT_COUNTRY_LANGUAGES = {
    "United Arab Emirates": "Arabic",
    "Saudi Arabia": "Arabic",
    "Qatar": "Arabic",
    "Kuwait": "Arabic",
    "Egypt": "Arabic",
    "United Kingdom": "English",
    "United States": "English",
    "India": "English",
    "France": "French",
    "Germany": "German",
    "Russia": "Russian",
    "China": "Chinese",
}


class RuleExtractor(BaseExtractor):
    def extract(self, text_content: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        extracted = {}

        phone = metadata.get("phone")
        country = metadata.get("country")
        language = metadata.get("language")
        timezone = metadata.get("timezone")

        # Rule 1: Infer country from phone if missing
        if not country and phone:
            phone_norm = PhoneNormalizer.normalize(phone)
            if phone_norm["country"]:
                extracted["country"] = phone_norm["country"]
                extracted["country_iso2"] = phone_norm["iso2"]
                extracted["country_confidence"] = 0.95
                if not timezone and phone_norm["timezone"]:
                    extracted["timezone"] = phone_norm["timezone"]
                    extracted["timezone_confidence"] = 0.95

        # Rule 2: Infer language from country if missing
        target_country = country or extracted.get("country")
        if not language and target_country:
            inferred_lang = DEFAULT_COUNTRY_LANGUAGES.get(target_country)
            if inferred_lang:
                extracted["language"] = inferred_lang
                extracted["language_confidence"] = 0.70

        # Rule 3: Infer currency (Default to AED if UAE / +971)
        if target_country == "United Arab Emirates" or (phone and str(phone).startswith("+971")):
            extracted["default_currency"] = "AED"
            extracted["currency_confidence"] = 0.99

        return extracted
