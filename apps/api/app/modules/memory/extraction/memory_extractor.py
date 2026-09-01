"""
Structured Memory Extraction Engine
====================================
Parses raw conversation messages, agent notes, and forms into validated memory candidates.
Enforces Pydantic schema validation and prevents unsupported AI hallucinations.
"""

import re
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class MemoryCandidateDTO(BaseModel):
    memory_type: str = Field(..., description="PREFERENCE | CONSTRAINT | NEGATIVE_PREFERENCE | INTENT | LOCATION | BUDGET | OBJECTION")
    key: str = Field(..., description="Canonical key, e.g. budget_max, bedrooms, locality")
    value_json: Dict[str, Any] = Field(default_factory=dict)
    value_text: str = Field(...)
    source_type: str = Field("CUSTOMER_STATED")
    confidence: float = Field(0.95, ge=0.0, le=1.0)
    importance: float = Field(0.80, ge=0.0, le=1.0)
    is_customer_safe: bool = Field(True)


class MemoryExtractor:
    """
    Extracts memory candidates from natural text and conversation events.
    """

    @classmethod
    def extract_candidates(cls, text: str, is_customer_message: bool = True) -> List[MemoryCandidateDTO]:
        candidates: List[MemoryCandidateDTO] = []
        clean = text.strip()
        source = "CUSTOMER_STATED" if is_customer_message else "AGENT_CONFIRMED"

        # 1. Budget Extraction (e.g. "under AED 2.5M", "budget 2,000,000", "max $1.5M")
        budget_match = re.search(r'(?:budget|under|max|around|up to)\s*(?:aed|inr|\$)?\s*([\d\.,]+)\s*(m|million|cr|crore|k)?', clean, re.IGNORECASE)
        if budget_match:
            raw_num = budget_match.group(1).replace(",", "")
            unit = (budget_match.group(2) or "").lower()
            try:
                val = float(raw_num)
                if unit in ("m", "million"):
                    val *= 1_000_000
                elif unit in ("cr", "crore"):
                    val *= 10_000_000
                elif unit == "k":
                    val *= 1_000

                candidates.append(MemoryCandidateDTO(
                    memory_type="CONSTRAINT",
                    key="budget_max",
                    value_json={"amount": val, "currency": "AED", "formatted": f"AED {val:,.0f}"},
                    value_text=f"Max budget: AED {val:,.0f}",
                    source_type=source,
                    confidence=0.98 if is_customer_message else 0.90,
                    importance=0.95
                ))
            except Exception:
                pass

        # 2. Bedrooms / BHK Extraction (e.g. "3 bedroom", "3-bedroom", "3BHK", "4-bed")
        bed_match = re.search(r'(\d+)[\s-]*(?:bhk|bed|bedroom|bedrooms|beds)', clean, re.IGNORECASE)
        if bed_match:
            beds = int(bed_match.group(1))
            candidates.append(MemoryCandidateDTO(
                memory_type="PREFERENCE",
                key="bedrooms",
                value_json={"bedrooms": beds},
                value_text=f"{beds} Bedrooms",
                source_type=source,
                confidence=0.98 if is_customer_message else 0.90,
                importance=0.90
            ))

        # 3. Location Extraction (e.g. "in Dubai Marina", "in Palm Jumeirah", "Downtown")
        for loc in ["Dubai Marina", "Downtown Dubai", "Palm Jumeirah", "Business Bay", "Dubai Hills", "Whitefield", "Indiranagar"]:
            if loc.lower() in clean.lower():
                candidates.append(MemoryCandidateDTO(
                    memory_type="LOCATION",
                    key="preferred_locality",
                    value_json={"locality": loc, "city": "Dubai" if "Dubai" in loc or "Palm" in loc or "Business" in loc else "Bangalore"},
                    value_text=f"Preferred area: {loc}",
                    source_type=source,
                    confidence=0.95 if is_customer_message else 0.88,
                    importance=0.85
                ))

        # 4. Negative Dislikes / Rejections (e.g. "don't want off-plan", "no ground floor")
        if "no off-plan" in clean.lower() or "don't want off-plan" in clean.lower() or "ready only" in clean.lower():
            candidates.append(MemoryCandidateDTO(
                memory_type="NEGATIVE_PREFERENCE",
                key="disliked_property_type",
                value_json={"disliked": "off_plan", "required": "ready_to_move"},
                value_text="Only ready-to-move properties (rejects off-plan)",
                source_type=source,
                confidence=0.95,
                importance=0.90
            ))

        # 5. Price Objection Extraction
        if "too expensive" in clean.lower() or "price is high" in clean.lower() or "over budget" in clean.lower():
            candidates.append(MemoryCandidateDTO(
                memory_type="OBJECTION",
                key="price_objection",
                value_json={"objection_type": "PRICE", "reason": "Customer expressed price is too high"},
                value_text="Customer stated property is over budget / too expensive",
                source_type=source,
                confidence=0.92,
                importance=0.88
            ))

        return candidates
