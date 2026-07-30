import re

def redact_phone_number(phone: str) -> str:
    """Masks phone number for PII log compliance (e.g. +91 98765 43210 -> +91 **** **210)."""
    if not phone or len(phone) < 6:
        return "****"
    return f"{phone[:3]} **** **{phone[-3:]}"

def redact_email(email: str) -> str:
    """Masks email address for PII log compliance (e.g. rahul@domain.com -> r***l@domain.com)."""
    if not email or "@" not in email:
        return "****"
    name, domain = email.split("@", 1)
    if len(name) <= 2:
        masked_name = name[0] + "*"
    else:
        masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
    return f"{masked_name}@{domain}"

def sanitize_pii_dict(data: dict) -> dict:
    """Recursively redacts PII fields in dictionaries before logging."""
    sanitized = {}
    for key, value in data.items():
        key_lower = key.lower()
        if "phone" in key_lower and isinstance(value, str):
            sanitized[key] = redact_phone_number(value)
        elif "email" in key_lower and isinstance(value, str):
            sanitized[key] = redact_email(value)
        elif "token" in key_lower or "secret" in key_lower or "password" in key_lower:
            sanitized[key] = "[REDACTED_SECRET]"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_pii_dict(value)
        else:
            sanitized[key] = value
    return sanitized
