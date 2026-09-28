"""
Master Build 06 — AI Sales Agent Objection Intelligence Layer
============================================================
Detects customer objections, classifies into controlled categories,
and executes the 5-step consultative response framework:
  ACKNOWLEDGE → CLARIFY → ADDRESS → VERIFY → NEXT_STEP

CRITICAL SAFETY GUARANTEES:
  1. ZERO FALSE SCARCITY: Never manufacture urgency ("only 1 unit left", "prices increase tomorrow").
  2. ZERO FABRICATED DISCOUNTS: Never promise unapproved discounts.
  3. REAL INVENTORY ALTERNATIVES: Price objections trigger structured searches for lower-priced
     configurations, flexible payment plans, or location trade-offs.
  4. FACT-BASED COMPETITOR HANDLING: Never attack competitors or invent comparisons.
"""
from __future__ import annotations

import enum
import re
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── 1. Objection Categories (Section 22) ────────────────────────────────────

class ObjectionCategory(str, enum.Enum):
    PRICE = "PRICE"
    LOCATION = "LOCATION"
    TRUST = "TRUST"
    TIMELINE = "TIMELINE"
    FINANCING = "FINANCING"
    PROPERTY = "PROPERTY"
    DEVELOPER = "DEVELOPER"
    COMPETITOR = "COMPETITOR"
    FAMILY_DECISION = "FAMILY_DECISION"
    UNCERTAINTY = "UNCERTAINTY"
    NO_URGENCY = "NO_URGENCY"


# ─── 2. Classification Patterns ──────────────────────────────────────────────

