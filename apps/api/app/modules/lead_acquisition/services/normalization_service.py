"""
Part 21.1 — Phone / Email / Budget Normalization Service
=========================================================
Normalizes contact data before deduplication or CRM import.

Rules:
  Phone → E.164 format using phonenumbers library (falls back gracefully)
  Email → lowercase, strip whitespace, canonical form
  Budget → Decimal (NEVER float)
  Currency → ISO 4217 uppercase
  Name → stripped, title-cased

AI MUST NOT invent values. If absent: None.
"""
from __future__ import annotations
import hashlib
import re
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# E.164 pattern for quick validation
E164_PATTERN = re.compile(r"^\+[1-9]\d{6,14}$")


class PhoneNormalizationResult(tuple):
    """
    Subclass of 2-tuple (normalized_phone, confidence) for backwards compatibility.
    Code using `phone_e164, phone_conf = normalize_phone(...)` continues to work.
    Also exposes:
        .normalized_phone
        .confidence
        .raw_phone
        .phone_country
        .normalization_status: 'valid' | 'formatted' | 'uncertain' | 'invalid'
    """
    def __new__(
        cls,
        normalized_phone: Optional[str],
        confidence: float,
        raw_phone: Optional[str] = None,
        phone_country: Optional[str] = None,
        normalization_status: str = "invalid"
    ):
        instance = super().__new__(cls, (normalized_phone, confidence))
        instance.normalized_phone = normalized_phone
        instance.confidence = confidence
        instance.raw_phone = raw_phone
        instance.phone_country = phone_country
        instance.normalization_status = normalization_status
        return instance

    def to_dict(self) -> dict:
        return {
            "normalized_phone": self.normalized_phone,
            "confidence": self.confidence,
            "raw_phone": self.raw_phone,
            "phone_country": self.phone_country,
            "normalization_status": self.normalization_status,
        }


COUNTRY_PREFIX_MAP = {
    "91": "IN",
    "971": "AE",
    "1": "US",
    "44": "GB",
    "65": "SG",
    "60": "MY",
    "966": "SA",
    "974": "QA",
}


def _infer_country_from_e164(e164: str) -> Optional[str]:
    digits = e164.lstrip("+")
    for prefix_len in (3, 2, 1):
        prefix = digits[:prefix_len]
        if prefix in COUNTRY_PREFIX_MAP:
            return COUNTRY_PREFIX_MAP[prefix]
    return None


def normalize_phone(
    phone: Optional[str],
    default_country_code: Optional[str] = None
) -> PhoneNormalizationResult:
    """
    Normalize phone to canonical E.164 format.
    Handles:
      - WhatsApp identifiers (@c.us, @s.whatsapp.net, whatsapp:)
      - Indian 10-digit [6-9]XXXXXXXXX -> +91XXXXXXXXXX
      - Indian 11-digit 0[6-9]XXXXXXXXX -> +91XXXXXXXXXX
      - Indian 12-digit 91[6-9]XXXXXXXXX -> +91XXXXXXXXXX
      - International prefixes (00XX -> +XX)
      - Standard E.164 (+[1-9]...)
      - Preserves raw input, country code, and explicit normalization status

    Returns:
        PhoneNormalizationResult (subclass of 2-tuple (normalized_e164, confidence))
    """
    if not phone:
        return PhoneNormalizationResult(None, 0.0, raw_phone=phone, phone_country=None, normalization_status="invalid")

    raw_input = phone
    cleaned = phone.strip()
    if not cleaned:
        return PhoneNormalizationResult(None, 0.0, raw_phone=raw_input, phone_country=None, normalization_status="invalid")

    # Strip WhatsApp and Tel URI prefixes / suffixes
    cleaned = re.sub(r"^(whatsapp|tel):", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"@(c\.us|s\.whatsapp\.net)$", "", cleaned, flags=re.IGNORECASE)

    # Remove common formatting characters: spaces, hyphens, parentheses, dots
    digits_only = re.sub(r"[\s\-\(\)\.]", "", cleaned)

    if not digits_only or not re.search(r"\d", digits_only):
        return PhoneNormalizationResult(None, 0.0, raw_phone=raw_input, phone_country=None, normalization_status="invalid")

    # 1. Already valid E.164?
    if E164_PATTERN.match(digits_only):
        country = _infer_country_from_e164(digits_only) or default_country_code
        return PhoneNormalizationResult(
            digits_only,
            1.0,
            raw_phone=raw_input,
            phone_country=country,
            normalization_status="valid"
        )

    # 2. Try phonenumbers library if available in environment
    try:
        import phonenumbers
        country_hint = default_country_code or "IN"
        try:
            parsed = phonenumbers.parse(cleaned, country_hint)
            if phonenumbers.is_valid_number(parsed):
                e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                region = phonenumbers.region_code_for_number(parsed)
                return PhoneNormalizationResult(
                    e164,
                    0.95,
                    raw_phone=raw_input,
                    phone_country=region,
                    normalization_status="valid"
                )
        except phonenumbers.NumberParseException:
            pass
    except ImportError:
        pass

    # 3. Leading 00 international dialing prefix (e.g. 00971501234567 -> +971501234567)
    if digits_only.startswith("00") and len(digits_only) >= 10:
        candidate = "+" + digits_only[2:]
        if E164_PATTERN.match(candidate):
            country = _infer_country_from_e164(candidate) or default_country_code
            return PhoneNormalizationResult(
                candidate,
                0.85,
                raw_phone=raw_input,
                phone_country=country,
                normalization_status="formatted"
            )

    # 4. Indian formats:
    # 4a. 12 digits starting with 91 and mobile digit [6-9]
    if len(digits_only) == 12 and digits_only.startswith("91") and digits_only[2] in "6789":
        candidate = "+" + digits_only
        return PhoneNormalizationResult(
            candidate,
            0.9,
            raw_phone=raw_input,
            phone_country="IN",
            normalization_status="formatted"
        )

    # 4b. 11 digits starting with 0 and mobile digit [6-9] (trunk prefix 0)
    if len(digits_only) == 11 and digits_only.startswith("0") and digits_only[1] in "6789":
        candidate = "+91" + digits_only[1:]
        return PhoneNormalizationResult(
            candidate,
            0.85,
            raw_phone=raw_input,
            phone_country="IN",
            normalization_status="formatted"
        )

    # 4c. 10 digits starting with [6-9] (Indian mobile standard)
    if len(digits_only) == 10 and digits_only[0] in "6789":
        default_prefix = default_country_code.upper() if default_country_code else "IN"
        if default_prefix in ("IN", "+91", None):
            candidate = "+91" + digits_only
            return PhoneNormalizationResult(
                candidate,
                0.85,
                raw_phone=raw_input,
                phone_country="IN",
                normalization_status="formatted"
            )

    # 5. Fallback with default_country_code if specified
    if default_country_code and not digits_only.startswith("+"):
        prefix = default_country_code if default_country_code.startswith("+") else f"+{default_country_code}"
        candidate = f"{prefix}{digits_only}"
        if E164_PATTERN.match(candidate):
            return PhoneNormalizationResult(
                candidate,
                0.75,
                raw_phone=raw_input,
                phone_country=default_country_code,
                normalization_status="formatted"
            )

    # 6. Uncertain: 7 or more digits but non-conformant
    raw_stripped = re.sub(r"\s+", "", cleaned)
    digits_count = len(re.sub(r"\D", "", raw_stripped))
    if digits_count >= 7:
        return PhoneNormalizationResult(
            raw_stripped,
            0.3,
            raw_phone=raw_input,
            phone_country=None,
            normalization_status="uncertain"
        )

    # 7. Invalid: too short or nonsensical
    return PhoneNormalizationResult(
        None,
        0.0,
        raw_phone=raw_input,
        phone_country=None,
        normalization_status="invalid"
    )


