"""
Part 21.2A — Missing Information & Next Best Question Engine
==============================================================
Identifies critical, missing real estate qualification dimensions and
generates prioritized, sales-ready Next Best Questions for brokers.
"""
from typing import List, Dict, Any, Tuple
from app.modules.prospect_intelligence.dto.prospect_intelligence_dto import NextBestQuestionDTO, StrictLLMProspectExtractionDTO


# Canonical priority order of qualification questions by closing impact
QUALIFICATION_FIELD_METADATA = [
    {
        "field": "budget",
        "check": lambda data: not (data.budget_min or data.budget_max),
        "priority": 1,
        "question": "Could you share your approximate budget range for this property purchase?",
        "rationale": "Budget is the primary constraint required to filter viable inventory.",
    },
    {
        "field": "location",
        "check": lambda data: not data.location and not data.preferred_areas,
        "priority": 2,
        "question": "Which specific areas or communities do you prefer?",
        "rationale": "Geographic focus determines inventory alignment and broker specialization.",
    },
    {
        "field": "property_type_or_bedrooms",
        "check": lambda data: not data.property_type or data.bedrooms is None,
        "priority": 3,
        "question": "What property type and bedroom configuration are you looking for?",
        "rationale": "Unit layout requirements ensure precise property recommendations.",
    },
    {
        "field": "timeline",
        "check": lambda data: not data.timeline or data.timeline == "UNKNOWN",
        "priority": 4,
        "question": "What is your target move-in or investment timeline?",
        "rationale": "Timeline establishes prospect urgency and pipeline scheduling.",
    },
    {
        "field": "financing_method",
        "check": lambda data: not data.financing or data.financing == "UNKNOWN",
        "priority": 5,
        "question": "Will you be purchasing via cash funds or bank mortgage financing?",
        "rationale": "Financing readiness impacts transaction closing velocity.",
    },
    {
        "field": "purpose",
        "check": lambda data: not data.purpose or data.purpose == "UNKNOWN",
        "priority": 6,
        "question": "Are you purchasing for personal residence (end-use) or rental investment yield?",
        "rationale": "Buyer motivation determines whether ROI yield or lifestyle amenities are prioritized.",
    },
    {
        "field": "ready_vs_offplan",
        "check": lambda data: not data.ready_or_off_plan,
        "priority": 7,
        "question": "Are you interested in ready-to-move-in properties or high-growth off-plan projects?",
        "rationale": "Clarifies payment plan vs immediate handover requirements.",
    },
]


class MissingInformationEngine:
    """
    Evaluates extracted prospect data and identifies material qualification gaps.
    """

    @classmethod
    def evaluate(
        cls, extraction: StrictLLMProspectExtractionDTO
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """
        Returns:
            missing_fields: List of string field names that are missing.
            next_best_questions: List of ranked NextBestQuestionDTO dicts.
        """
        missing_fields: List[str] = []
        questions: List[Dict[str, Any]] = []

        for item in QUALIFICATION_FIELD_METADATA:
            if item["check"](extraction):
                missing_fields.append(item["field"])
                questions.append({
                    "field": item["field"],
                    "question": item["question"],
                    "priority": item["priority"],
                    "business_rationale": item["rationale"],
                })

        # Sort strictly by priority
        questions.sort(key=lambda q: q["priority"])
        return missing_fields, questions
