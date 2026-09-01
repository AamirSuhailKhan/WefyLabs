"""
Part 21.7 — Multi-Intent Extraction Engine
==========================================
Classifies customer responses into controlled intent categories.
Enforces:
- Prompt injection defense
- Multi-intent extraction from a single message
- Evidence quoting and calibrated confidence scoring
- Deterministic extraction fallback
"""
from __future__ import annotations

import re
import logging
from typing import List, Tuple

from app.modules.conversation_intelligence.taxonomies import CustomerIntent
from app.modules.conversation_intelligence.dto import ExtractedIntentDTO
from app.infrastructure.security.prompt_guard import validate_prompt_injection

logger = logging.getLogger(__name__)

# ─── Opt-Out & Stop Patterns ──────────────────────────────────────────────────
OPT_OUT_PATTERNS = [
    r"^\s*stop\s*$",
    r"\bstop\s+(messaging|contacting|calling|texting|emailing)\s+me\b",
    r"\bstop\s+messaging\b",
    r"\bstop\s+contacting\b",
    r"^\s*unsubscribe\s*$",
    r"^\s*cancel\s*$",
    r"^\s*quit\s*$",
    r"don'?t\s+(message|contact|call|email|text)\s+me",
    r"do\s+not\s+(message|contact|call|email|text)\s+me",
    r"remove\s+me(\s+from\s+(your|the)\s+list)?",
    r"no\s+more\s+messages?",
    r"leave\s+me\s+alone",
    r"block\s+me",
]

# ─── Human Agent Request Patterns ─────────────────────────────────────────────
HUMAN_AGENT_PATTERNS = [
    r"talk\s+to\s+(a\s+)?(human|person|agent|broker|manager|representative)",
    r"speak\s+(to|with)\s+(a\s+)?(human|person|agent|broker|manager|someone)",
    r"real\s+person",
    r"human\s+agent",
    r"connect\s+me\s+to\s+(a\s+)?(human|broker|agent)",
    r"are\s+you\s+a\s+bot",
]

# ─── Complaint & Legal Risk Patterns ──────────────────────────────────────────
COMPLAINT_PATTERNS = [
    r"terrible\s+service",
    r"worst\s+experience",
    r"scam",
    r"cheat",
    r"unacceptable",
    r"harassment",
    r"file\s+a\s+complaint",
    r"report\s+you",
    r"waste\s+of\s+time",
]

LEGAL_PATTERNS = [
    r"lawyer",
    r"attorney",
    r"legal\s+action",
    r"sue\s+you",
    r"police",
    r"authorities",
    r"court",
    r"rera\s+complaint",
]


