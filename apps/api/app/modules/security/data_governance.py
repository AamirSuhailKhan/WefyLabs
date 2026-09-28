"""
WefyLabs Data Governance, Classification & PII Protection Engine
================================================================
Implements Build 11 Enterprise Data Governance:
- 4 Canonical Data Classifications:
  PUBLIC, INTERNAL, CONFIDENTIAL, RESTRICTED
- Field-level Data Inventory across CRM, Payments, Properties & AI Context
- Data Minimization & Role-Based Field Redaction / Masking
- Sensitive Data Scrubber for AI Boundaries, Logs, and Exports
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Union


class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"              # Marketing descriptions, brochures, organization public slug
    INTERNAL = "INTERNAL"          # Lead status, deal stage, tasks, assignees, internal operational notes
    CONFIDENTIAL = "CONFIDENTIAL"  # Customer identity, phone, email, budget, conversations, offers
    RESTRICTED = "RESTRICTED"      # Payment tokens, commissions, owner private contracts, provider API keys, credentials


# Canonical Data Classification Inventory mapping fields to sensitivity
DATA_INVENTORY: dict[str, dict[str, DataClassification]] = {
    "lead": {
        "id": DataClassification.PUBLIC,
        "organization_id": DataClassification.INTERNAL,
        "name": DataClassification.CONFIDENTIAL,
        "phone": DataClassification.CONFIDENTIAL,
        "email": DataClassification.CONFIDENTIAL,
        "budget": DataClassification.CONFIDENTIAL,
        "pipeline_stage": DataClassification.INTERNAL,
        "source": DataClassification.INTERNAL,
        "assigned_agent_id": DataClassification.INTERNAL,
        "internal_notes": DataClassification.INTERNAL,
        "metadata": DataClassification.INTERNAL,
    },
    "property": {
        "id": DataClassification.PUBLIC,
        "organization_id": DataClassification.INTERNAL,
        "title": DataClassification.PUBLIC,
        "description": DataClassification.PUBLIC,
        "location": DataClassification.PUBLIC,
        "price": DataClassification.PUBLIC,
        "bedrooms": DataClassification.PUBLIC,
        "amenities": DataClassification.PUBLIC,
        "owner_contact": DataClassification.RESTRICTED,
        "commission_rate": DataClassification.RESTRICTED,
        "internal_valuation": DataClassification.RESTRICTED,
        "private_notes": DataClassification.RESTRICTED,
    },
    "opportunity": {
        "id": DataClassification.PUBLIC,
        "organization_id": DataClassification.INTERNAL,
        "lead_id": DataClassification.CONFIDENTIAL,
        "property_id": DataClassification.PUBLIC,
        "stage": DataClassification.INTERNAL,
        "deal_value": DataClassification.CONFIDENTIAL,
        "expected_commission": DataClassification.RESTRICTED,
        "closing_probability": DataClassification.INTERNAL,
    },
    "booking": {
        "id": DataClassification.PUBLIC,
        "organization_id": DataClassification.INTERNAL,
        "lead_id": DataClassification.CONFIDENTIAL,
        "property_id": DataClassification.PUBLIC,
        "booking_amount": DataClassification.CONFIDENTIAL,
        "payment_status": DataClassification.CONFIDENTIAL,
        "payment_reference": DataClassification.RESTRICTED,
        "slot_time": DataClassification.INTERNAL,
    },
    "payment": {
        "id": DataClassification.PUBLIC,
        "organization_id": DataClassification.INTERNAL,
        "amount": DataClassification.CONFIDENTIAL,
        "currency": DataClassification.CONFIDENTIAL,
        "card_last4": DataClassification.CONFIDENTIAL,
        "card_brand": DataClassification.CONFIDENTIAL,
        "payment_method_token": DataClassification.RESTRICTED,
        "client_secret": DataClassification.RESTRICTED,
        "gateway_response": DataClassification.RESTRICTED,
    },
    "ai_context": {
        "prompt": DataClassification.INTERNAL,
        "response": DataClassification.INTERNAL,
        "system_instructions": DataClassification.RESTRICTED,
        "api_keys": DataClassification.RESTRICTED,
        "provider_credentials": DataClassification.RESTRICTED,
        "tool_arguments": DataClassification.INTERNAL,
    }
}


_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_PHONE_RE = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
_CARD_RE = re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b")
_BEARER_TOKEN_RE = re.compile(r"Bearer\s+([A-Za-z0-9\-._~+/]+=*)", re.IGNORECASE)
_SECRET_KEY_RE = re.compile(
    r"(api[_-]?key|secret|password|auth_token|access_token|refresh_token)\s*[:=]\s*['\"]?([A-Za-z0-9\-_]{8,})['\"]?",
    re.IGNORECASE
)

SENSITIVE_FIELD_NAMES: set[str] = {
    "password", "secret", "token", "access_token", "refresh_token",
    "api_key", "apikey", "authorization", "credential", "private_key",
    "secret_key", "card_number", "cvv", "payment_method_token", "client_secret"
}


def mask_phone(phone: Optional[str]) -> str:
    """Masks phone number preserving country code and last 4 digits."""
    if not phone:
        return ""
    clean = re.sub(r"[^\d+]", "", phone)
    if len(clean) <= 6:
        return "****"
    return clean[:3] + "******" + clean[-4:]


def mask_email(email: Optional[str]) -> str:
    """Masks email address, showing only first and last characters of username."""
    if not email or "@" not in email:
        return ""
    user, domain = email.split("@", 1)
    if len(user) <= 2:
        masked_user = user[0] + "***"
    else:
        masked_user = user[0] + "***" + user[-1]
    return f"{masked_user}@{domain}"


def scrub_pii_and_secrets(text: str) -> str:
    """Neutralizes emails, phones, card numbers, bearer tokens, and secrets from text."""
    if not isinstance(text, str):
        return text
    s = _BEARER_TOKEN_RE.sub("Bearer [REDACTED_TOKEN]", text)
    s = _SECRET_KEY_RE.sub(r"\1: [REDACTED_SECRET]", s)
    s = _CARD_RE.sub("[REDACTED_CARD]", s)
    s = _EMAIL_RE.sub("[REDACTED_EMAIL]", s)
    s = _PHONE_RE.sub("[REDACTED_PHONE]", s)
    return s


def filter_payload_for_role(
    resource_type: str,
    payload: Dict[str, Any],
    role: str
) -> Dict[str, Any]:
    """
    Applies role-based attribute filtering according to data classification.
    - OWNER / ADMIN: All fields accessible.
    - FINANCE: Payment/Revenue restricted fields allowed; property owner contracts restricted.
    - SALES / AGENT / MARKETING / SUPPORT / ANALYST / READ_ONLY:
      RESTRICTED fields are omitted or replaced with [RESTRICTED].
    """
    norm_role = role.strip().upper() if role else "READ_ONLY"
    if norm_role in ("OWNER", "ADMIN"):
        return payload

    inventory = DATA_INVENTORY.get(resource_type.lower(), {})
    sanitized: Dict[str, Any] = {}

    for k, v in payload.items():
        classification = inventory.get(k, DataClassification.INTERNAL)

        # Restricted check
        if classification == DataClassification.RESTRICTED:
            if norm_role == "FINANCE" and resource_type in ("payment", "booking", "opportunity"):
                sanitized[k] = v
            else:
                sanitized[k] = "[RESTRICTED]"
        elif classification == DataClassification.CONFIDENTIAL:
            # Mask PII for READ_ONLY roles
            if norm_role == "READ_ONLY":
                if k == "phone" and isinstance(v, str):
                    sanitized[k] = mask_phone(v)
                elif k == "email" and isinstance(v, str):
                    sanitized[k] = mask_email(v)
                else:
                    sanitized[k] = v
            else:
                sanitized[k] = v
        else:
            sanitized[k] = v

    return sanitized


def sanitize_for_ai_context(obj: Any) -> Any:
    """
    Strictly removes credentials, secrets, and RESTRICTED fields before feeding into AI prompts.
    """
    if isinstance(obj, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in obj.items():
            if any(sens in k.lower() for sens in SENSITIVE_FIELD_NAMES):
                continue
            cleaned[k] = sanitize_for_ai_context(v)
        return cleaned
    elif isinstance(obj, list):
        return [sanitize_for_ai_context(item) for item in obj]
    elif isinstance(obj, str):
        return scrub_pii_and_secrets(obj)
    return obj
