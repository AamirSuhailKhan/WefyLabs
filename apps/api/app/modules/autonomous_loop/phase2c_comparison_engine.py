"""
Phase 2C — Human-vs-Agent Comparison Engine
============================================
Implements the 5-tier comparison model for shadow accuracy evidence.

Tiers (per Phase 2C Section 14):
  1. EXACT_AGREEMENT          — Agent and human chose identical action
  2. SEMANTIC_AGREEMENT       — Different labels but equivalent business intent
  3. ACCEPTABLE_DISAGREEMENT  — Both valid; human preferred different approach
  4. HARMFUL_DISAGREEMENT     — Agent would have caused material problem
  5. ABSTENTION               — Agent correctly chose not to act
  6. INSUFFICIENT_EVIDENCE    — Human decision not yet recorded

IMPORTANT:
  Shadow accuracy is only counted from tiers 1, 2, and 5.
  Tier 3 is counted but not attributed as agreement.
  Tier 4 is an automatic INCIDENT candidate.
  Tier 6 is excluded from shadow accuracy denominator.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Optional


class ComparisonCategory(str, enum.Enum):
    EXACT_AGREEMENT       = "EXACT_AGREEMENT"
    SEMANTIC_AGREEMENT    = "SEMANTIC_AGREEMENT"
    ACCEPTABLE_DISAGREEMENT = "ACCEPTABLE_DISAGREEMENT"
    HARMFUL_DISAGREEMENT  = "HARMFUL_DISAGREEMENT"
    ABSTENTION            = "ABSTENTION"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


@dataclass
class ComparisonResult:
    category: ComparisonCategory
    agreement_score: float  # 0.0 to 1.0
    notes: str
    is_incident_candidate: bool = False


# ── Semantic Equivalence Map ──────────────────────────────────────────────────
# Actions that are semantically equivalent despite different labels.
# Format: {canonical_group: {action_variants...}}

_SEMANTIC_GROUPS: list[set[str]] = [
    {"SEND_WHATSAPP_MESSAGE", "SEND_SMS", "SEND_MESSAGE", "MESSAGE_CUSTOMER"},
    {"SEND_EMAIL", "EMAIL_CUSTOMER", "SEND_EMAIL_FOLLOW_UP"},
    {"SEND_FOLLOW_UP", "CREATE_FOLLOW_UP", "FOLLOW_UP"},
    {"SCHEDULE_SITE_VISIT", "BOOK_VISIT", "SCHEDULE_VISIT"},
    {"SEND_PROPERTY_RECOMMENDATIONS", "SEND_PROPERTIES", "SHARE_PROPERTIES"},
    {"NO_ACTION", "ABSTAIN", "WAIT", "HOLD"},
    {"UPDATE_DEAL_STATUS", "UPDATE_DEAL", "PROGRESS_DEAL"},
    {"ESCALATE_TO_MANAGER", "ESCALATE", "HUMAN_ESCALATION"},
]


def _normalize_action(action: Optional[str]) -> str:
    if not action or not action.strip():
        return "NO_ACTION"
    return action.strip().upper().replace(" ", "_")


def _are_semantically_equivalent(action_a: str, action_b: str) -> bool:
    """Returns True if both actions belong to the same semantic group."""
    a = _normalize_action(action_a)
    b = _normalize_action(action_b)
    for group in _SEMANTIC_GROUPS:
        if a in group and b in group:
            return True
    return False


# ── Harmful Action Pairs ──────────────────────────────────────────────────────
# If agent recommends action_a but human takes action_b, it may indicate
# the agent recommendation would have caused harm.
# Format: {(agent_would_have, human_did): reason}

_POTENTIALLY_HARMFUL_PAIRS: dict[tuple[str, str], str] = {
    ("SEND_WHATSAPP_MESSAGE", "NO_ACTION"): "Customer had DND/opt-out that may not have been detected",
    ("SCHEDULE_SITE_VISIT", "NO_ACTION"): "Visit scheduling when lead not yet ready",
    ("SEND_PROPERTY_RECOMMENDATIONS", "ESCALATE_TO_MANAGER"): "Agent missed complexity requiring human escalation",
    ("UPDATE_DEAL_STATUS", "NO_ACTION"): "Premature deal progression",
}


class Phase2CComparisonEngine:
    """
    Canonical comparison engine for shadow observation analysis.
    All methods are pure functions — no side effects.
    """

    @staticmethod
    def compare(
        agent_action: Optional[str],
        human_action: Optional[str],
        decision_type: str = "CHOOSE_ALTERNATIVE",
    ) -> ComparisonResult:
        """
        Computes comparison category for a single shadow observation.

        Args:
            agent_action: What the agent recommended (e.g. "SEND_WHATSAPP_MESSAGE")
            human_action: What the human actually did (e.g. "SEND_EMAIL")
            decision_type: Human decision type (ACCEPT, REJECT, MODIFY, IGNORE, CHOOSE_ALTERNATIVE)
        """
        # Tier 5: Abstention — agent chose not to act, human also chose not to act
        agent_norm = _normalize_action(agent_action)
        human_norm = _normalize_action(human_action)

        if agent_norm in {"NO_ACTION", "ABSTAIN"} and human_norm in {"NO_ACTION", "ABSTAIN"}:
            return ComparisonResult(
                category=ComparisonCategory.ABSTENTION,
                agreement_score=1.0,
                notes="Both agent and human abstained — correct restraint.",
            )

        # Tier 6: Insufficient evidence (human not yet decided)
        if not human_action or decision_type == "PENDING":
            return ComparisonResult(
                category=ComparisonCategory.INSUFFICIENT_EVIDENCE,
                agreement_score=0.0,
                notes="Human decision not yet recorded.",
            )

        # Tier 1: Exact agreement
        if agent_norm == human_norm:
            return ComparisonResult(
                category=ComparisonCategory.EXACT_AGREEMENT,
                agreement_score=1.0,
                notes=f"Exact agreement on action: {agent_norm}",
            )

        # Tier 2: Semantic agreement
        if _are_semantically_equivalent(agent_action, human_action):
            return ComparisonResult(
                category=ComparisonCategory.SEMANTIC_AGREEMENT,
                agreement_score=0.85,
                notes=f"Semantic equivalence: agent={agent_norm} human={human_norm}",
            )

        # Tier 4: Harmful disagreement check (before acceptable disagreement)
        harm_key = (agent_norm, human_norm)
        if harm_key in _POTENTIALLY_HARMFUL_PAIRS:
            return ComparisonResult(
                category=ComparisonCategory.HARMFUL_DISAGREEMENT,
                agreement_score=0.0,
                notes=f"Potentially harmful: {_POTENTIALLY_HARMFUL_PAIRS[harm_key]}",
                is_incident_candidate=True,
            )

        # Tier 3: Acceptable disagreement
        return ComparisonResult(
            category=ComparisonCategory.ACCEPTABLE_DISAGREEMENT,
            agreement_score=0.0,
            notes=f"Different valid approaches: agent={agent_norm} human={human_norm}",
        )

    @staticmethod
    def is_eligible_for_shadow_accuracy(category: ComparisonCategory) -> bool:
        """
        Returns True if this observation should count toward shadow accuracy.
        Tiers 1 (Exact), 2 (Semantic), 5 (Abstention) = eligible.
        Tiers 3, 4, 6 = not counted in shadow accuracy numerator.
        """
        return category in {
            ComparisonCategory.EXACT_AGREEMENT,
            ComparisonCategory.SEMANTIC_AGREEMENT,
            ComparisonCategory.ABSTENTION,
        }

    @staticmethod
    def is_incident_candidate(result: ComparisonResult) -> bool:
        """Returns True if this comparison should be escalated as a safety incident."""
        return result.is_incident_candidate or result.category == ComparisonCategory.HARMFUL_DISAGREEMENT
