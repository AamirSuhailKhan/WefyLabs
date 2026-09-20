"""
Provenance & Source Evidence Tracker
=====================================
Defines provenance tiers, default confidence scores, and source validation rules:
- CUSTOMER_STATED: 0.95 - 0.99 (Highest Priority)
- AGENT_CONFIRMED: 0.90
- CRM_VERIFIED: 0.92
- BEHAVIORAL_SIGNAL: 0.75 - 0.85
- AI_INFERRED: 0.50 - 0.65
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PROVENANCE_HIERARCHY: Dict[str, int] = {
    "EXPLICIT": 100,
    "CUSTOMER_STATED": 100,
    "AGENT_CONFIRMED": 90,
    "CRM": 85,
    "CRM_VERIFIED": 85,
    "IMPORTED": 80,
    "SYSTEM": 75,
    "BEHAVIORAL_SIGNAL": 60,
    "INFERRED": 40,
    "AI_INFERRED": 40,
    "UNKNOWN": 10
}

DEFAULT_CONFIDENCE: Dict[str, float] = {
    "EXPLICIT": 1.00,
    "CUSTOMER_STATED": 0.98,
    "AGENT_CONFIRMED": 0.90,
    "CRM": 0.92,
    "CRM_VERIFIED": 0.92,
    "IMPORTED": 0.85,
    "SYSTEM": 0.80,
    "BEHAVIORAL_SIGNAL": 0.80,
    "INFERRED": 0.60,
    "AI_INFERRED": 0.60,
    "UNKNOWN": 0.30
}

class ProvenanceTracker:
    """
    Validates source evidence and enforces priority hierarchy.
    """

    @classmethod
    def get_source_rank(cls, source_type: str) -> int:
        return PROVENANCE_HIERARCHY.get(source_type.upper().strip(), 10)

    @classmethod
    def get_default_confidence(cls, source_type: str) -> float:
        return DEFAULT_CONFIDENCE.get(source_type.upper().strip(), 0.50)

    @classmethod
    def can_source_override(cls, new_source: str, existing_source: str) -> bool:
        """
        Determines whether a new memory source has sufficient rank to supersede an existing active memory.
        AI inferences can NEVER override explicit customer statements.
        """
        new_rank = cls.get_source_rank(new_source)
        existing_rank = cls.get_source_rank(existing_source)
        return new_rank >= existing_rank
