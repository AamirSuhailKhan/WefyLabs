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


def normalize_phone(phone: Optional[str], default_country_code: Optional[str] = None) -> Tuple[Optional[str], float]:
    """
    Normalize phone to E.164 format.

    Returns:
        (normalized_phone_e164_or_None, confidence_float)
        confidence = 1.0 if already E.164
        confidence = 0.8 if normalized from local format
        confidence = 0.0 if cannot normalize
    """
    if not phone:
        return None, 0.0

    phone = phone.strip()
    if not phone:
        return None, 0.0

    # Remove common formatting characters
    digits_only = re.sub(r"[\s\-\(\)\.]", "", phone)

    # Already E.164?
    if E164_PATTERN.match(digits_only):
        return digits_only, 1.0

    # Try phonenumbers library if available
    try:
        import phonenumbers
        country = default_country_code or "AE"  # Default region for parsing only — NOT business logic
        try:
            parsed = phonenumbers.parse(phone, country)
            if phonenumbers.is_valid_number(parsed):
                e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
                return e164, 0.9
        except phonenumbers.NumberParseException:
            pass
    except ImportError:
        pass

    # Last resort: if starts with 00, convert to +
    if digits_only.startswith("00") and len(digits_only) >= 10:
        candidate = "+" + digits_only[2:]
        if E164_PATTERN.match(candidate):
            return candidate, 0.7

    # Cannot normalize — return raw stripped for storage, low confidence
    raw_stripped = re.sub(r"\s+", "", phone)
    if len(raw_stripped) >= 7:
        return raw_stripped, 0.3

    return None, 0.0


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
