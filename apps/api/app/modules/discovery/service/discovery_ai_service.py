"""
Part 21.2 — AI Discovery Signal Extraction Service
====================================================
Uses Gemini AI to extract real estate buying signals from actual incoming text.

Safety & Integrity Rules:
  - AI MUST NEVER invent: names, phones, emails, budgets, locations, or consent.
  - Prompt Injection Defense: untrusted content is strictly sanitized.
  - Whitelist-only output mapping.
  - LLM failure is non-fatal: graceful fallback to empty extraction.
"""
from __future__ import annotations
import json
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

ALLOWED_DISCOVERY_FIELDS = {
    "intent",              # BUYER, SELLER, TENANT, LANDLORD, INVESTOR
    "transaction_type",    # BUY, SELL, RENT, LEASE, INVEST
    "property_type",       # apartment, villa, townhouse, penthouse, plot
    "location",            # specific city or area mentioned
    "budget_min",          # numeric or null
    "budget_max",          # numeric or null
    "currency",            # ISO 4217 or null
    "bedrooms",            # integer or null
    "timeline",            # immediate, 1_month, 3_months, 6_months, etc.
    "financing_needed",    # yes, no, unknown
    "urgency",             # high, medium, low
}

INJECTION_PATTERNS = [
    r"ignore previous instructions",
    r"system prompt",
    r"new instructions",
    r"forget everything",
    r"act as",
    r"jailbreak",
    r"pretend you are",
    r"developer mode",
    r"reveal secret",
]


def sanitize_discovery_input(text: str) -> str:
    """Sanitize untrusted external text to prevent prompt injection."""
    if not text:
        return ""
    sanitized = text
    lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, lower):
            logger.warning("[AI_DISCOVERY] Prompt injection pattern detected and neutralized.")
            sanitized = re.sub(pattern, "[FILTERED]", sanitized, flags=re.IGNORECASE)
    # Truncate overly long inputs to limit token abuse
    return sanitized[:2500]


def build_signal_extraction_prompt(message: str, country_hint: Optional[str] = None) -> str:
    country_note = f"The inquiry is located in {country_hint}." if country_hint else ""
    return f"""You are a specialized Real Estate Signal Extraction Engine for BeetleLabs CRM.
Analyze the following inquiry message and extract ONLY factual buying/selling signals explicitly stated.

CRITICAL RULES:
1. NEVER invent, fabricate, or assume contact info (name, phone, email).
2. If a detail is NOT mentioned in the text, set its value to null.
3. Return ONLY valid JSON with the exact specified keys. No commentary.

{country_note}

Message:
\"\"\"
{message}
\"\"\"

Return JSON:
{{
  "intent": null,
  "transaction_type": null,
  "property_type": null,
  "location": null,
  "budget_min": null,
  "budget_max": null,
  "currency": null,
  "bedrooms": null,
  "timeline": null,
  "financing_needed": null,
  "urgency": null
}}
"""


class DiscoveryAIService:
    @staticmethod
    async def extract_signals_from_text(
        text: Optional[str], country_hint: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract structured real estate signals from message text.
        Never hallucinates missing fields.
        """
        if not text or not text.strip():
            return {k: None for k in ALLOWED_DISCOVERY_FIELDS}

        sanitized = sanitize_discovery_input(text)
        prompt = build_signal_extraction_prompt(sanitized, country_hint)

        try:
            from app.core.ai.gemini_client import GeminiClient
            client = GeminiClient()
            response_text = await client.generate_text(prompt, temperature=0.1, max_tokens=400)

            json_match = re.search(r"\{[^{}]*\}", response_text, re.DOTALL)
            if not json_match:
                return {k: None for k in ALLOWED_DISCOVERY_FIELDS}

            raw = json.loads(json_match.group())
            result = {}
            for key in ALLOWED_DISCOVERY_FIELDS:
                val = raw.get(key)
                if isinstance(val, str) and val.strip().lower() in ("", "null", "none", "n/a"):
                    val = None
                result[key] = val

            return result

        except ImportError:
            logger.debug("[AI_DISCOVERY] Gemini client unavailable — returning empty extraction")
            return {k: None for k in ALLOWED_DISCOVERY_FIELDS}
        except Exception as exc:
            logger.warning(f"[AI_DISCOVERY] Extraction exception: {exc}")
            return {k: None for k in ALLOWED_DISCOVERY_FIELDS}
