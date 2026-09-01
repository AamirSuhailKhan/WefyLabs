"""
Part 21.1 — AI Extraction Service
====================================
Uses existing Gemini/AI infrastructure to extract structured fields
from unstructured incoming lead content (messages, emails, etc.).

CRITICAL RULES:
  - AI MUST NOT invent: name, phone, email, budget, property, consent, location
  - If a field is not present in the source content: return None / UNKNOWN
  - AI inference is NOT verified fact — mark confidence < 1.0
  - Prompt injection protection: sanitize inputs before passing to LLM

Extractable fields:
  intent, property_type, location, budget, timeline,
  financing, investment_purpose, preferred_bedrooms,
  preferred_amenities, language, urgency
"""
from __future__ import annotations
import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Allowed output fields — AI cannot add arbitrary keys
ALLOWED_EXTRACTION_FIELDS = {
    "intent",           # BUYER | SELLER | TENANT | LANDLORD | INVESTOR | OTHER
    "property_type",    # From existing taxonomy
    "location",         # String — city/area
    "budget_min",       # Numeric string or null
    "budget_max",       # Numeric string or null
    "currency",         # ISO 4217 or null
    "timeline",         # immediate | 1_month | 3_months | 6_months | 12_months | unknown
    "financing",        # yes | no | unknown
    "investment_purpose",  # rental_income | capital_gain | own_use | unknown
    "preferred_bedrooms",  # Integer or null
    "preferred_amenities", # List of strings
    "language",         # BCP 47 detected language
    "urgency",          # high | medium | low | unknown
    "transaction_type", # BUY | SELL | RENT | LEASE | INVEST | UNKNOWN
}

# Prompt injection patterns to detect and sanitize
INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"system prompt",
    r"new instructions",
    r"forget everything",
    r"act as",
    r"jailbreak",
    r"pretend you are",
]


def _sanitize_input(text: str) -> str:
    """Basic prompt injection detection and sanitization."""
    lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower):
            logger.warning(f"[AI_EXTRACT] Potential prompt injection detected — sanitizing")
            # Replace with safe placeholder
            text = re.sub(pattern, "[REDACTED]", text, flags=re.IGNORECASE)
    # Truncate extremely long inputs
    return text[:2000]


def _build_extraction_prompt(content: str, language_hint: Optional[str] = None) -> str:
    lang_note = f"The message may be in {language_hint}." if language_hint else ""
    return f"""You are a real-estate lead data extraction assistant for BeetleLabs CRM.
Extract structured information from the following real estate inquiry message.

CRITICAL RULES:
1. NEVER invent or assume: name, phone, email, budget, property, location, consent
2. If a field is not mentioned in the message, set it to null
3. Only extract what is EXPLICITLY stated or can be DIRECTLY inferred from the text
4. Do NOT hallucinate facts not in the message
5. Return ONLY valid JSON with these exact keys (no extra keys)

{lang_note}

Message:
\"\"\"
{content}
\"\"\"

Return JSON with ONLY these keys (set null if not present):
{{
  "intent": null,
  "property_type": null,
  "location": null,
  "budget_min": null,
  "budget_max": null,
  "currency": null,
  "timeline": null,
  "financing": null,
  "investment_purpose": null,
  "preferred_bedrooms": null,
  "preferred_amenities": null,
  "language": null,
  "urgency": null,
  "transaction_type": null
}}
"""


async def extract_from_message(
    content: Optional[str],
    language_hint: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Extract structured real-estate intent fields from free-text content.

    Returns a dict with ONLY the allowed fields. Never adds extra keys.
    Empty/null fields are preserved as None.
    """
    if not content or not content.strip():
        return {k: None for k in ALLOWED_EXTRACTION_FIELDS}

    sanitized = _sanitize_input(content)
    prompt = _build_extraction_prompt(sanitized, language_hint)

    try:
        # Use existing Gemini infrastructure
        from app.core.ai.gemini_client import GeminiClient
        client = GeminiClient()
        response_text = await client.generate_text(prompt, temperature=0.1, max_tokens=500)

        # Parse and validate response
        extracted = _parse_and_validate_response(response_text)
        return extracted

    except ImportError:
        logger.debug("[AI_EXTRACT] Gemini client not available — returning empty extraction")
        return {k: None for k in ALLOWED_EXTRACTION_FIELDS}
    except Exception as exc:
        logger.warning(f"[AI_EXTRACT] Extraction failed: {exc}")
        return {k: None for k in ALLOWED_EXTRACTION_FIELDS}


def _parse_and_validate_response(response_text: str) -> Dict[str, Any]:
    """Parse AI response and validate — only allowed fields are returned."""
    try:
        # Extract JSON from response (may have surrounding text)
        json_match = re.search(r"\{[^{}]*\}", response_text, re.DOTALL)
        if not json_match:
            return {k: None for k in ALLOWED_EXTRACTION_FIELDS}

        raw = json.loads(json_match.group())

        # Only return allowed fields — drop any extra keys AI may have added
        result = {}
        for key in ALLOWED_EXTRACTION_FIELDS:
            val = raw.get(key)
            # Convert empty strings to None
            if isinstance(val, str) and val.strip() in ("", "null", "N/A", "n/a"):
                val = None
            result[key] = val

        return result

    except (json.JSONDecodeError, Exception) as e:
        logger.debug(f"[AI_EXTRACT] Response parse error: {e}")
        return {k: None for k in ALLOWED_EXTRACTION_FIELDS}
