"""
PhoneService — Production-Grade Phone Number Engine
====================================================
Handles E.164 normalization, country extraction, masking,
validation, and type detection.

Uses the phonenumbers library for authoritative international
phone number parsing. Never relies on naive string parsing alone.

Install: pip install phonenumbers
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

try:
    import phonenumbers
    from phonenumbers import (
        PhoneNumberFormat, PhoneNumberType,
        is_valid_number, is_possible_number,
        number_type, format_number, parse,
    )
    PHONENUMBERS_AVAILABLE = True
except ImportError:
    PHONENUMBERS_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class ParsedPhone:
    """Structured phone number result."""
    raw: str                          # As supplied by caller
    e164: Optional[str]               # +919084399304
    country_code: Optional[str]       # "IN", "AE", "GB"
    phone_prefix: Optional[str]       # "+91"
    national_number: Optional[str]    # "9084399304"
    is_valid: bool
    is_possible: bool
    number_type: Optional[str]        # MOBILE | FIXED_LINE | VOIP | UNKNOWN
    masked: str                       # "+91 XXXX XX9304" — safe for logs

    def to_dict(self) -> dict:
        return {
            "e164": self.e164,
            "country_code": self.country_code,
            "phone_prefix": self.phone_prefix,
            "national_number": self.national_number,
            "is_valid": self.is_valid,
            "is_possible": self.is_possible,
            "number_type": self.number_type,
            "masked": self.masked,
        }


class PhoneService:
    """
    Production-grade phone number service.

    Core rules:
    - ALL phones stored in E.164 format: +[country_code][number]
    - NEVER log full phone numbers — always use masked()
    - country_code is ISO Alpha-2 (IN, AE, GB), NOT +91 prefix
    - Validation uses phonenumbers library (maintained), not regex alone
    """

    _FALLBACK_PREFIX_MAP = {
        "+91": "IN", "+971": "AE", "+966": "SA", "+44": "GB",
        "+1": "US", "+61": "AU", "+65": "SG", "+974": "QA",
        "+968": "OM", "+973": "BH", "+965": "KW",
    }

    _REGION_TO_PREFIX = {
        "IN": "+91", "AE": "+971", "SA": "+966", "GB": "+44",
        "US": "+1", "CA": "+1", "AU": "+61", "SG": "+65",
        "QA": "+974", "OM": "+968", "BH": "+973", "KW": "+965",
    }

    @classmethod
    def parse_phone(
        cls,
        raw: str,
        default_region: Optional[str] = None,
    ) -> ParsedPhone:
        """
        Parse and validate a phone number.

        Args:
            raw: The phone number as supplied (any format)
            default_region: ISO2 hint if no country prefix present (e.g., "IN")

        Returns:
            ParsedPhone with full metadata
        """
        raw = (raw or "").strip()

        if PHONENUMBERS_AVAILABLE:
            return cls._parse_with_library(raw, default_region)
        else:
            return cls._parse_fallback(raw, default_region)

    @classmethod
    def _parse_with_library(cls, raw: str, default_region: Optional[str]) -> ParsedPhone:
        """Full parsing via phonenumbers library."""
        try:
            parsed = phonenumbers.parse(raw, default_region)
        except Exception as e:
            logger.debug(f"[PhoneService] Failed to parse: {cls._mask(raw)} — {e}")
            return ParsedPhone(
                raw=raw,
                e164=None,
                country_code=None,
                phone_prefix=None,
                national_number=None,
                is_valid=False,
                is_possible=False,
                number_type=None,
                masked=cls._mask(raw),
            )

        valid = is_valid_number(parsed)
        possible = is_possible_number(parsed)
        e164 = format_number(parsed, PhoneNumberFormat.E164) if valid else None
        country = phonenumbers.region_code_for_number(parsed) if valid else None
        prefix = f"+{parsed.country_code}" if parsed.country_code else None
        national = str(parsed.national_number) if parsed.national_number else None

        # Number type
        try:
            ntype = number_type(parsed)
            ntype_str = {
                PhoneNumberType.MOBILE: "MOBILE",
                PhoneNumberType.FIXED_LINE: "FIXED_LINE",
                PhoneNumberType.FIXED_LINE_OR_MOBILE: "FIXED_LINE_OR_MOBILE",
                PhoneNumberType.VOIP: "VOIP",
                PhoneNumberType.TOLL_FREE: "TOLL_FREE",
                PhoneNumberType.PREMIUM_RATE: "PREMIUM_RATE",
                PhoneNumberType.UNKNOWN: "UNKNOWN",
            }.get(ntype, "UNKNOWN")
        except Exception:
            ntype_str = "UNKNOWN"

        return ParsedPhone(
            raw=raw,
            e164=e164,
            country_code=country,
            phone_prefix=prefix,
            national_number=national,
            is_valid=valid,
            is_possible=possible,
            number_type=ntype_str,
            masked=cls._mask(e164 or raw),
        )

    @classmethod
    def _parse_fallback(cls, raw: str, default_region: Optional[str]) -> ParsedPhone:
        """Fallback parsing when phonenumbers library not installed."""
        cleaned = re.sub(r"[^\d+]", "", raw)
        
        country = None
        prefix = None
        national = None

        if not cleaned.startswith("+"):
            def_reg = (default_region or "GLOBAL").upper()
            if def_reg in cls._REGION_TO_PREFIX:
                prefix = cls._REGION_TO_PREFIX[def_reg]
                country = def_reg
                national = cleaned.lstrip("0")
                cleaned = f"{prefix}{national}"
            else:
                cleaned = "+" + cleaned.lstrip("0")

        if not prefix:
            for pre, iso in sorted(cls._FALLBACK_PREFIX_MAP.items(), key=lambda x: -len(x[0])):
                if cleaned.startswith(pre):
                    prefix = pre
                    country = iso
                    national = cleaned[len(prefix):]
                    break

        if default_region and not country:
            country = default_region

        is_valid = bool(national and len(national) >= 7)

        return ParsedPhone(
            raw=raw,
            e164=cleaned if is_valid else None,
            country_code=country,
            phone_prefix=prefix,
            national_number=national,
            is_valid=is_valid,
            is_possible=is_valid,
            number_type=None,
            masked=cls._mask(cleaned),
        )

    @classmethod
    def normalize_to_e164(
        cls,
        raw: str,
        default_region: Optional[str] = None,
    ) -> Optional[str]:
        """
        Return E.164 form of phone number, or None if unparseable.
        Safe to store in database. Never logs the raw number.
        """
        result = cls.parse_phone(raw, default_region)
        if not result.e164:
            logger.warning(f"[PhoneService] Could not normalize to E.164: {result.masked}")
        return result.e164

    @classmethod
    def mask(cls, phone: Optional[str]) -> str:
        """
        Return masked version safe for logs/display.
        Example: +919084399304 → "+91 XXXX XXX304"
        ALWAYS use this in log statements instead of raw phone.
        """
        return cls._mask(phone or "")

    @classmethod
    def _mask(cls, phone: str) -> str:
        """Internal masking implementation."""
        if not phone:
            return "[NO_PHONE]"
        if len(phone) <= 7:
            return phone[:2] + "X" * (len(phone) - 2)
        keep_end = 4
        keep_start = 3 if phone.startswith("+") else 0
        visible_prefix = phone[:keep_start + 2]
        visible_suffix = phone[-keep_end:]
        hidden_count = len(phone) - len(visible_prefix) - keep_end
        return f"{visible_prefix} {'X' * max(hidden_count, 1)} {visible_suffix}"

    @classmethod
    def extract_country_code(cls, phone: str) -> Optional[str]:
        """Extract ISO Alpha-2 country code from phone number. Returns None if unknown."""
        result = cls.parse_phone(phone)
        return result.country_code

    @classmethod
    def format_for_display(cls, e164: str, locale: str = "en") -> str:
        """Format E.164 number for human display in given locale."""
        if PHONENUMBERS_AVAILABLE:
            try:
                parsed = phonenumbers.parse(e164, None)
                return format_number(parsed, PhoneNumberFormat.INTERNATIONAL)
            except Exception:
                pass
        return e164

    @classmethod
    def are_same_number(cls, phone_a: str, phone_b: str) -> bool:
        """
        Check if two phone strings refer to the same number.
        Used for deduplication — normalizes both to E.164 before comparing.
        """
        e164_a = cls.normalize_to_e164(phone_a)
        e164_b = cls.normalize_to_e164(phone_b)
        if not e164_a or not e164_b:
            return False
        return e164_a == e164_b