_OBJECTION_PATTERNS: List[Tuple[ObjectionCategory, re.Pattern]] = [
    (
        ObjectionCategory.PRICE,
        re.compile(
            r"\b(?:too\s+expensive|high\s+price|out\s+of\s+budget|over\s+budget|costs?\s+too\s+much|"
            r"cannot\s+afford|can't\s+afford|lower\s+price|any\s+discount|cheaper|rates?\s+are\s+high|"
            r"price\s+is\s+too\s+high|negotiable|less\s+expensive)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObjectionCategory.FINANCING,
        re.compile(
            r"\b(?:loan\s+(?:is\s+)?(?:not\s+approved|rejected)|mortgage|down\s+payment|interest\s+rates?|"
            r"bank\s+approval|need\s+financing|emi\s+is\s+too\s+high|payment\s+plan)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObjectionCategory.LOCATION,
        re.compile(
            r"\b(?:too\s+far|far\s+away|bad\s+location|traffic\s+is\s+bad|remote\s+area|"
            r"not\s+in\s+my\s+preferred\s+area|distance\s+is\s+too\s+much|connectivity\s+poor)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObjectionCategory.FAMILY_DECISION,
        re.compile(
            r"\b(?:discuss\s*(?:this\s*)?with\s+(?:my\s+)?(?:wife|husband|spouse|family|parents|partner)|"
            r"ask\s+(?:my\s+)?(?:wife|husband|spouse|family|parents|partner)|family\s+decision)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObjectionCategory.TIMELINE,
        re.compile(
            r"\b(?:possession\s+is\s+too\s+late|delayed\s+possession|need\s+immediate\s+move|"
            r"completion\s+date\s+is\s+too\s+far|cannot\s+wait\s+that\s+long|ready\s+to\s+move\s+only|"
            r"(?:only\s+)?buy\s+next\s+year|next\s+year)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObjectionCategory.TRUST,
        re.compile(
            r"\b(?:is\s+this\s+legit|scam|trustworthy|rera\s+registered|fake|hidden\s+charges|"
            r"hidden\s+costs|is\s+developer\s+reliable|fraud|legal\s+dispute|genuine|litigation|"
            r"court\s+case|title\s+clear|land\s+dispute|is\s+this\s+builder\s+genuine)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObjectionCategory.DEVELOPER,
        re.compile(
            r"\b(?:builder\s+reputation|developer\s+history|builder\s+delayed|developer\s+track\s+record)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObjectionCategory.COMPETITOR,
        re.compile(
            r"\b(?:better\s+deal\s+at|compared\s+to|project\s+[A-Za-z0-9]+\s+is\s+cheaper|"
            r"other\s+developer\s+offers?|another\s+agent\s+offered|dlf|godrej|sobha|emaar|competitor|"
            r"offering\s+better)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObjectionCategory.NO_URGENCY,
        re.compile(
            r"\b(?:just\s+browsing|just\s+looking|not\s+in\s+a\s+hurry|no\s+rush|"
            r"maybe\s+later|thinking\s+about\s+it|sometime\s+in\s+the\s+future)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObjectionCategory.UNCERTAINTY,
        re.compile(
            r"\b(?:not\s+sure|confused|market\s+is\s+volatile|waiting\s+for\s+prices\s+to\s+drop|"
            r"hesitant|second\s+thoughts|too\s+risky)\b",
            re.IGNORECASE,
        ),
    ),
    (
        ObjectionCategory.PROPERTY,
        re.compile(
            r"\b(?:rooms?\s*(?:sizes?|s)?\s*(?:and\s+layout\s+)?(?:are\s+)?too\s+small|layout\s+is\s+bad|"
            r"poor\s+construction|no\s+balcony|low\s+floor|view\s+is\s+not\s+good|amenities\s+missing|carpet\s+area\s+small)\b",
            re.IGNORECASE,
        ),
    ),
]

# Patterns of deceptive urgency / scarcity that AI must NEVER use
_FORBIDDEN_SCARCITY_PATTERNS = [
    re.compile(r"\b(?:only\s+1\s+unit\s+left|last\s+chance|prices?\s+(?:are\s+definitely\s+)?increase|prices?\s+increase\s+tomorrow|prices?\s+are\s+definitely\s+increasing\s+tomorrow)\b", re.IGNORECASE),
    re.compile(r"\b(?:book\s+today\s+or\s+(?:you'll\s+)?lose\s+it|another\s+buyer\s+is\s+making\s+an\s+offer|if\s+you\s+do\s+not\s+book\s+now)\b", re.IGNORECASE),
    re.compile(r"\b(?:special\s+discount|exclusive\s+(?:secret\s+)?discount|secret\s+discount|flash\s+sale|discount\s+just\s+for\s+you)\b", re.IGNORECASE),
]


# ─── 3. DTOs ──────────────────────────────────────────────────────────────────

@dataclass
class ObjectionAnalysis:
    detected: bool
    category: Optional[ObjectionCategory] = None
    matched_phrase: Optional[str] = None
    confidence: float = 0.0


@dataclass
class ObjectionResponseDTO:
    category: ObjectionCategory
    acknowledge: str
    clarify: str
    address: str
    verify: str
    next_step: str
    composed_message: str
    alternative_search_params: Optional[Dict[str, Any]] = None

    @property
    def objection_category(self) -> ObjectionCategory:
        return self.category


# ─── 4. Objection Intelligence Engine ─────────────────────────────────────────

class ObjectionIntelligenceEngine:
    """
    Identifies customer objections and formulates consultative responses
    using the 5-step framework without manufactured pressure.
    """

    def analyze(self, customer_message: str) -> ObjectionAnalysis:
        """Classifies customer message against objection taxonomies."""
        if not customer_message:
            return ObjectionAnalysis(detected=False)

        for category, pattern in _OBJECTION_PATTERNS:
            match = pattern.search(customer_message)
            if match:
                return ObjectionAnalysis(
                    detected=True,
                    category=category,
                    matched_phrase=match.group(0),
                    confidence=0.9,
                )

        return ObjectionAnalysis(detected=False)

    def formulate_response(
        self,
        analysis: ObjectionAnalysis,
        current_property: Optional[Dict[str, Any]] = None,
        qualification_facts: Optional[Dict[str, Any]] = None,
    ) -> ObjectionResponseDTO:
        """
        Builds a 5-step consultative response respecting WefyLabs safety rules.
        """
        cat = analysis.category or ObjectionCategory.UNCERTAINTY
        facts = qualification_facts or {}
        prop = current_property or {}

        alt_params: Optional[Dict[str, Any]] = None

        if cat == ObjectionCategory.PRICE:
            budget = facts.get("budget_max") or prop.get("price")
            acknowledge = "I completely understand that budget alignment is paramount."
            clarify = "Are you looking for options strictly under a specific figure, or would a more flexible payment plan help?"
            address = (
                "We have verified properties in nearby emerging sectors that offer similar layouts at a lower price point, "
                "as well as developer-backed linked payment schedules."
            )
            verify = "Would you like me to share verified inventory that fits within that comfortable range?"
            next_step = "I can filter for units with lower starting prices immediately."
            
            # Setup real search parameters for alternatives
            alt_params = {
                "budget_max": float(budget) * 0.85 if budget else None,
                "max_price": float(budget) * 0.85 if budget else None,
                "property_type": facts.get("property_type") or prop.get("property_type"),
                "bedrooms": facts.get("bedrooms") or prop.get("bedrooms"),
            }

        elif cat == ObjectionCategory.LOCATION:
            acknowledge = "Location convenience and daily connectivity make a huge difference in living quality."
            clarify = "What are the primary focal points for your commute or preferred schools/workplaces?"
            address = "We can evaluate projects positioned near major arterial roads or upcoming metro corridors."
            verify = "Would exploring a 5–10 minute radius adjustment be acceptable if the project offers superior amenities?"
            next_step = "Let me adjust our geographic filter to focus closer to your primary transit hubs."

        elif cat == ObjectionCategory.FAMILY_DECISION:
            acknowledge = "Purchasing a home is a shared family journey and taking time to align together is essential."
            clarify = "Would it help if I compiled a comprehensive brochure and video walkthrough you can share with your family?"
            address = "I can package the floor plans, verified pricing, and amenity overview into a clean summary."
            verify = "Does that give everyone the details needed to discuss comfortably?"
            next_step = "Take all the time you need, and feel free to reach out whenever you're ready to review together."

        elif cat == ObjectionCategory.TIMELINE:
            acknowledge = "Moving timelines and possession certainty are critical for planning."
            clarify = "Are you seeking ready-to-move-in homes, or possession within 6–12 months?"
            address = "We distinguish between ready-to-move inventory with immediate handover and under-construction milestones."
            verify = "Should we focus solely on ready-to-move units to eliminate handover uncertainty?"
            next_step = "I will restrict our property shortlist strictly to ready or near-completion homes."
            alt_params = {"possession_status": "READY_TO_MOVE"}

        elif cat == ObjectionCategory.TRUST:
            acknowledge = "Trust, legal diligence, and developer track record are non-negotiable in real estate."
            clarify = "Would you like to review the official RERA registration details and verified land title approvals?"
            address = "All properties presented on our platform carry verified RERA numbers and audited developer delivery histories."
            verify = "Does seeing the legal documentation give you peace of mind?"
            next_step = "I can connect you with our legal compliance advisor to walk through the paperwork."

        elif cat == ObjectionCategory.FINANCING:
            acknowledge = "Securing smooth financing with favorable rates is an important part of the decision."
            clarify = "Have you begun pre-approval with any bank, or are you exploring structured construction-linked plans?"
            address = "Many developers offer subsidized subvention schemes or tie-ups with leading financial institutions."
            verify = "Would you like an overview of verified payment schedule milestones?"
            next_step = "We can have our home loan specialist outline transparent EMI projections for you."

        else:
            acknowledge = "I understand you have considerations and want to be completely confident before moving forward."
            clarify = "What specific aspect would bring the greatest clarity for you right now?"
            address = "We prioritize verified facts and complete transparency so you can make decisions at your own pace."
            verify = "Does that feel like a helpful direction?"
            next_step = "I am here to answer any specific questions whenever you are ready."

        composed = f"{acknowledge} {clarify} {address} {verify} {next_step}"

        # Sanitize composed message to strictly guarantee NO false scarcity
        for pattern in _FORBIDDEN_SCARCITY_PATTERNS:
            if pattern.search(composed):
                composed = re.sub(pattern, "", composed).strip()

        return ObjectionResponseDTO(
            category=cat,
            acknowledge=acknowledge,
            clarify=clarify,
            address=address,
            verify=verify,
            next_step=next_step,
            composed_message=composed,
            alternative_search_params=alt_params,
        )

    def build_governed_response(
        self,
        analysis: ObjectionAnalysis,
        current_property: Optional[Dict[str, Any]] = None,
        qualification_facts: Optional[Dict[str, Any]] = None,
    ) -> ObjectionResponseDTO:
        return self.formulate_response(
            analysis=analysis,
            current_property=current_property,
            qualification_facts=qualification_facts,
        )

    def verify_response_safety(self, text: str) -> Tuple[bool, Optional[str]]:
        for pattern in _FORBIDDEN_SCARCITY_PATTERNS:
            match = pattern.search(text)
            if match:
                return False, f"Prohibited scarcity or manipulation detected: '{match.group(0)}'"
        return True, None

    def get_alternative_search_params(
        self,
        analysis: ObjectionAnalysis,
        current_budget: Optional[float] = None,
    ) -> Dict[str, Any]:
        max_p = float(current_budget) * 0.85 if current_budget else 10000000
        return {
            "max_price": max_p,
            "allow_alternative_sectors": True,
            "allow_smaller_configuration": True,
        }
