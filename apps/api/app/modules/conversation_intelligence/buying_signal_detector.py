"""
Part 21.7 — Buying Signal Detector
==================================
Identifies high-confidence buying signals from customer communications.
Evaluates indicators:
- Viewing requests / Visit readiness
- Payment details / Payment plan inquiry
- Availability inquiry
- Mortgage / Financing inquiry
- Booking / Token deposit questions
- Explicit timeframe to close
- Request for contracts / documents
"""
from __future__ import annotations

import re
import logging
from typing import List

from app.modules.conversation_intelligence.taxonomies import (
    BuyingSignalLevel,
    BuyingSignalIndicator,
)
from app.modules.conversation_intelligence.dto import BuyingSignalDTO

logger = logging.getLogger(__name__)


class BuyingSignalDetector:
    """Grounded buying signal extraction."""

    @staticmethod
    def detect_signals(text: str) -> BuyingSignalDTO:
        if not text or not text.strip():
            return BuyingSignalDTO(
                level=BuyingSignalLevel.NONE,
                indicators=[],
                evidence=None,
                confidence=0.0,
            )

        lowered = text.lower()
        indicators: List[BuyingSignalIndicator] = []
        evidence_snippets: List[str] = []

        # 1. Booking / Token Deposit / Ready to close
        if re.search(r"(book\s+this|token\s+amount|ready\s+to\s+(book|buy|pay|close)|lock\s+this\s+unit|reserve)", lowered):
            indicators.append(BuyingSignalIndicator.BOOKING_INQUIRY)
            evidence_snippets.append("Booking inquiry")

        # 2. Viewing / Visit request
        if re.search(r"(visit|view|viewing|tour|see\s+the\s+unit|when\s+can\s+i\s+(visit|see)|meet\s+at\s+site)", lowered):
            indicators.append(BuyingSignalIndicator.VIEWING_REQUEST)
            evidence_snippets.append("Viewing request")

        # 3. Payment Details / Payment Plan
        if re.search(r"(payment\s+plan|down\s*payment|installment|cheques|cash\s+discount)", lowered):
            indicators.append(BuyingSignalIndicator.PAYMENT_DETAILS_REQUEST)
            evidence_snippets.append("Payment details inquiry")

        # 4. Mortgage / Loan inquiry
        if re.search(r"(mortgage|bank\s+loan|pre-?approval|finance\s+option)", lowered):
            indicators.append(BuyingSignalIndicator.MORTGAGE_INQUIRY)
            evidence_snippets.append("Mortgage inquiry")

        # 5. Availability & Possession
        if re.search(r"(is\s+this\s+still\s+available|handover\s+date|ready\s+to\s+move|possession)", lowered):
            indicators.append(BuyingSignalIndicator.AVAILABILITY_INQUIRY)
            evidence_snippets.append("Availability / possession inquiry")

        # 6. Documentation / Title Deed
        if re.search(r"(title\s+deed|floor\s*plan|noc|developer\s+agreement|mou|form\s+f)", lowered):
            indicators.append(BuyingSignalIndicator.DOCUMENTATION_REQUEST)
            evidence_snippets.append("Documentation request")

        # 7. Negotiation / Price flexibility
        if re.search(r"(discount|last\s+price|negotiable|can\s+we\s+close\s+at)", lowered):
            indicators.append(BuyingSignalIndicator.NEGOTIATION_INQUIRY)
            evidence_snippets.append("Negotiation inquiry")

        # 8. Explicit purchase timeframe
        if re.search(r"(this\s+week|this\s+month|immediately|urgent|within\s+\d+\s+days)", lowered):
            indicators.append(BuyingSignalIndicator.EXPLICIT_TIMEFRAME)
            evidence_snippets.append("Explicit timeframe")

        # 9. Explicit willingness to proceed
        if re.search(r"(i\s+want\s+to\s+proceed|move\s+forward|send\s+offer|finalize)", lowered):
            indicators.append(BuyingSignalIndicator.EXPLICIT_WILLINGNESS)
            evidence_snippets.append("Willingness to proceed")

        # Evaluate Level
        if BuyingSignalIndicator.BOOKING_INQUIRY in indicators or (
            BuyingSignalIndicator.VIEWING_REQUEST in indicators and BuyingSignalIndicator.PAYMENT_DETAILS_REQUEST in indicators
        ):
            level = BuyingSignalLevel.VERY_HIGH
            confidence = 0.95
        elif len(indicators) >= 2 or BuyingSignalIndicator.VIEWING_REQUEST in indicators:
            level = BuyingSignalLevel.HIGH
            confidence = 0.88
        elif len(indicators) == 1:
            level = BuyingSignalLevel.MEDIUM
            confidence = 0.75
        elif re.search(r"(interested|like\s+this|send\s+more)", lowered):
            level = BuyingSignalLevel.LOW
            confidence = 0.60
            indicators.append(BuyingSignalIndicator.SIMILAR_PROPERTIES_REQUEST)
            evidence_snippets.append("General interest")
        else:
            level = BuyingSignalLevel.NONE
            confidence = 0.0

        return BuyingSignalDTO(
            level=level,
            indicators=indicators,
            evidence="; ".join(evidence_snippets) if evidence_snippets else None,
            confidence=confidence,
        )
