"""
WefyLabs AI Workforce — Agent Router
Part 10 Bounded & Deterministic Routing Engine
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from app.modules.ai_agent.workforce.enums import WorkforceRole
from app.modules.ai_agent.workforce.policy import WorkforcePolicyEngine


@dataclass(frozen=True)
class RoutingDecision:
    selected_role: WorkforceRole
    confidence: float
    is_deterministic_fast_path: bool
    reason: str


class WorkforceRouter:
    """
    Deterministic & bounded agent router.
    Avoids multi-agent swarms for simple queries.
    Never uses an unbounded LLM loop to decide which agent to invoke.
    """

    # Fast-path pattern definitions
    PRICE_PATTERNS = [r"\bprice\b", r"\bcost\b", r"\bhow much\b", r"\brate\b", r"\bpricing\b"]
    COMPARE_PATTERNS = [r"\bcompare\b", r"\bwhich is better\b", r"\bparking\b", r"\bamid\b", r"\bamenities\b", r"\bfloor plan\b"]
    APPOINTMENT_PATTERNS = [r"\bvisit\b", r"\bappointment\b", r"\bschedule\b", r"\bviewing\b", r"\bsaturday\b", r"\bsunday\b", r"\bslot\b", r"\bsee this\b"]
    HANDOFF_PATTERNS = [r"\bhuman\b", r"\breal person\b", r"\bspeak to someone\b", r"\bcall me\b", r"\bmanager\b", r"\bconnect me\b", r"\bcomplaint\b"]
    QUALIFICATION_PATTERNS = [r"\bmissing\b", r"\bwhat info\b", r"\bqualification\b", r"\bwhat do you need\b"]
    REVENUE_PATTERNS = [r"\bwhy is this (opportunity|lead) (high priority|urgent)\b", r"\brevenue priority\b", r"\bdeal score\b"]
    MANAGER_PATTERNS = [r"\bwhich leads need attention\b", r"\brevenue at risk\b", r"\bteam workload\b", r"\bsla\b", r"\bmanager briefing\b"]
    FOLLOWUP_PATTERNS = [r"\bdraft (follow[- ]?up|message)\b", r"\bpost[- ]?visit\b", r"\bre[- ]?engagement\b"]

    @classmethod
    def route(
        cls,
        query: str,
        conversation_state: Optional[str] = None,
        is_internal_manager: bool = False,
        context: Optional[Dict[str, Any]] = None,
    ) -> RoutingDecision:
        """
        Evaluate query against deterministic rules and select optimal specialist.
        """
        sanitized_query, _ = WorkforcePolicyEngine.sanitize_untrusted_input(query)
        q_lower = sanitized_query.lower()

        # ── 1. Fast-Path: Simple Price / Single Fact Lookup ───────────────────
        # RULE 4: Do not use multi-agent swarms for simple tasks.
        for p in cls.PRICE_PATTERNS:
            if re.search(p, q_lower):
                return RoutingDecision(
                    selected_role=WorkforceRole.SALES_AGENT,
                    confidence=0.98,
                    is_deterministic_fast_path=True,
                    reason="Fast-path: Direct property retrieval / price lookup handled by primary Sales Agent.",
                )

        # ── 2. Manager Operational Inquiries ──────────────────────────────────
        for p in cls.MANAGER_PATTERNS:
            if re.search(p, q_lower):
                if is_internal_manager:
                    return RoutingDecision(
                        selected_role=WorkforceRole.MANAGER_COMMAND_AGENT,
                        confidence=0.95,
                        is_deterministic_fast_path=False,
                        reason="Operational management inquiry routed to Manager Command Agent.",
                    )
                else:
                    # External customers asking manager queries fall back to Sales Agent
                    return RoutingDecision(
                        selected_role=WorkforceRole.SALES_AGENT,
                        confidence=0.80,
                        is_deterministic_fast_path=False,
                        reason="Customer inquiry routed to Sales Agent (manager command restricted).",
                    )

        # ── 3. Revenue Copilot Explanations ───────────────────────────────────
        for p in cls.REVENUE_PATTERNS:
            if re.search(p, q_lower):
                return RoutingDecision(
                    selected_role=WorkforceRole.REVENUE_COPILOT,
                    confidence=0.92,
                    is_deterministic_fast_path=False,
                    reason="Deal momentum/priority inquiry routed to Revenue Copilot.",
                )

        # ── 4. Human Escalation ───────────────────────────────────────────────
        for p in cls.HANDOFF_PATTERNS:
            if re.search(p, q_lower):
                return RoutingDecision(
                    selected_role=WorkforceRole.HANDOFF_ASSISTANT,
                    confidence=0.99,
                    is_deterministic_fast_path=False,
                    reason="Customer requested live person or escalation; routed to Handoff Assistant.",
                )

        # ── 5. Follow-Up Draft Generation ─────────────────────────────────────
        for p in cls.FOLLOWUP_PATTERNS:
            if re.search(p, q_lower):
                return RoutingDecision(
                    selected_role=WorkforceRole.FOLLOW_UP_AGENT,
                    confidence=0.95,
                    is_deterministic_fast_path=False,
                    reason="Follow-up draft generation intent routed to Follow-Up Agent.",
                )

        # ── 6. Appointment & Viewing Scheduling ───────────────────────────────
        for p in cls.APPOINTMENT_PATTERNS:
            if re.search(p, q_lower):
                return RoutingDecision(
                    selected_role=WorkforceRole.APPOINTMENT_ASSISTANT,
                    confidence=0.95,
                    is_deterministic_fast_path=False,
                    reason="Viewing/appointment intent detected; routed to Appointment Assistant.",
                )

        # ── 7. Property Comparison & Deep Exploration ─────────────────────────
        for p in cls.COMPARE_PATTERNS:
            if re.search(p, q_lower):
                return RoutingDecision(
                    selected_role=WorkforceRole.PROPERTY_ADVISOR,
                    confidence=0.93,
                    is_deterministic_fast_path=False,
                    reason="Property comparison or attribute inquiry routed to Property Advisor.",
                )

        # ── 8. Qualification Gap Analysis ─────────────────────────────────────
        for p in cls.QUALIFICATION_PATTERNS:
            if re.search(p, q_lower):
                return RoutingDecision(
                    selected_role=WorkforceRole.QUALIFICATION_AGENT,
                    confidence=0.90,
                    is_deterministic_fast_path=False,
                    reason="Missing qualification information inquiry routed to Qualification Agent.",
                )

        # ── 9. Safe Default: Primary Sales Agent ──────────────────────────────
        return RoutingDecision(
            selected_role=WorkforceRole.SALES_AGENT,
            confidence=0.85,
            is_deterministic_fast_path=False,
            reason="Standard consultative customer dialogue routed to primary Sales Agent.",
        )
