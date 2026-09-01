"""
Part 21.7 — Human Handoff & Escalation Service
==============================================
Evaluates when human intervention is mandatory and compiles a structured
HumanHandoffBriefDTO for the broker.

Escalation Triggers:
1. COMPLAINT / Customer Dissatisfaction
2. LEGAL_RISK / Regulatory concerns
3. AGGRESSIVE_NEGOTIATION / Price concession request
4. CUSTOMER_REQUEST / Explicit human agent request
5. HIGH_VALUE_TRANSACTION / Luxury Tier
6. QUALIFICATION_CONFLICT / Contradictory critical facts
7. CONTRACT_DOCUMENT_REQUEST
"""
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from app.modules.conversation_intelligence.taxonomies import (
    CustomerIntent,
    HandoffTrigger,
    ObjectionSeverity,
)
from app.modules.conversation_intelligence.dto import (
    HumanHandoffBriefDTO,
    ExtractedIntentDTO,
    BuyingSignalDTO,
    ObjectionDTO,
    NegotiationSignalDTO,
    ExtractedQualificationUpdateDTO,
)

logger = logging.getLogger(__name__)


class HumanHandoffService:
    """Evaluates escalation conditions and compiles comprehensive sales briefs."""

    @staticmethod
    def evaluate_escalation(
        intents: List[ExtractedIntentDTO],
        objections: List[ObjectionDTO],
        negotiation: NegotiationSignalDTO,
        is_luxury_or_high_value: bool = False,
    ) -> Tuple[bool, HandoffTrigger, str]:
        """
        Determines if human handoff is required and returns the primary trigger.
        """
        intent_types = [i.intent for i in intents]

        # 1. Legal Risk
        if CustomerIntent.LEGAL_RISK in intent_types:
            return True, HandoffTrigger.LEGAL_RISK, "Customer mentioned legal or regulatory action"

        # 2. Complaint
        if CustomerIntent.COMPLAINT in intent_types:
            return True, HandoffTrigger.COMPLAINT, "Customer expressed dissatisfaction or submitted a complaint"

        # 3. Explicit Human Request
        if CustomerIntent.HUMAN_AGENT_REQUEST in intent_types:
            return True, HandoffTrigger.CUSTOMER_REQUEST, "Customer explicitly requested to speak with a human agent"

        # 4. Price Negotiation / Discount
        if negotiation.is_negotiating:
            return True, HandoffTrigger.AGGRESSIVE_NEGOTIATION, f"Customer initiated price negotiation: {negotiation.evidence}"

        # 5. High-Value / Luxury Lead
        if is_luxury_or_high_value:
            return True, HandoffTrigger.HIGH_VALUE_TRANSACTION, "High-value enterprise lead requires senior broker oversight"

        # 6. Severe Objection
        for obj in objections:
            if obj.severity == ObjectionSeverity.HIGH:
                return True, HandoffTrigger.CUSTOMER_DISSATISFACTION, f"Severe {obj.category.value} objection detected"

        return False, HandoffTrigger.NONE, "No escalation required"

    @staticmethod
    def build_brief(
        lead_id: str,
        organization_id: str,
        trigger: HandoffTrigger,
        customer_message: str,
        intents: List[ExtractedIntentDTO],
        buying_signal: BuyingSignalDTO,
        objections: List[ObjectionDTO],
        negotiation: NegotiationSignalDTO,
        qualification_update: Optional[ExtractedQualificationUpdateDTO],
        recommended_action: str,
        reason: str,
    ) -> HumanHandoffBriefDTO:
        """Constructs an actionable HumanHandoffBriefDTO for the broker."""
        detected_intents = [i.intent for i in intents]

        summary_parts = [f"Trigger: {trigger.value} ({reason})"]
        if buying_signal.level.value in ("VERY_HIGH", "HIGH"):
            summary_parts.append(f"High buying intent detected: {buying_signal.evidence}")
        if negotiation.is_negotiating:
            summary_parts.append(f"Negotiation offer: {negotiation.evidence}")
        if objections:
            obj_str = ", ".join([o.category.value for o in objections])
            summary_parts.append(f"Active objections: {obj_str}")

        summary = ". ".join(summary_parts)

        qual_dict = qualification_update.model_dump(exclude_none=True) if qualification_update else {}

        return HumanHandoffBriefDTO(
            lead_id=lead_id,
            organization_id=organization_id,
            trigger=trigger,
            urgency="URGENT" if trigger in (HandoffTrigger.LEGAL_RISK, HandoffTrigger.COMPLAINT) else "HIGH",
            summary=summary,
            customer_message=customer_message,
            detected_intents=detected_intents,
            buying_signal=buying_signal,
            objections=objections,
            qualification_changes=qual_dict,
            recommended_action=recommended_action,
            evidence=customer_message[:500],
        )
