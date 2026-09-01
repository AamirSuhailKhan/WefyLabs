"""
Volume 2 PART 2 — Phone Normalizer & Country Inferral
"""
import re
from typing import Dict, Any, Optional

# Country dial code mappings
DIAL_CODE_MAP = {
    "971": {"country": "United Arab Emirates", "iso2": "AE", "iso3": "ARE", "timezone": "Asia/Dubai"},
    "1": {"country": "United States", "iso2": "US", "iso3": "USA", "timezone": "America/New_York"},
    "44": {"country": "United Kingdom", "iso2": "GB", "iso3": "GBR", "timezone": "Europe/London"},
    "91": {"country": "India", "iso2": "IN", "iso3": "IND", "timezone": "Asia/Kolkata"},
    "966": {"country": "Saudi Arabia", "iso2": "SA", "iso3": "SAU", "timezone": "Asia/Riyadh"},
    "974": {"country": "Qatar", "iso2": "QA", "iso3": "QAT", "timezone": "Asia/Qatar"},
    "965": {"country": "Kuwait", "iso2": "KW", "iso3": "KWT", "timezone": "Asia/Kuwait"},
    "968": {"country": "Oman", "iso2": "OM", "iso3": "OMN", "timezone": "Asia/Muscat"},
    "973": {"country": "Bahrain", "iso2": "BH", "iso3": "BHR", "timezone": "Asia/Bahrain"},
    "20": {"country": "Egypt", "iso2": "EG", "iso3": "EGY", "timezone": "Africa/Cairo"},
    "33": {"country": "France", "iso2": "FR", "iso3": "FRA", "timezone": "Europe/Paris"},
    "49": {"country": "Germany", "iso2": "DE", "iso3": "DEU", "timezone": "Europe/Berlin"},
    "7": {"country": "Russia", "iso2": "RU", "iso3": "RUS", "timezone": "Europe/Moscow"},
    "86": {"country": "China", "iso2": "CN", "iso3": "CHN", "timezone": "Asia/Shanghai"},
    "92": {"country": "Pakistan", "iso2": "PK", "iso3": "PAK", "timezone": "Asia/Karachi"},
}


class PhoneNormalizer:
    @staticmethod
    def normalize(phone_raw: Optional[str]) -> Dict[str, Any]:
        if not phone_raw:
            return {
                "e164": None,
                "country": None,
                "iso2": None,
                "iso3": None,
                "dial_code": None,
                "timezone": None,
                "is_valid": False,
                "confidence": 0.0
            }

        # Strip all non-digits except leading +
        cleaned = re.sub(r"[^\d+]", "", phone_raw.strip())
        if cleaned.startswith("+"):
            digits = cleaned[1:]
        elif cleaned.startswith("00"):
            digits = cleaned[2:]
        else:
            digits = cleaned

        if not digits or len(digits) < 7 or len(digits) > 15:
            return {
                "e164": phone_raw,
                "country": None,
                "iso2": None,
                "iso3": None,
                "dial_code": None,
                "timezone": None,
                "is_valid": False,
                "confidence": 0.2
            }

        # Match longest prefix dial code
        matched_country = None
        matched_code = None
        for code_len in [3, 2, 1]:
            prefix = digits[:code_len]
            if prefix in DIAL_CODE_MAP:
                matched_country = DIAL_CODE_MAP[prefix]
                matched_code = prefix
                break

        e164 = f"+{digits}"
        if matched_country:
            return {
                "e164": e164,
                "country": matched_country["country"],
                "iso2": matched_country["iso2"],
                "iso3": matched_country["iso3"],
                "dial_code": f"+{matched_code}",
                "timezone": matched_country["timezone"],
                "is_valid": True,
                "confidence": 0.95
            }

        return {
            "e164": e164,
            "country": None,
            "iso2": None,
            "iso3": None,
            "dial_code": None,
            "timezone": None,
            "is_valid": True,
            "confidence": 0.6
        }
