"""
Part 21.2A — Sales Intelligence Brief & Next Best Action Generator
====================================================================
Synthesizes a structured, concise sales briefing for brokers and determines the
highest-impact Next Best Action grounded in extracted evidence.
"""
from typing import Dict, Any, List, Optional
from app.models.prospect_intelligence_models import NextBestActionType, SalesReadiness
from app.modules.prospect_intelligence.dto.prospect_intelligence_dto import (
    StrictLLMProspectExtractionDTO, SalesBriefDTO
)


class SalesBriefGenerator:
    """
    Grounded Sales Brief & Action Recommendation Engine.
    """

    @classmethod
    def generate_brief(
        cls,
        extraction: StrictLLMProspectExtractionDTO,
        matched_properties: List[Dict[str, Any]],
        missing_fields: List[str],
        sales_readiness: str,
        overall_confidence: float,
    ) -> Tuple[Dict[str, Any], str, str]:
        """
        Returns:
            brief_dict: Dict representation of SalesBriefDTO
            next_best_action: NextBestActionType enum string
            action_reason: Detailed rationale
        """
        # 1. Headline
        intent = extraction.transaction_intent if extraction.transaction_intent != "UNKNOWN" else "PROPERTY"
        prop_str = f"{extraction.bedrooms}BHK " if extraction.bedrooms else ""
        type_str = extraction.property_type.title() if extraction.property_type else "Real Estate"
        loc_str = f"in {extraction.location}" if extraction.location else ""

        if sales_readiness == SalesReadiness.HIGH_PRIORITY.value:
            headline = f"🔥 HIGH-INTENT {prop_str}{type_str.upper()} {intent} {loc_str}".strip()
        elif sales_readiness == SalesReadiness.SALES_READY.value:
            headline = f"QUALIFIED {prop_str}{type_str.upper()} {intent} {loc_str}".strip()
        elif sales_readiness == SalesReadiness.NEEDS_QUALIFICATION.value:
            headline = f"ACTIVE INQUIRY — {prop_str}{type_str.upper()} {intent}".strip()
        else:
            headline = f"NEW INQUIRY — {intent} PROSPECT".strip()

        # 2. Summaries
        intent_summary = f"Transaction Intent: {intent} (Confidence: {int(overall_confidence * 100)}%)"
        buyer_profile_summary = f"Prospect Type: {', '.join(extraction.prospect_types)} • Purpose: {extraction.purpose}"

        if extraction.budget_min or extraction.budget_max:
            b_min = f"{extraction.budget_min:,.0f}" if extraction.budget_min else "Any"
            b_max = f"{extraction.budget_max:,.0f}" if extraction.budget_max else "Open"
            curr = extraction.currency if extraction.currency != "UNKNOWN" else ""
            financial_summary = f"Budget: {b_min} - {b_max} {curr} • Financing: {extraction.financing}"
        else:
            financial_summary = f"Budget: Unknown • Financing: {extraction.financing}"

        timeline_summary = f"Target Move-in Timeline: {extraction.timeline} • Urgency: {extraction.urgency}"

        # 3. Next Best Action selection
        if matched_properties and len(matched_properties) >= 1 and sales_readiness in [SalesReadiness.HIGH_PRIORITY.value, SalesReadiness.SALES_READY.value]:
            nba = NextBestActionType.SEND_PROPERTY_OPTIONS.value
            action_desc = f"Share top {min(3, len(matched_properties))} verified matching properties with client and offer viewing slots."
            rationale = f"Found {len(matched_properties)} matching inventory units in tenant database aligned with client's budget and location."
        elif "budget" in missing_fields:
            nba = NextBestActionType.ASK_BUDGET.value
            action_desc = "Clarify target purchase budget range during initial consultation."
            rationale = "Budget ceiling is required to shortlist relevant listings from inventory."
        elif "timeline" in missing_fields:
            nba = NextBestActionType.ASK_TIMELINE.value
            action_desc = "Ask client for expected move-in or investment decision timeframe."
            rationale = "Clarifies whether to present ready-to-move or off-plan options."
        elif "financing_method" in missing_fields:
            nba = NextBestActionType.ASK_FINANCING.value
            action_desc = "Inquire if client requires bank mortgage pre-approval assistance."
            rationale = "Mortgage qualification accelerates transaction completion."
        elif sales_readiness == SalesReadiness.HIGH_PRIORITY.value:
            nba = NextBestActionType.OFFER_VIEWING.value
            action_desc = "Schedule on-site property viewing with broker."
            rationale = "High buyer urgency and complete qualifications."
        elif sales_readiness == SalesReadiness.NOT_READY.value:
            nba = NextBestActionType.WAIT_FOR_RESPONSE.value
            action_desc = "Awaiting inbound response from lead."
            rationale = "Insufficient data to formulate tailored inventory recommendation."
        else:
            nba = NextBestActionType.CALL_LEAD.value
            action_desc = "Initiate discovery call to qualify requirements."
            rationale = "Gather missing core preferences."

        brief = {
            "headline": headline,
            "intent_summary": intent_summary,
            "buyer_profile_summary": buyer_profile_summary,
            "financial_summary": financial_summary,
            "timeline_summary": timeline_summary,
            "verified_matches_count": len(matched_properties),
            "missing_critical_info": missing_fields[:3],
            "recommended_action": action_desc,
            "recommended_action_type": nba,
            "action_rationale": rationale,
        }

        return brief, nba, action_desc
