"""
Part 21.7 — Negotiation & Price Flexibility Detector
=====================================================
Detects customer price negotiation attempts, requested discounts,
counter-offers, and fee waiver requests.
Guarantees:
- If a customer requests a discount, never promises or authorizes it.
- Flags requires_human_approval = True.
"""
from __future__ import annotations

import re
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

from app.modules.conversation_intelligence.taxonomies import NegotiationDirection
from app.modules.conversation_intelligence.dto import NegotiationSignalDTO

logger = logging.getLogger(__name__)


class NegotiationDetector:
    """Detects price negotiation and discount requests."""

    @staticmethod
    def detect_negotiation(text: str) -> NegotiationSignalDTO:
        if not text or not text.strip():
            return NegotiationSignalDTO(is_negotiating=False)

        lowered = text.lower()
        is_negotiating = False
        direction = NegotiationDirection.NONE
        requested_price: Optional[Decimal] = None
        discount_percentage: Optional[float] = None
        evidence = None

        # 1. Direct Discount Request
        disc_match = re.search(r"(\d+)%\s+discount", lowered)
        if disc_match:
            is_negotiating = True
            direction = NegotiationDirection.DISCOUNT_REQUEST
            discount_percentage = float(disc_match.group(1))
            evidence = disc_match.group(0)

        elif re.search(r"(any\s+discount|reduce\s+the\s+price|is\s+the\s+price\s+negotiable|negotiable|last\s+price|best\s+offer)", lowered):
            is_negotiating = True
            direction = NegotiationDirection.DISCOUNT_REQUEST
            evidence = "Discount request"

        # 2. Counter-offer / Specific target price
        # e.g., "Can you do 1.8M?", "I can close at 1.9M", "Offer is 1.85 million"
        price_match = re.search(
            r"(?:can\s+you\s+do|i\s+can\s+offer|close\s+at|offer\s+is|give\s+it\s+for|can\s+the\s+owner\s+do)\s+(?:aed|inr|\$)?\s*(\d+(?:\.\d+)?)\s*(m|million|k|lakh|cr)?",
            lowered,
        )
        if price_match:
            is_negotiating = True
            direction = NegotiationDirection.COUNTER_OFFER
            num_val = float(price_match.group(1))
            unit = (price_match.group(2) or "").lower()
            multiplier = 1
            if unit in ("m", "million"):
                multiplier = 1_000_000
            elif unit in ("k", "thousand"):
                multiplier = 1_000
            elif unit == "cr":
                multiplier = 10_000_000
            elif unit == "lakh":
                multiplier = 100_000
            elif num_val < 100 and not unit:
                # e.g. "1.8" -> 1.8M in real estate context
                multiplier = 1_000_000

            try:
                requested_price = Decimal(str(int(num_val * multiplier)))
            except (InvalidOperation, ValueError):
                pass
            evidence = price_match.group(0)

        # 3. Payment Plan negotiation
        elif re.search(r"(post\s*handover\s+payment\s+plan|flexible\s+payment\s+terms|more\s+cheques)", lowered):
            is_negotiating = True
            direction = NegotiationDirection.PAYMENT_PLAN_REQUEST
            evidence = "Payment plan negotiation"

        # 4. Fee / DLD Waiver
        elif re.search(r"(waive\s+(dld|commission|service\s+charge)|zero\s+commission|free\s+dld)", lowered):
            is_negotiating = True
            direction = NegotiationDirection.WAIVER_REQUEST
            evidence = "Fee waiver request"

        return NegotiationSignalDTO(
            is_negotiating=is_negotiating,
            direction=direction,
            requested_price=requested_price,
            discount_percentage=discount_percentage,
            currency="AED",
            evidence=evidence,
            confidence=0.92 if is_negotiating else 0.0,
            requires_human_approval=is_negotiating,
        )
