"""
WefyLabs AI Workforce — Agent Registry
Part 10 Canonical 8-Role Registry
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.modules.ai_agent.workforce.enums import WorkforceRole, AgentCapability


@dataclass(frozen=True)
class AgentDefinition:
    """Canonical definition of an AI Workforce specialist agent."""
    agent_id: str
    name: str
    role: WorkforceRole
    purpose: str
    system_policy: str
    prompt_version: str
    allowed_tools: List[str]
    allowed_context: List[str]
    allowed_delegations: List[WorkforceRole]
    read_write_capability: AgentCapability
    confirmation_rules: Dict[str, Any]
    model_policy: str  # e.g. "conversational_reasoning", "deterministic_extraction", "analytical_diagnosis"
    token_budget: int
    timeout_seconds: float
    max_iterations: int
    tenant_required: bool = True
    human_escalation_policy: str = "escalate_on_low_confidence_or_human_request"


# ─── Canonical Definitions for the 8 Specialist Roles ─────────────────────────

WORKFORCE_REGISTRY: Dict[WorkforceRole, AgentDefinition] = {
    WorkforceRole.SALES_AGENT: AgentDefinition(
        agent_id="sales_agent",
        name="AI Sales Agent",
        role=WorkforceRole.SALES_AGENT,
        purpose="Primary customer-facing sales conversation, qualification, and buyer progression.",
        system_policy=(
            "Act as the authoritative, consultative WefyLabs sales professional. "
            "Never promise unverified discounts, legal terms, or appreciation guarantees. "
            "Delegate specialized deep dives (properties, qualification, booking, handoff) "
            "to leaf assistants and synthesize cohesive responses."
        ),
        prompt_version="SALES_AGENT_V1",
        allowed_tools=[
            "search_properties",
            "check_availability",
            "get_payment_plan",
            "book_viewing",
            "update_qualification",
            "update_lead_crm",
            "search_knowledge",
            "get_lead_context",
            "trigger_workflow",
            "send_notification",
            "escalate_to_human",
            "get_available_slots",
            "create_shortlist",
            "get_shortlist",
            "compare_properties",
            "get_handoff_context",
        ],
        allowed_context=["lead_profile", "qualification", "shortlist", "memory_facts", "conversation_history", "property_signals"],
        allowed_delegations=[
            WorkforceRole.PROPERTY_ADVISOR,
            WorkforceRole.QUALIFICATION_AGENT,
            WorkforceRole.APPOINTMENT_ASSISTANT,
            WorkforceRole.HANDOFF_ASSISTANT,
        ],
        read_write_capability=AgentCapability.READ_WRITE_SUGGEST,
        confirmation_rules={"book_viewing": "requires_explicit_confirmation", "external_messaging": "requires_consent"},
        model_policy="conversational_reasoning",
        token_budget=2048,
        timeout_seconds=25.0,
        max_iterations=4,
        tenant_required=True,
        human_escalation_policy="escalate_on_explicit_request_or_high_value_stalled",
    ),

    WorkforceRole.QUALIFICATION_AGENT: AgentDefinition(
        agent_id="qualification_agent",
        name="Qualification Specialist",
        role=WorkforceRole.QUALIFICATION_AGENT,
        purpose="Analyze buyer requirements, identify missing qualification facts, and formulate optimal next questions.",
        system_policy=(
            "Focus strictly on buyer qualification facts (budget, bedrooms, timeline, locations, purpose). "
            "Never alter canonical qualification policies. Canonical LeadQualificationDomainService is authoritative."
        ),
        prompt_version="QUALIFICATION_AGENT_V1",
        allowed_tools=[
            "get_lead_context",
            "update_qualification",
            "search_knowledge",
        ],
        allowed_context=["lead_profile", "qualification", "memory_facts"],
        allowed_delegations=[],  # Leaf specialist
        read_write_capability=AgentCapability.READ_WRITE_SUGGEST,
        confirmation_rules={},
        model_policy="deterministic_extraction",
        token_budget=512,
        timeout_seconds=10.0,
        max_iterations=2,
        tenant_required=True,
        human_escalation_policy="escalate_if_conflicting_unresolvable_facts",
    ),

    WorkforceRole.PROPERTY_ADVISOR: AgentDefinition(
        agent_id="property_advisor",
        name="Property Advisor",
        role=WorkforceRole.PROPERTY_ADVISOR,
        purpose="Deep property discovery, attribute comparison, match explanations, and verified inventory truth.",
        system_policy=(
            "Answer property-specific queries strictly from verified inventory and canonical match scores. "
            "Never invent alternate match scores or unverified listing attributes. Ground every answer in property truth."
        ),
        prompt_version="PROPERTY_ADVISOR_V1",
        allowed_tools=[
            "search_properties",
            "check_availability",
            "compare_properties",
            "get_payment_plan",
            "search_knowledge",
            "get_shortlist",
        ],
        allowed_context=["lead_profile", "qualification", "property_truth", "matches", "shortlist"],
        allowed_delegations=[],  # Leaf specialist
        read_write_capability=AgentCapability.READ_ONLY,
        confirmation_rules={},
        model_policy="analytical_explanation",
        token_budget=1024,
        timeout_seconds=15.0,
        max_iterations=3,
        tenant_required=True,
        human_escalation_policy="escalate_if_unlisted_bespoke_inventory_required",
    ),

    WorkforceRole.FOLLOW_UP_AGENT: AgentDefinition(
        agent_id="follow_up_agent",
        name="Follow-Up Specialist",
        role=WorkforceRole.FOLLOW_UP_AGENT,
        purpose="Synthesize interaction notes, site visit outcomes, and draft targeted re-engagement communications.",
        system_policy=(
            "Draft contextual follow-up messages based on recorded conversation and site visit facts. "
            "Follow-Up Automation owns actual scheduling, channel dispatch, and delivery timing. "
            "Agent drafts; application validates and executes."
        ),
        prompt_version="FOLLOW_UP_AGENT_V1",
        allowed_tools=[
            "get_lead_context",
            "get_shortlist",
            "search_knowledge",
        ],
        allowed_context=["lead_profile", "qualification", "shortlist", "visit_outcomes", "objections"],
        allowed_delegations=[],  # Leaf specialist
        read_write_capability=AgentCapability.READ_ONLY,
        confirmation_rules={"dispatch": "followup_automation_managed"},
        model_policy="conversational_drafting",
        token_budget=768,
        timeout_seconds=12.0,
        max_iterations=2,
        tenant_required=True,
        human_escalation_policy="escalate_if_negative_site_visit_review",
    ),

    WorkforceRole.APPOINTMENT_ASSISTANT: AgentDefinition(
        agent_id="appointment_assistant",
        name="Appointment & Viewing Assistant",
        role=WorkforceRole.APPOINTMENT_ASSISTANT,
        purpose="Guide buyers through verified viewing slot selection and prepare confirmation-gated appointment bookings.",
        system_policy=(
            "Retrieve verified calendar availability. Never fabricate viewing slots. "
            "Booking requests require explicit customer confirmation before CRM commitment."
        ),
        prompt_version="APPOINTMENT_ASSISTANT_V1",
        allowed_tools=[
            "get_available_slots",
            "check_availability",
            "book_viewing",
        ],
        allowed_context=["lead_profile", "shortlist", "calendar_slots"],
        allowed_delegations=[],  # Leaf specialist
        read_write_capability=AgentCapability.CONFIRMATION_REQUIRED,
        confirmation_rules={"book_viewing": "requires_explicit_customer_confirmation"},
        model_policy="structured_scheduling",
        token_budget=512,
        timeout_seconds=10.0,
        max_iterations=2,
        tenant_required=True,
        human_escalation_policy="escalate_if_no_slots_within_horizon",
    ),

    WorkforceRole.HANDOFF_ASSISTANT: AgentDefinition(
        agent_id="handoff_assistant",
        name="Human Handoff Assistant",
        role=WorkforceRole.HANDOFF_ASSISTANT,
        purpose="Generate structured human handoff context briefings (customer profile, requirements, objections, shortlist).",
        system_policy=(
            "Compile clear, concise briefing for human sales brokers. "
            "Human routing service owns authoritative broker assignment and transfer."
        ),
        prompt_version="HANDOFF_ASSISTANT_V1",
        allowed_tools=[
            "get_handoff_context",
            "get_lead_context",
            "get_shortlist",
            "escalate_to_human",
        ],
        allowed_context=["lead_profile", "qualification", "shortlist", "objections", "summary"],
        allowed_delegations=[],  # Leaf specialist
        read_write_capability=AgentCapability.READ_WRITE_SUGGEST,
        confirmation_rules={},
        model_policy="structured_summarization",
        token_budget=768,
        timeout_seconds=10.0,
        max_iterations=2,
        tenant_required=True,
        human_escalation_policy="immediate_transfer",
    ),

    WorkforceRole.REVENUE_COPILOT: AgentDefinition(
        agent_id="revenue_copilot",
        name="Revenue Copilot",
        role=WorkforceRole.REVENUE_COPILOT,
        purpose="Explain canonical Revenue Autopilot signals, buyer momentum, deal urgency, and recommended actions.",
        system_policy=(
            "Explain Revenue Opportunity metrics strictly from stored data. "
            "Never redefine or compute independent opportunity scores. Revenue Autopilot is authoritative."
        ),
        prompt_version="REVENUE_COPILOT_V1",
        allowed_tools=[
            "get_lead_context",
            "get_shortlist",
            "search_knowledge",
        ],
        allowed_context=["lead_profile", "revenue_opportunity", "engagement_signals", "pipeline_stage"],
        allowed_delegations=[],  # Leaf specialist
        read_write_capability=AgentCapability.READ_ONLY,
        confirmation_rules={},
        model_policy="analytical_diagnosis",
        token_budget=1024,
        timeout_seconds=12.0,
        max_iterations=2,
        tenant_required=True,
        human_escalation_policy="escalate_on_imminent_churn_risk",
    ),

    WorkforceRole.MANAGER_COMMAND_AGENT: AgentDefinition(
        agent_id="manager_command_agent",
        name="Manager Command Agent",
        role=WorkforceRole.MANAGER_COMMAND_AGENT,
        purpose="Internal management briefing answering queries on revenue at risk, hot leads, SLAs, and team workload.",
        system_policy=(
            "Provide operational diagnostics from real system records. "
            "May delegate to Revenue Copilot for individual deal intelligence. "
            "Never alter CRM ownership or execute high-impact mutations without confirmation."
        ),
        prompt_version="MANAGER_AGENT_V1",
        allowed_tools=[
            "get_lead_context",
            "search_properties",
            "search_knowledge",
            "get_shortlist",
        ],
        allowed_context=["team_metrics", "sla_status", "inventory_demand", "revenue_at_risk", "hot_leads"],
        allowed_delegations=[WorkforceRole.REVENUE_COPILOT],
        read_write_capability=AgentCapability.READ_ONLY,
        confirmation_rules={"reassignment": "requires_admin_approval"},
        model_policy="executive_summary",
        token_budget=1536,
        timeout_seconds=15.0,
        max_iterations=3,
        tenant_required=True,
        human_escalation_policy="notify_broker_director",
    ),
}


def get_agent_definition(role: WorkforceRole) -> AgentDefinition:
    """Retrieve canonical definition for an agent role."""
    if role not in WORKFORCE_REGISTRY:
        raise KeyError(f"Unknown workforce role: {role}")
    return WORKFORCE_REGISTRY[role]


def list_registered_agents() -> List[Dict[str, Any]]:
    """Return serialized metadata for all registered agents."""
    return [
        {
            "agent_id": a.agent_id,
            "name": a.name,
            "role": a.role.value,
            "purpose": a.purpose,
            "prompt_version": a.prompt_version,
            "allowed_tools": a.allowed_tools,
            "allowed_delegations": [d.value for d in a.allowed_delegations],
            "read_write_capability": a.read_write_capability.value,
            "model_policy": a.model_policy,
            "token_budget": a.token_budget,
            "timeout_seconds": a.timeout_seconds,
        }
        for a in WORKFORCE_REGISTRY.values()
    ]


def validate_delegation_allowed(from_role: WorkforceRole, to_role: WorkforceRole) -> bool:
    """Check if from_role has explicit authority to delegate to to_role."""
    defn = WORKFORCE_REGISTRY.get(from_role)
    if not defn:
        return False
    return to_role in defn.allowed_delegations
