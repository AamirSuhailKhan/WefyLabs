"""
WefyLabs AI Workforce — Tool Permission Matrix
Part 10 Canonical AGENT x TOOL x PERMISSION Specification
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from app.modules.ai_agent.workforce.enums import WorkforceRole


@dataclass(frozen=True)
class ToolPermission:
    allowed: bool
    access: str  # "read" | "write" | "external"
    side_effect: bool
    confirmation_required: bool


# ─── Canonical AGENT x TOOL x PERMISSION Matrix ──────────────────────────────

_TOOL_METADATA: Dict[str, Tuple[str, bool, bool]] = {
    # tool_name: (access, side_effect, confirmation_required)
    "search_properties":    ("read", False, False),
    "check_availability":   ("read", False, False),
    "get_payment_plan":     ("read", False, False),
    "book_viewing":         ("write", True, True),
    "update_qualification": ("write", True, False),
    "update_lead_crm":      ("write", True, False),
    "search_knowledge":     ("read", False, False),
    "get_lead_context":     ("read", False, False),
    "trigger_workflow":     ("external", True, False),
    "send_notification":    ("external", True, False),
    "escalate_to_human":    ("write", True, False),
    "get_available_slots":  ("read", False, False),
    "create_shortlist":     ("write", True, False),
    "get_shortlist":        ("read", False, False),
    "compare_properties":   ("read", False, False),
    "get_handoff_context":  ("read", False, False),
    # Part 11 Revenue Intelligence & Copilot Tools
    "get_revenue_overview":             ("read", False, False),
    "get_funnel_metrics":               ("read", False, False),
    "get_leakage_summary":              ("read", False, False),
    "get_source_attribution":           ("read", False, False),
    "get_opportunity_flow":             ("read", False, False),
    "get_action_effectiveness":         ("read", False, False),
    "get_outcome_history":              ("read", False, False),
    "get_data_quality":                 ("read", False, False),
    "get_lead_revenue_journey":         ("read", False, False),
    "get_property_conversion_history":  ("read", False, False),
    "get_agent_action_history":         ("read", False, False),
    "get_revenue_at_risk":              ("read", False, False),
}

# Explicit Allowed Tools per Role
_ROLE_ALLOWED_TOOLS: Dict[WorkforceRole, set[str]] = {
    WorkforceRole.SALES_AGENT: {
        "search_properties", "check_availability", "get_payment_plan", "book_viewing",
        "update_qualification", "update_lead_crm", "search_knowledge", "get_lead_context",
        "trigger_workflow", "send_notification", "escalate_to_human", "get_available_slots",
        "create_shortlist", "get_shortlist", "compare_properties", "get_handoff_context",
    },
    WorkforceRole.QUALIFICATION_AGENT: {
        "get_lead_context", "update_qualification", "search_knowledge",
    },
    WorkforceRole.PROPERTY_ADVISOR: {
        "search_properties", "check_availability", "compare_properties",
        "get_payment_plan", "search_knowledge", "get_shortlist",
    },
    WorkforceRole.FOLLOW_UP_AGENT: {
        "get_lead_context", "get_shortlist", "search_knowledge",
    },
    WorkforceRole.APPOINTMENT_ASSISTANT: {
        "get_available_slots", "check_availability", "book_viewing",
    },
    WorkforceRole.HANDOFF_ASSISTANT: {
        "get_handoff_context", "get_lead_context", "get_shortlist", "escalate_to_human",
    },
    WorkforceRole.REVENUE_COPILOT: {
        "get_lead_context", "get_shortlist", "search_knowledge",
        "get_revenue_overview", "get_funnel_metrics", "get_leakage_summary",
        "get_source_attribution", "get_opportunity_flow", "get_action_effectiveness",
        "get_outcome_history", "get_data_quality", "get_lead_revenue_journey",
        "get_property_conversion_history", "get_agent_action_history", "get_revenue_at_risk",
    },
    WorkforceRole.MANAGER_COMMAND_AGENT: {
        "get_lead_context", "search_properties", "search_knowledge", "get_shortlist",
        "get_revenue_overview", "get_funnel_metrics", "get_leakage_summary",
        "get_source_attribution", "get_opportunity_flow", "get_action_effectiveness",
        "get_outcome_history", "get_data_quality", "get_lead_revenue_journey",
        "get_property_conversion_history", "get_agent_action_history", "get_revenue_at_risk",
    },
}


def get_tool_permission(role: WorkforceRole, tool_name: str) -> ToolPermission:
    """Check permission for (role, tool) pair."""
    allowed_tools = _ROLE_ALLOWED_TOOLS.get(role, set())
    if tool_name not in allowed_tools:
        return ToolPermission(allowed=False, access="none", side_effect=False, confirmation_required=False)
    
    meta = _TOOL_METADATA.get(tool_name, ("read", False, False))
    return ToolPermission(
        allowed=True,
        access=meta[0],
        side_effect=meta[1],
        confirmation_required=meta[2],
    )


def is_tool_authorized(role: WorkforceRole, tool_name: str) -> bool:
    """Boolean check for tool authorization."""
    return tool_name in _ROLE_ALLOWED_TOOLS.get(role, set())
