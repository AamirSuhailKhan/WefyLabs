"""
Part 21.7 — Customer Objection Detector
=======================================
Extracts structured objection categories:
- PRICE: too expensive, over budget, high service charges
- LOCATION: too far, bad traffic, undesirable neighborhood
- PROPERTY_SIZE: too small, not enough space, cramped
- PROPERTY_TYPE: want villa not apartment, low floor, no balcony
- AMENITIES: no pool, no gym, no parking
- PAYMENT_TERMS: down payment too high, too many cheques
- FINANCING: mortgage rejected, high interest rate
- TIMELINE: completion too late, handover delayed
- TRUST / DEVELOPER: unknown developer, delayed past projects
- AVAILABILITY / POSSESSION: already sold, tenant occupied
"""
from __future__ import annotations

import re
import logging
from typing import List, Optional

from app.modules.conversation_intelligence.taxonomies import (
    ObjectionCategory,
    ObjectionSeverity,
)
from app.modules.conversation_intelligence.dto import ObjectionDTO

logger = logging.getLogger(__name__)


class ObjectionDetector:
    """Detects and categorizes customer objections from conversation text."""

    @staticmethod
    def detect_objections(text: str, source_message_id: Optional[str] = None) -> List[ObjectionDTO]:
        if not text or not text.strip():
            return []

        lowered = text.lower()
        objections: List[ObjectionDTO] = []

        # 1. PRICE
        if re.search(r"(too\s+(expensive|high|pricey|much)|out\s+of\s+(my\s+)?budget|can'?t\s+afford|over\s+priced|budget\s+is\s+only)", lowered):
            objections.append(
                ObjectionDTO(
                    category=ObjectionCategory.PRICE,
                    severity=ObjectionSeverity.HIGH,
                    evidence="Price / budget exceeded statement",
                    confidence=0.94,
                    source_message_id=source_message_id,
                )
            )

        # 2. LOCATION
        if re.search(r"(too\s+far|don'?t\s+like\s+(the\s+)?(area|location|community)|traffic\s+is\s+bad|not\s+in\s+my\s+preferred\s+area)", lowered):
            objections.append(
                ObjectionDTO(
                    category=ObjectionCategory.LOCATION,
                    severity=ObjectionSeverity.MEDIUM,
                    evidence="Location suitability objection",
                    confidence=0.88,
                    source_message_id=source_message_id,
                )
            )

        # 3. PROPERTY SIZE / BEDROOMS
        if re.search(r"(too\s+small|cramped|need\s+bigger|not\s+enough\s+(space|bedrooms|rooms)|small\s+layout)", lowered):
            objections.append(
                ObjectionDTO(
                    category=ObjectionCategory.PROPERTY_SIZE,
                    severity=ObjectionSeverity.MEDIUM,
                    evidence="Size / layout objection",
                    confidence=0.89,
                    source_message_id=source_message_id,
                )
            )

        # 4. PAYMENT TERMS
        if re.search(r"(down\s*payment\s+is\s+too\s+high|payment\s+plan\s+is\s+tight|cannot\s+pay\s+in\s+\d\s+cheques)", lowered):
            objections.append(
                ObjectionDTO(
                    category=ObjectionCategory.PAYMENT_TERMS,
                    severity=ObjectionSeverity.HIGH,
                    evidence="Payment terms objection",
                    confidence=0.90,
                    source_message_id=source_message_id,
                )
            )

        # 5. TIMELINE / HANDOVER
        if re.search(r"(handover\s+is\s+too\s+late|cannot\s+wait\s+till|need\s+immediate\s+move\s*in|too\s+long\s+to\s+complete)", lowered):
            objections.append(
                ObjectionDTO(
                    category=ObjectionCategory.TIMELINE,
                    severity=ObjectionSeverity.MEDIUM,
                    evidence="Timeline / completion objection",
                    confidence=0.87,
                    source_message_id=source_message_id,
                )
            )

        # 6. FINANCING / MORTGAGE
        if re.search(r"(mortgage\s+(denied|rejected|issues)|loan\s+problem|bank\s+valuation)", lowered):
            objections.append(
                ObjectionDTO(
                    category=ObjectionCategory.FINANCING,
                    severity=ObjectionSeverity.HIGH,
                    evidence="Financing / mortgage objection",
                    confidence=0.92,
                    source_message_id=source_message_id,
                )
            )

        # 7. AMENITIES
        if re.search(r"(no\s+balcony|no\s+parking|no\s+pool|no\s+gym|missing\s+amenit)", lowered):
            objections.append(
                ObjectionDTO(
                    category=ObjectionCategory.AMENITIES,
                    severity=ObjectionSeverity.LOW,
                    evidence="Missing amenities objection",
                    confidence=0.85,
                    source_message_id=source_message_id,
                )
            )

        return objections