def normalize_email(email: Optional[str]) -> Tuple[Optional[str], str]:
    """
    Normalize email to canonical lowercase form.

    Returns:
        (normalized_email_or_None, fingerprint_hex)
    """
    if not email:
        return None, ""

    email = email.strip().lower()
    if not email or "@" not in email:
        return None, ""

    parts = email.split("@")
    if len(parts) != 2:
        return None, ""

    local, domain = parts
    if not local or not domain or "." not in domain:
        return None, ""

    # Remove Gmail-style plus aliases and dots for fingerprint only
    # But preserve the actual normalized email as-is (do not mutate the real email)
    fingerprint_local = local.split("+")[0].replace(".", "")
    fingerprint_source = f"{fingerprint_local}@{domain}"
    fingerprint = hashlib.sha256(fingerprint_source.encode()).hexdigest()

    return email, fingerprint


def normalize_name(name: Optional[str]) -> Optional[str]:
    """Strip and title-case a name. Never invent names."""
    if not name:
        return None
    stripped = name.strip()
    if not stripped:
        return None
    # Remove excessive whitespace
    cleaned = re.sub(r"\s+", " ", stripped)
    return cleaned


def normalize_budget(
    raw_budget: Optional[str | float | int | Decimal],
    currency: Optional[str] = None
) -> Tuple[Optional[Decimal], Optional[str]]:
    """
    Normalize budget to Decimal. Never use float for budget.

    Returns:
        (budget_decimal_or_None, normalized_currency_or_None)
    """
    normalized_currency = currency.strip().upper() if currency else None

    if raw_budget is None:
        return None, normalized_currency

    if isinstance(raw_budget, Decimal):
        return raw_budget, normalized_currency

    try:
        # Handle string formats: "2,000,000" "AED 2.5M" "2.5 million"
        if isinstance(raw_budget, str):
            raw = raw_budget.strip()
            # Remove currency prefix
            raw = re.sub(r"^[A-Z]{3}\s*", "", raw, flags=re.IGNORECASE)
            # Handle millions/thousands shorthand
            multiplier = Decimal("1")
            if raw.upper().endswith("M") or raw.upper().endswith("MILLION"):
                multiplier = Decimal("1000000")
                raw = re.sub(r"(M|MILLION)$", "", raw, flags=re.IGNORECASE).strip()
            elif raw.upper().endswith("K"):
                multiplier = Decimal("1000")
                raw = raw[:-1].strip()
            # Remove commas
            raw = raw.replace(",", "").strip()
            if not raw:
                return None, normalized_currency
            return Decimal(raw) * multiplier, normalized_currency
        return Decimal(str(raw_budget)), normalized_currency
    except (InvalidOperation, ValueError) as e:
        logger.debug(f"[NORMALIZATION] Budget normalization failed: {raw_budget!r} — {e}")
        return None, normalized_currency


def normalize_currency(currency: Optional[str]) -> Optional[str]:
    """Normalize currency to ISO 4217 uppercase. Return None if blank."""
    if not currency:
        return None
    code = currency.strip().upper()
    if len(code) != 3 or not code.isalpha():
        return None
    return code


def normalize_country_code(country: Optional[str]) -> Optional[str]:
    """Normalize to ISO Alpha-2 uppercase. Return None if invalid."""
    if not country:
        return None
    code = country.strip().upper()
    if len(code) == 2 and code.isalpha():
        return code
    return None
