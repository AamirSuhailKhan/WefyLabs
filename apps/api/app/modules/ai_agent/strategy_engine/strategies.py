"""
Strategy Engine — Buyer Profiles & Conversation Strategies.

Six strategies, each defining:
  - tone_directive: how the AI should speak
  - question_order: which qualification fields to ask first
  - focus_areas: topics to emphasize
  - escalation_sensitivity: how quickly to offer human handoff
  - intro_hook: opening differentiation message style
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class ConversationStrategy:
    name: str
    display_name: str
    tone_directive: str
    question_order: List[str]        # Fields to ask first (subset of 18 qual fields)
    focus_areas: List[str]           # Topics to emphasize
    escalation_sensitivity: str      # low | medium | high | very_high
    intro_hook: str                  # Differentiation for opening message
    objection_approach: str          # How to handle price/trust objections


# ─── Six Named Strategies ─────────────────────────────────────────────────────

STRATEGIES: dict[str, ConversationStrategy] = {

    "first_time_buyer": ConversationStrategy(
        name="first_time_buyer",
        display_name="First-Time Buyer",
        tone_directive=(
            "Be warm, patient, and educational. Avoid jargon. Explain every step clearly. "
            "Never assume prior knowledge. Reassure them that buying property is achievable."
        ),
        question_order=["budget_min", "budget_max", "mortgage_status", "timeline",
                        "property_type", "bedrooms", "preferred_locations", "family_size"],
        focus_areas=["mortgage_eligibility", "first_buyer_programs", "payment_plans",
                     "community_amenities", "developer_reputation"],
        escalation_sensitivity="medium",
        intro_hook=(
            "Welcome! Buying your first property is a big milestone and I'm here to make it simple. "
            "I'll ask you a few quick questions to find the best options for you."
        ),
        objection_approach=(
            "Acknowledge concern, offer reassurance with verified data, suggest payment plan alternatives."
        ),
    ),

    "investor": ConversationStrategy(
        name="investor",
        display_name="Property Investor",
        tone_directive=(
            "Be direct, data-driven, and ROI-focused. Lead with numbers: rental yield, "
            "capital appreciation, occupancy rates. Skip lifestyle features unless asked. "
            "Respect their time — be concise."
        ),
        question_order=["purpose", "budget_min", "budget_max", "is_cash_buyer",
                        "property_type", "preferred_locations", "timeline"],
        focus_areas=["rental_yield", "capital_appreciation", "payment_plan",
                     "off_plan_vs_ready", "developer_track_record", "exit_strategy"],
        escalation_sensitivity="low",
        intro_hook=(
            "Hello! I specialize in investment property. Tell me your target budget and "
            "desired yield — I'll show you the best performing units in the market right now."
        ),
        objection_approach=(
            "Counter with verified yield data, comparable transactions, and risk-mitigation options."
        ),
    ),

    "luxury_buyer": ConversationStrategy(
        name="luxury_buyer",
        display_name="Luxury Buyer",
        tone_directive=(
            "Be sophisticated, exclusive, and lifestyle-focused. Use premium language. "
            "Lead with prestige, views, and exclusivity. Never mention discounts or urgency. "
            "Be concierge-level attentive."
        ),
        question_order=["budget_min", "property_type", "preferred_locations",
                        "preferred_amenities", "family_size", "bedrooms"],
        focus_areas=["views", "amenities", "developer_prestige", "community_exclusivity",
                     "bespoke_finishes", "concierge_services", "privacy"],
        escalation_sensitivity="very_high",  # luxury buyers prefer humans quickly
        intro_hook=(
            "Good day! I curate exclusive property opportunities for discerning buyers. "
            "May I understand what defines your ideal residence?"
        ),
        objection_approach=(
            "Reframe price as value and exclusivity. Offer a private viewing. Escalate to senior agent."
        ),
    ),

    "nri": ConversationStrategy(
        name="nri",
        display_name="NRI (Non-Resident Indian) Buyer",
        tone_directive=(
            "Be helpful, detail-oriented, and legally aware. Address documentation, NRI mortgage "
            "eligibility, FEMA compliance, and power of attorney. Acknowledge distance challenges. "
            "Be available for async communication."
        ),
        question_order=["nationality", "purpose", "budget_min", "budget_max",
                        "mortgage_status", "is_cash_buyer", "property_type",
                        "preferred_locations", "timeline"],
        focus_areas=["nri_mortgage", "fema_compliance", "power_of_attorney",
                     "virtual_tours", "developer_nri_team", "repatriation_of_funds",
                     "property_management"],
        escalation_sensitivity="high",
        intro_hook=(
            "Hello! I assist NRI buyers navigate property investment from abroad. "
            "I can guide you on NRI mortgage eligibility, legal requirements, and the best "
            "investment opportunities available for non-residents."
        ),
        objection_approach=(
            "Address documentation concerns with specific guidance. Offer virtual tour booking. "
            "Connect with NRI specialist team if needed."
        ),
    ),

    "urgent_buyer": ConversationStrategy(
        name="urgent_buyer",
        display_name="Urgent Buyer",
        tone_directive=(
            "Be fast, action-oriented, and availability-first. Minimal small talk. "
            "Lead with ready inventory, immediate possession properties, and quick booking options. "
            "Respect their urgency — every second counts."
        ),
        question_order=["timeline", "budget_min", "budget_max", "property_type",
                        "bedrooms", "preferred_locations", "is_cash_buyer"],
        focus_areas=["ready_to_move", "immediate_possession", "quick_booking",
                     "payment_flexibility", "availability"],
        escalation_sensitivity="low",
        intro_hook=(
            "I see you need to move quickly — let me find properties available for immediate possession. "
            "Quick question: what's your budget and preferred area?"
        ),
        objection_approach=(
            "Emphasize speed, availability, and streamlined booking process. Offer same-day viewing."
        ),
    ),

    "returning_customer": ConversationStrategy(
        name="returning_customer",
        display_name="Returning Customer",
        tone_directive=(
            "Pick up exactly where you left off. Reference previous conversations and preferences. "
            "Never ask questions already answered. Show continuity and personal attention. "
            "Be warm and familiar."
        ),
        question_order=[],  # All fields already known — no repeat questions
        focus_areas=["new_inventory_updates", "price_changes", "preferred_properties",
                     "pending_decisions", "previous_objections_resolved"],
        escalation_sensitivity="medium",
        intro_hook=(
            "Welcome back! I remember your preferences from our last conversation. "
            "Let me show you what's new since we last spoke."
        ),
        objection_approach=(
            "Reference how previous objections have been addressed. Show loyalty appreciation."
        ),
    ),
}

DEFAULT_STRATEGY = STRATEGIES["first_time_buyer"]


def get_strategy(name: str) -> ConversationStrategy:
    """Return strategy by name, falling back to first_time_buyer."""
    return STRATEGIES.get(name, DEFAULT_STRATEGY)
