"""
Tool Registry — defines the 11 tools available to the AI agent.

Each tool has:
  - name: unique identifier
  - description: what it does (included in LLM tool definitions)
  - parameters: JSON Schema for LLM function calling
  - handler: async callable that executes the tool

The AI NEVER invents information. Every factual claim must come from a tool call.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler_key: str  # Key into ToolExecutor.handlers dict
    # Machine-readable policy metadata.  The model only sees the function
    # schema; the executor is the authority that enforces these controls.
    access: str = "read"  # read | write | external
    tenant_scoped: bool = True
    required_permission: str = "ai_agent.use"
    confirmation_required: bool = False
    audit_required: bool = True
    idempotency_required: bool = False


# ─── Tool Definitions (JSON Schema for LLM) ──────────────────────────────────

TOOLS: List[ToolDefinition] = [

    ToolDefinition(
        name="search_properties",
        description=(
            "Search the property database for units matching buyer criteria. "
            "ALWAYS call this before recommending any property. "
            "Returns a list of matching properties with verified price and availability."
        ),
        parameters={
            "type": "object",
            "properties": {
                "property_type": {"type": "string", "description": "apartment | villa | townhouse | plot"},
                "bedrooms": {"type": "integer", "description": "Minimum number of bedrooms"},
                "budget_max": {"type": "number", "description": "Maximum budget in local currency"},
                "locations": {"type": "array", "items": {"type": "string"},
                              "description": "List of preferred areas or communities"},
                "purpose": {"type": "string", "description": "invest | end_user"},
                "limit": {"type": "integer", "default": 3, "description": "Max results to return"},
            },
            "required": [],
        },
        handler_key="search_properties",
    ),

    ToolDefinition(
        name="check_availability",
        description=(
            "Check current availability status for a specific property ID. "
            "ALWAYS call this before confirming availability to a buyer."
        ),
        parameters={
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "description": "Property ID to check"},
            },
            "required": ["property_id"],
        },
        handler_key="check_availability",
    ),

    ToolDefinition(
        name="get_payment_plan",
        description=(
            "Retrieve the verified payment plan for a property from the developer. "
            "ALWAYS call this before discussing payment options."
        ),
        parameters={
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "description": "Property ID"},
                "developer_id": {"type": "string", "description": "Developer ID (optional)"},
            },
            "required": ["property_id"],
        },
        handler_key="get_payment_plan",
    ),

    ToolDefinition(
        name="book_viewing",
        description=(
            "Book a property viewing for the buyer. Creates a Task and Meeting in the CRM. "
            "Call this when the buyer agrees to visit a property."
        ),
        parameters={
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "description": "Property to visit"},
                "preferred_date": {"type": "string", "description": "ISO date e.g. 2025-09-15"},
                "preferred_time": {"type": "string", "description": "e.g. 10:00 AM"},
                "notes": {"type": "string", "description": "Special instructions"},
            },
            "required": ["property_id", "preferred_date"],
        },
        handler_key="book_viewing",
    ),

    ToolDefinition(
        name="update_qualification",
        description=(
            "Update the buyer qualification profile with newly discovered facts. "
            "Call after EVERY new piece of qualification information is collected. "
            "This updates the CRM lead profile."
        ),
        parameters={
            "type": "object",
            "properties": {
                "budget_min": {"type": "number"},
                "budget_max": {"type": "number"},
                "budget_currency": {"type": "string"},
                "is_cash_buyer": {"type": "boolean"},
                "mortgage_status": {"type": "string"},
                "property_type": {"type": "string"},
                "bedrooms": {"type": "integer"},
                "bathrooms": {"type": "integer"},
                "preferred_locations": {"type": "array", "items": {"type": "string"}},
                "purpose": {"type": "string"},
                "timeline": {"type": "string"},
                "nationality": {"type": "string"},
                "family_size": {"type": "integer"},
            },
            "required": [],
        },
        handler_key="update_qualification",
    ),

    ToolDefinition(
        name="update_lead_crm",
        description=(
            "Update the lead's CRM record with new status, pipeline stage, or notes. "
            "Call after significant conversation milestones."
        ),
        parameters={
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "active | qualified | converted"},
                "pipeline_stage": {"type": "string", "description": "contacted | viewing | negotiating"},
                "notes": {"type": "string", "description": "Summary note to add to lead record"},
            },
            "required": [],
        },
        handler_key="update_lead_crm",
    ),

    ToolDefinition(
        name="search_knowledge",
        description=(
            "Search the organization's knowledge base for policies, FAQs, developer info, "
            "area guides, or process documentation. Call before answering policy questions."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "category": {"type": "string",
                             "description": "policy | faq | developer | area_guide | process"},
            },
            "required": ["query"],
        },
        handler_key="search_knowledge",
    ),

    ToolDefinition(
        name="get_lead_context",
        description="Load the full lead profile, intelligence scores, and CRM history.",
        parameters={
            "type": "object",
            "properties": {
                "lead_id": {"type": "string"},
            },
            "required": ["lead_id"],
        },
        handler_key="get_lead_context",
    ),

    ToolDefinition(
        name="trigger_workflow",
        description=(
            "Trigger a CRM workflow by name. Use for follow-up sequences, "
            "drip campaigns, or automated task creation."
        ),
        parameters={
            "type": "object",
            "properties": {
                "workflow_name": {"type": "string", "description": "Workflow identifier"},
                "payload": {"type": "object", "description": "Workflow input data"},
            },
            "required": ["workflow_name"],
        },
        handler_key="trigger_workflow",
    ),

    ToolDefinition(
        name="send_notification",
        description="Send a notification to the assigned broker or manager.",
        parameters={
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "Notification message"},
                "priority": {"type": "string", "description": "low | medium | high | urgent"},
            },
            "required": ["message"],
        },
        handler_key="send_notification",
    ),

    ToolDefinition(
        name="escalate_to_human",
        description=(
            "Escalate the conversation to a human agent. "
            "Call when: buyer requests human, complaint, legal/financial question, "
            "very high value lead, or AI confidence is low."
        ),
        parameters={
            "type": "object",
            "properties": {
                "reason": {"type": "string",
                           "description": "human_requested | high_value_lead | low_confidence | "
                                          "complaint | legal_question | financial_advice | "
                                          "unsupported_request"},
                "priority": {"type": "string", "description": "low | medium | high | urgent"},
                "notes": {"type": "string", "description": "Additional context for the human agent"},
            },
            "required": ["reason"],
        },
        handler_key="escalate_to_human",
    ),

    ToolDefinition(
        name="get_available_slots",
        description=(
            "Get available property viewing time slots for the next 7 days. "
            "ALWAYS call this before confirming any appointment. "
            "Returns suggested slots; actual confirmation requires agent approval."
        ),
        parameters={
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "description": "Property to visit (optional)"},
                "days_ahead": {"type": "integer", "default": 7,
                               "description": "How many days ahead to check"},
            },
            "required": [],
        },
        handler_key="get_available_slots",
    ),

    ToolDefinition(
        name="create_shortlist",
        description=(
            "Add a property to the customer's shortlist. "
            "Call when the customer expresses interest or wants to save a property. "
            "Status can be: shortlisted | liked | rejected | visit_requested."
        ),
        parameters={
            "type": "object",
            "properties": {
                "property_id": {"type": "string", "description": "Property ID to shortlist"},
                "status": {"type": "string",
                           "description": "shortlisted | liked | rejected | visit_requested",
                           "default": "shortlisted"},
                "notes": {"type": "string", "description": "Reason for shortlisting or rejection"},
            },
            "required": ["property_id"],
        },
        handler_key="create_shortlist",
    ),

    ToolDefinition(
        name="get_shortlist",
        description=(
            "Retrieve the customer's current shortlisted properties. "
            "Call to show what the customer has saved so far."
        ),
        parameters={
            "type": "object",
            "properties": {
                "status_filter": {"type": "string",
                                  "description": "Filter by: shortlisted | liked | rejected | all"},
            },
            "required": [],
        },
        handler_key="get_shortlist",
    ),

    ToolDefinition(
        name="compare_properties",
        description=(
            "Retrieve verified data for multiple properties for side-by-side comparison. "
            "Call when customer says 'compare these' or 'which is better'. "
            "Returns verified structured attributes only."
        ),
        parameters={
            "type": "object",
            "properties": {
                "property_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of property IDs to compare (2-4 max)",
                },
            },
            "required": ["property_ids"],
        },
        handler_key="compare_properties",
    ),

    ToolDefinition(
        name="get_handoff_context",
        description=(
            "Generate a structured handoff summary for the human agent. "
            "Call BEFORE escalating to include customer context, requirements, shortlist, and objections."
        ),
        parameters={
            "type": "object",
            "properties": {
                "include_shortlist": {"type": "boolean", "default": True},
                "include_objections": {"type": "boolean", "default": True},
            },
            "required": [],
        },
        handler_key="get_handoff_context",
    ),

    # ── Part 11 Revenue Intelligence & Copilot Tools ─────────────────────────
    ToolDefinition(
        name="get_revenue_overview",
        description="Get high-level revenue figures including confirmed revenue, active pipeline, and revenue at risk.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler_key="get_revenue_overview",
    ),
    ToolDefinition(
        name="get_funnel_metrics",
        description="Get stage-by-stage counts, conversion rates, and pipeline values for the revenue funnel.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler_key="get_funnel_metrics",
    ),
    ToolDefinition(
        name="get_leakage_summary",
        description="Get operational revenue leakage items, dropped leads, and value-at-risk analysis.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler_key="get_leakage_summary",
    ),
    ToolDefinition(
        name="get_source_attribution",
        description="Get lead source and channel attribution report showing conversion yield per source.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler_key="get_source_attribution",
    ),
    ToolDefinition(
        name="get_opportunity_flow",
        description="Get learning loop summary showing highest-performing opportunity types and conversion rates.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler_key="get_opportunity_flow",
    ),
    ToolDefinition(
        name="get_action_effectiveness",
        description="Get action effectiveness metrics showing positive vs negative outcomes of revenue actions.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler_key="get_action_effectiveness",
    ),
    ToolDefinition(
        name="get_outcome_history",
        description="Get historical outcome distribution and true win rates from feedback logs and deals.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler_key="get_outcome_history",
    ),
    ToolDefinition(
        name="get_data_quality",
        description="Get data health score and audit of missing sources, budgets, or outcomes.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler_key="get_data_quality",
    ),
    ToolDefinition(
        name="get_lead_revenue_journey",
        description="Get unified chronological revenue journey for an individual lead.",
        parameters={"type": "object", "properties": {"lead_id": {"type": "string", "description": "Lead UUID"}}, "required": ["lead_id"]},
        handler_key="get_lead_revenue_journey",
    ),
    ToolDefinition(
        name="get_property_conversion_history",
        description="Get conversion history, appointments, and deals for a specific property listing.",
        parameters={"type": "object", "properties": {"property_id": {"type": "string", "description": "Property UUID"}}, "required": ["property_id"]},
        handler_key="get_property_conversion_history",
    ),
    ToolDefinition(
        name="get_agent_action_history",
        description="Get operational activity metrics and closed deals per sales representative.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler_key="get_agent_action_history",
    ),
    ToolDefinition(
        name="get_revenue_at_risk",
        description="Get total estimated revenue at risk from stalled and lost opportunities.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler_key="get_revenue_at_risk",
    ),
]

# LLM function-calling format (OpenAI-compatible)
def get_tool_definitions_for_llm() -> List[Dict[str, Any]]:
    """Return tools in OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }
        for t in TOOLS
    ]

TOOL_MAP: Dict[str, ToolDefinition] = {t.name: t for t in TOOLS}
