"""
WefyLabs PII & Secret Redaction Engine
=====================================
Ensures that no customer PII (phone, email) or security secrets (tokens, passwords, API keys)
are inadvertently leaked into application logs, Prometheus metric labels, or error messages.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Union

_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_REGEX = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_TOKEN_REGEX = re.compile(r"Bearer\s+([A-Za-z0-9\-._~+/]+=*)", re.IGNORECASE)
_API_KEY_REGEX = re.compile(r"(api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{8,})['\"]?", re.IGNORECASE)

SENSITIVE_KEYS = {
    "password", "secret", "token", "access_token", "refresh_token",
    "api_key", "apikey", "authorization", "auth", "credential",
    "private_key", "secret_key", "card_number", "cvv"
}


def redact_string(text: str) -> str:
    """Redacts known PII patterns and secrets from a raw string."""
    if not isinstance(text, str):
        return text
    s = _TOKEN_REGEX.sub("Bearer [REDACTED_TOKEN]", text)
    s = _API_KEY_REGEX.sub(r"\1: [REDACTED_SECRET]", s)
    s = _EMAIL_REGEX.sub("[REDACTED_EMAIL]", s)
    s = _PHONE_REGEX.sub("[REDACTED_PHONE]", s)
    return s


def redact_payload(obj: Any) -> Any:
    """
    Recursively redacts dictionary or list payloads, scrubbing both
    sensitive dictionary keys and PII patterns in string values.
    """
    if isinstance(obj, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in obj.items():
            if any(sens in k.lower() for sens in SENSITIVE_KEYS):
                cleaned[k] = "[REDACTED]"
            else:
                cleaned[k] = redact_payload(v)
        return cleaned
    elif isinstance(obj, list):
        return [redact_payload(item) for item in obj]
    elif isinstance(obj, str):
        return redact_string(obj)
    return obj