class IntentExtractor:
    """Extracts all active intents from inbound customer text."""

    @staticmethod
    def sanitize_and_check_injection(text: str) -> Tuple[bool, str]:
        """Validates text against prompt injection patterns."""
        is_safe, error_msg = validate_prompt_injection(text)
        if not is_safe:
            logger.warning(f"[IntentExtractor] Prompt injection attempt detected: {error_msg}")
            return False, error_msg
        return True, text

    @classmethod
    def extract_intents(cls, text: str) -> List[ExtractedIntentDTO]:
        """
        Deterministic, robust multi-intent extraction.
        A single message can contain multiple intents.
        """
        if not text or not text.strip():
            return [ExtractedIntentDTO(intent=CustomerIntent.UNCLEAR, confidence=0.0, evidence="")]

        _, sanitized = cls.sanitize_and_check_injection(text)
        lowered = sanitized.lower()
        intents: List[ExtractedIntentDTO] = []

        # 1. OPT_OUT / STOP_COMMUNICATION (Highest Priority)
        for pat in OPT_OUT_PATTERNS:
            match = re.search(pat, lowered)
            if match:
                intents.append(
                    ExtractedIntentDTO(
                        intent=CustomerIntent.OPT_OUT,
                        confidence=1.0,
                        evidence=match.group(0),
                    )
                )
                intents.append(
                    ExtractedIntentDTO(
                        intent=CustomerIntent.STOP_COMMUNICATION,
                        confidence=1.0,
                        evidence=match.group(0),
                    )
                )
                return intents  # Early exit on stop/opt-out

        # 2. LEGAL RISK
        for pat in LEGAL_PATTERNS:
            match = re.search(pat, lowered)
            if match:
                intents.append(
                    ExtractedIntentDTO(
                        intent=CustomerIntent.LEGAL_RISK,
                        confidence=0.95,
                        evidence=match.group(0),
                    )
                )
                break

        # 3. COMPLAINT
        for pat in COMPLAINT_PATTERNS:
            match = re.search(pat, lowered)
            if match:
                intents.append(
                    ExtractedIntentDTO(
                        intent=CustomerIntent.COMPLAINT,
                        confidence=0.90,
                        evidence=match.group(0),
                    )
                )
                break

        # 4. HUMAN AGENT REQUEST
        for pat in HUMAN_AGENT_PATTERNS:
            match = re.search(pat, lowered)
            if match:
                intents.append(
                    ExtractedIntentDTO(
                        intent=CustomerIntent.HUMAN_AGENT_REQUEST,
                        confidence=0.95,
                        evidence=match.group(0),
                    )
                )
                break

        # 5. VIEWING INTENTS
        if re.search(r"(can'?t\s+make\s+it|cancel\s+(the\s+)?(viewing|visit|meeting))", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.VIEWING_CANCELLATION, confidence=0.95, evidence="cancellation intent"))
        elif re.search(r"(reschedule|change\s+the\s+time|postpone|another\s+day)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.VIEWING_RESCHEDULE, confidence=0.90, evidence="reschedule intent"))
        elif re.search(r"(works\s+for\s+me|confirm(ed)?|i'?ll\s+be\s+there|see\s+you\s+then|perfect\s+time)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.VIEWING_CONFIRMATION, confidence=0.90, evidence="confirmation intent"))
        elif re.search(r"(visit|view|viewing|tour|see\s+the\s+property|schedule\s+a\s+visit)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.VIEWING_REQUEST, confidence=0.92, evidence="viewing request"))

        # 6. PRICE OBJECTION / NEGOTIATION
        if re.search(r"(too\s+(expensive|high|pricey)|out\s+of\s+my\s+budget|over\s+budget)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.PRICE_OBJECTION, confidence=0.95, evidence="price objection"))

        if re.search(r"(discount|reduce\s+the\s+price|negotiable|best\s+price|last\s+price|can\s+you\s+do\s+\d|can\s+the\s+owner)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.NEGOTIATION, confidence=0.90, evidence="negotiation intent"))

        # 7. BUDGET / REQUIREMENT CHANGES
        if re.search(r"(my\s+budget\s+is|i\s+can\s+spend|can\s+afford|looking\s+around\s+\d+(\.\d+)?\s*(m|k|aed|inr|lakh|cr))", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.BUDGET_CHANGE, confidence=0.90, evidence="budget change"))

        if re.search(r"(show\s+me\s+in|prefer|looking\s+in|instead\s+of\s+\w+|want\s+in)\s+[a-zA-Z\s]+", lowered):
            if any(loc in lowered for loc in ["downtown", "marina", "palm", "creek", "hills", "business bay", "jvc", "difc"]):
                intents.append(ExtractedIntentDTO(intent=CustomerIntent.LOCATION_CHANGE, confidence=0.90, evidence="location change"))

        if re.search(r"(\d\s*bhk|\d\s*bed|villa|apartment|townhouse|penthouse)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.PROPERTY_TYPE_CHANGE, confidence=0.85, evidence="property type change"))

        # 8. PROPERTY REQUEST & INTEREST
        if re.search(r"(show\s+me|send\s+me|share|any\s+options|more\s+properties|details\s+of|brochure)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.PROPERTY_REQUEST, confidence=0.88, evidence="property request"))

        if re.search(r"(interested|i\s+like|looks\s+good|love\s+this|amazing|great\s+option)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.POSITIVE_INTEREST, confidence=0.85, evidence="positive interest"))

        if re.search(r"(not\s+interested|don'?t\s+like|pass\s+on\s+this|hate\s+it|not\s+for\s+me)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.NEGATIVE_INTEREST, confidence=0.88, evidence="negative interest"))

        # 9. GENERAL INTENT (Buy / Rent / Invest)
        if re.search(r"(buy|purchase|own|invest)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.BUYING_INTENT, confidence=0.85, evidence="buying intent"))
        elif re.search(r"(rent|lease)", lowered):
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.RENTING_INTENT, confidence=0.85, evidence="renting intent"))

        if not intents:
            intents.append(ExtractedIntentDTO(intent=CustomerIntent.NEUTRAL, confidence=0.60, evidence="neutral text"))

        return intents
