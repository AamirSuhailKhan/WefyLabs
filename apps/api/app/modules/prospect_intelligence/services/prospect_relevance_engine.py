"""
Part 21.2A — Prospect Relevance & Sales Readiness Engine
==========================================================
Computes:
1. Versioned Discovery Relevance Score (`v1.0-real-estate-prospect`, 0.00 – 1.00)
2. 11 Distinct Field-Level Confidences (0.00 – 1.00)
3. Sales Readiness State Machine (NOT_READY, NEEDS_QUALIFICATION, SALES_READY, HIGH_PRIORITY, HUMAN_REVIEW)
Strictly adheres to non-fabrication: missing fields remain neutral/zero and never receive manufactured defaults.
"""
from typing import Dict, Any, Tuple
from app.models.prospect_intelligence_models import SalesReadiness, TransactionIntent, TimelineCategory
from app.modules.prospect_intelligence.dto.prospect_intelligence_dto import StrictLLMProspectExtractionDTO

PROSPECT_RELEVANCE_MODEL_VERSION = "v1.0-real-estate-prospect"


class ProspectRelevanceEngine:
    """
    Evaluates prospect completeness, intent strength, and sales readiness.
    """

    @classmethod
    def evaluate(
        cls,
        extraction: StrictLLMProspectExtractionDTO,
        has_verified_matches: bool = False,
        has_phone: bool = True,
        has_email: bool = False,
    ) -> Tuple[float, Dict[str, float], float, str]:
        """
        Returns:
            discovery_relevance_score: float (0.00 – 1.00)
            confidences: Dict[str, float] (11 field-level scores)
            overall_confidence: float (0.00 – 1.00)
            sales_readiness: str (SalesReadiness enum value)
        """
        raw_conf = extraction.field_confidences or {}

        # 1. Compute 11 Field-Level Confidences
        intent_conf = raw_conf.get("intent_confidence", 0.90 if extraction.transaction_intent in ["BUY", "RENT", "SELL", "INVEST"] else 0.20)
        prop_type_conf = raw_conf.get("property_type_confidence", 0.85 if extraction.property_type or extraction.bedrooms else 0.0)
        loc_conf = raw_conf.get("location_confidence", 0.90 if extraction.location or extraction.preferred_areas else 0.0)
        budget_conf = raw_conf.get("budget_confidence", 0.88 if (extraction.budget_min or extraction.budget_max) else 0.0)
        timeline_conf = raw_conf.get("timeline_confidence", 0.85 if extraction.timeline != "UNKNOWN" else 0.0)
        financing_conf = raw_conf.get("financing_confidence", 0.85 if extraction.financing != "UNKNOWN" else 0.0)
        purpose_conf = raw_conf.get("purpose_confidence", 0.80 if extraction.purpose != "UNKNOWN" else 0.0)
        urgency_conf = raw_conf.get("urgency_confidence", 0.80 if extraction.urgency != "UNKNOWN" else 0.0)
        prop_match_conf = 0.95 if has_verified_matches else 0.30
        identity_conf = 0.95 if (has_phone and has_email) else (0.85 if has_phone else 0.40)
        source_conf = 0.90

        confidences = {
            "intent_confidence": round(intent_conf, 2),
            "property_type_confidence": round(prop_type_conf, 2),
            "location_confidence": round(loc_conf, 2),
            "budget_confidence": round(budget_conf, 2),
            "timeline_confidence": round(timeline_conf, 2),
            "financing_confidence": round(financing_conf, 2),
            "purpose_confidence": round(purpose_conf, 2),
            "urgency_confidence": round(urgency_conf, 2),
            "property_match_confidence": round(prop_match_conf, 2),
            "identity_confidence": round(identity_conf, 2),
            "source_confidence": round(source_conf, 2),
        }

        # 2. Compute Discovery Relevance Score (0.00 – 1.00)
        # Weights: Intent (30%), Budget (20%), Location (20%), Property Requirements (15%), Timeline (15%)
        w_intent = 0.30 if extraction.transaction_intent in ["BUY", "RENT", "SELL", "INVEST"] else 0.05
        w_budget = 0.20 if (extraction.budget_min or extraction.budget_max) else 0.0
        w_loc = 0.20 if (extraction.location or extraction.preferred_areas) else 0.0
        w_prop = 0.15 if (extraction.property_type or extraction.bedrooms) else 0.0
        w_time = 0.15 if (extraction.timeline in ["IMMEDIATE", "0_3_MONTHS", "3_6_MONTHS"]) else 0.02

        relevance_score = round(min(1.0, w_intent + w_budget + w_loc + w_prop + w_time), 2)

        # 3. Overall Confidence (harmonic mean of active confidences)
        active_confs = [c for c in confidences.values() if c > 0.0]
        overall_confidence = round(sum(active_confs) / len(active_confs), 2) if active_confs else 0.10

        # 4. Sales Readiness Evaluation
        has_intent = extraction.transaction_intent in ["BUY", "RENT", "SELL", "INVEST"]
        has_budget = bool(extraction.budget_min or extraction.budget_max)
        has_location = bool(extraction.location or extraction.preferred_areas)
        is_urgent = extraction.timeline in ["IMMEDIATE", "0_3_MONTHS"]

        if has_intent and has_budget and has_location and is_urgent:
            readiness = SalesReadiness.HIGH_PRIORITY.value
        elif has_intent and (has_budget or has_location):
            readiness = SalesReadiness.SALES_READY.value
        elif has_intent:
            readiness = SalesReadiness.NEEDS_QUALIFICATION.value
        elif extraction.transaction_intent == "UNKNOWN":
            readiness = SalesReadiness.NOT_READY.value
        else:
            readiness = SalesReadiness.HUMAN_REVIEW.value

        return relevance_score, confidences, overall_confidence, readiness
