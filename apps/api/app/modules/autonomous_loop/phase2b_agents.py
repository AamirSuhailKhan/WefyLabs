"""
Phase 2B -- Bounded Domain Agent Implementations
=================================================
10 concrete bounded domain agents implementing Phase2AgentContract.
Each agent has strict, declared boundaries:
  - Explicit allowed_tools and allowed_actions
  - Explicit forbidden_actions
  - Structured execution record production
  - Policy engine evaluation before every action
  - No direct database access

AGENTS:
  1.  LeadIntelligenceAgent  -- Summarizes lead intent and profiles
  2.  QualificationAgent     -- Evaluates lead qualification profiles
  3.  PropertyMatchAgent     -- Generates property shortlists
  4.  EngagementAgent        -- Prepares outbound engagement drafts
  5.  FollowUpAgent          -- Plans follow-up sequences
  6.  VisitAgent             -- Proposes and stages site visit plans
  7.  DealProgressionAgent   -- Monitors deal state and proposes updates
  8.  RecoveryAgent          -- Reactivates lost/stale leads
  9.  RevenueIntelligenceAgent -- Revenue pattern analysis and insights
  10. ManagerIntelligenceAgent -- Cross-portfolio insights for managers
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.modules.autonomous_loop.phase2_governance import (
    Phase2ActionType,
    Phase2RiskClass,
    RevenueActionPolicyEngine,
    AutonomyReadinessCondition,
    CANONICAL_CONDITION_1, CANONICAL_CONDITION_2, CANONICAL_CONDITION_3,
    CANONICAL_CONDITION_4, CANONICAL_CONDITION_5,
)
from app.modules.autonomous_loop.phase2_agent_contracts import (
    AgentDomain,
    AgentConfidence,
    AgentContextObject,
    AgentExecutionRecord,
    AgentExecutionState,
    AgentFailureType,
    Phase2AgentContract,
)

logger = logging.getLogger("wefylabs.phase2b.agents")
AGENT_VERSION = "v2b.1.0"


def build_conditions(context: AgentContextObject) -> List[AutonomyReadinessCondition]:
    freshness_ok = context.is_fresh()
    consent_ok = True
    if context.consent_state:
        consent_ok = (context.consent_state.get("has_explicit_opt_in", False) and
                      not context.consent_state.get("has_opt_out", False) and
                      not context.consent_state.get("is_dnd", False))
    quiet_ok = True
    if context.policy_summary:
        quiet_ok = context.policy_summary.get("quiet_hours_permitted", True)
    fatigue_ok = True
    if context.policy_summary:
        fatigue_ok = context.policy_summary.get("fatigue_budget_available", True)
    confidence_ok = False
    if context.policy_summary:
        lvl = context.policy_summary.get("agent_confidence", "UNKNOWN")
        score = context.policy_summary.get("confidence_score", 0.0)
        confidence_ok = lvl == "HIGH" or score >= 0.85
    return [
        AutonomyReadinessCondition(CANONICAL_CONDITION_1, "Context freshness", freshness_ok, str(freshness_ok)),
        AutonomyReadinessCondition(CANONICAL_CONDITION_2, "Customer consent", consent_ok, str(consent_ok)),
        AutonomyReadinessCondition(CANONICAL_CONDITION_3, "Quiet hours", quiet_ok, str(quiet_ok)),
        AutonomyReadinessCondition(CANONICAL_CONDITION_4, "Fatigue budget", fatigue_ok, str(fatigue_ok)),
        AutonomyReadinessCondition(CANONICAL_CONDITION_5, "Confidence threshold", confidence_ok, str(confidence_ok)),
    ]


class LeadIntelligenceAgent(Phase2AgentContract):
    @property
    def agent_id(self): return "lead-intelligence-agent-v2b"
    @property
    def domain(self): return AgentDomain.LEAD_INTELLIGENCE
    @property
    def version(self): return AGENT_VERSION
    @property
    def purpose(self): return "Summarize lead intent, behavior, and profile from bounded CRM context."
    @property
    def allowed_tools(self): return {"get_lead_profile", "get_lead_conversation", "get_recent_actions"}
    @property
    def allowed_actions(self):
        return {
            Phase2ActionType.SUMMARIZE_LEAD, Phase2ActionType.UPDATE_LEAD_INTENT_STATE,
            Phase2ActionType.LOG_OBJECTION, Phase2ActionType.RECORD_OUTCOME,
            Phase2ActionType.NO_ACTION, Phase2ActionType.SHADOW_OBSERVE,
            Phase2ActionType.REQUEST_HUMAN_APPROVAL,
        }

    async def execute(self, context, execution_record, policy_engine, dry_run=False):
        execution_record.execution_state = AgentExecutionState.PLANNING
        action_type = Phase2ActionType.SUMMARIZE_LEAD
        decision = policy_engine.evaluate(context.organization_id, action_type, conditions=build_conditions(context))
        execution_record.policy_decisions.append(decision.to_dict())
        if not decision.is_permitted or dry_run:
            execution_record.mark_complete(f"SHADOW: Lead summary prepared. Lead={context.lead_id}", AgentConfidence.HIGH)
            return execution_record
        summary = f"Lead {context.lead_id} intent analysis complete."
        execution_record.actions_taken.append({"action": "SUMMARIZE_LEAD", "lead_id": context.lead_id, "summary": summary})
        execution_record.total_tool_calls += 1
        execution_record.mark_complete(summary, AgentConfidence.HIGH)
        return execution_record


class QualificationAgent(Phase2AgentContract):
    @property
    def agent_id(self): return "qualification-agent-v2b"
    @property
    def domain(self): return AgentDomain.QUALIFICATION
    @property
    def version(self): return AGENT_VERSION
    @property
    def purpose(self): return "Evaluate lead qualification status and update qualification profile."
    @property
    def allowed_tools(self): return {"get_lead_profile", "get_qualification_rules", "update_qualification_profile"}
    @property
    def allowed_actions(self):
        return {
            Phase2ActionType.UPDATE_QUALIFICATION_PROFILE, Phase2ActionType.SUMMARIZE_LEAD,
            Phase2ActionType.RECORD_OUTCOME, Phase2ActionType.NO_ACTION,
            Phase2ActionType.SHADOW_OBSERVE, Phase2ActionType.REQUEST_HUMAN_APPROVAL,
        }

    async def execute(self, context, execution_record, policy_engine, dry_run=False):
        execution_record.execution_state = AgentExecutionState.PLANNING
        action_type = Phase2ActionType.UPDATE_QUALIFICATION_PROFILE
        decision = policy_engine.evaluate(context.organization_id, action_type, conditions=build_conditions(context))
        execution_record.policy_decisions.append(decision.to_dict())
        if not decision.is_permitted or dry_run:
            execution_record.mark_complete(f"SHADOW: Qualification assessment prepared for lead {context.lead_id}.", AgentConfidence.MEDIUM)
            return execution_record
        execution_record.actions_taken.append({"action": "UPDATE_QUALIFICATION_PROFILE", "lead_id": context.lead_id})
        execution_record.total_tool_calls += 1
        execution_record.mark_complete(f"Qualification profile updated for lead {context.lead_id}.", AgentConfidence.HIGH)
        return execution_record


class PropertyMatchAgent(Phase2AgentContract):
    @property
    def agent_id(self): return "property-match-agent-v2b"
    @property
    def domain(self): return AgentDomain.PROPERTY_MATCH
    @property
    def version(self): return AGENT_VERSION
    @property
    def purpose(self): return "Generate ranked property shortlists based on lead requirements and inventory truth."
    @property
    def allowed_tools(self): return {"get_lead_requirements", "get_property_inventory", "compute_match_scores"}
    @property
    def allowed_actions(self):
        return {
            Phase2ActionType.PREPARE_PROPERTY_SHORTLIST, Phase2ActionType.SEND_PROPERTY_RECOMMENDATIONS,
            Phase2ActionType.SEND_PROPERTY_DETAILS, Phase2ActionType.RECORD_OUTCOME,
            Phase2ActionType.NO_ACTION, Phase2ActionType.SHADOW_OBSERVE, Phase2ActionType.REQUEST_HUMAN_APPROVAL,
        }

    async def execute(self, context, execution_record, policy_engine, dry_run=False):
        execution_record.execution_state = AgentExecutionState.PLANNING
        conditions = build_conditions(context)
        prepare_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.PREPARE_PROPERTY_SHORTLIST, conditions=conditions)
        execution_record.policy_decisions.append(prepare_decision.to_dict())
        if not prepare_decision.is_permitted or dry_run:
            execution_record.mark_complete(f"SHADOW: Property shortlist prepared for lead {context.lead_id} (not dispatched).", AgentConfidence.HIGH)
            return execution_record
        shortlist = context.property_shortlist or []
        execution_record.actions_taken.append({"action": "PREPARE_PROPERTY_SHORTLIST", "lead_id": context.lead_id, "count": len(shortlist)})
        execution_record.total_tool_calls += 1
        send_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.SEND_PROPERTY_RECOMMENDATIONS, conditions=conditions)
        execution_record.policy_decisions.append(send_decision.to_dict())
        if not send_decision.is_permitted:
            execution_record.mark_complete(f"Shortlist prepared ({len(shortlist)} properties). Send blocked: {send_decision.block_reason}", AgentConfidence.HIGH)
            return execution_record
        execution_record.actions_taken.append({"action": "SEND_PROPERTY_RECOMMENDATIONS", "lead_id": context.lead_id, "count": len(shortlist)})
        execution_record.total_tool_calls += 1
        execution_record.mark_complete(f"Property recommendations sent: {len(shortlist)} properties.", AgentConfidence.HIGH)
        return execution_record


class EngagementAgent(Phase2AgentContract):
    @property
    def agent_id(self): return "engagement-agent-v2b"
    @property
    def domain(self): return AgentDomain.ENGAGEMENT
    @property
    def version(self): return AGENT_VERSION
    @property
    def purpose(self): return "Prepare outbound engagement message drafts and dispatch when policy permits."
    @property
    def allowed_tools(self): return {"get_lead_profile", "get_conversation_history", "draft_message", "send_whatsapp", "send_email"}
    @property
    def allowed_actions(self):
        return {
            Phase2ActionType.PREPARE_MESSAGE_DRAFT, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2ActionType.SEND_EMAIL, Phase2ActionType.SEND_SMS,
            Phase2ActionType.SEND_VIEWING_INVITATION, Phase2ActionType.SEND_FOLLOW_UP,
            Phase2ActionType.RECORD_OUTCOME, Phase2ActionType.NO_ACTION,
            Phase2ActionType.SHADOW_OBSERVE, Phase2ActionType.REQUEST_HUMAN_APPROVAL,
        }

    async def execute(self, context, execution_record, policy_engine, dry_run=False):
        execution_record.execution_state = AgentExecutionState.PLANNING
        conditions = build_conditions(context)
        draft_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.PREPARE_MESSAGE_DRAFT, conditions=conditions)
        execution_record.policy_decisions.append(draft_decision.to_dict())
        if not draft_decision.is_permitted or dry_run:
            execution_record.mark_complete(f"SHADOW: Message draft prepared for lead {context.lead_id}.", AgentConfidence.HIGH)
            return execution_record
        execution_record.actions_taken.append({"action": "PREPARE_MESSAGE_DRAFT", "lead_id": context.lead_id})
        execution_record.total_tool_calls += 1
        send_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.SEND_WHATSAPP_MESSAGE, conditions=conditions)
        execution_record.policy_decisions.append(send_decision.to_dict())
        if not send_decision.is_permitted:
            execution_record.human_intervention_required = send_decision.requires_approval
            execution_record.human_intervention_reason = send_decision.block_reason
            execution_record.mark_complete(f"Draft prepared. Send blocked: {send_decision.block_reason}", AgentConfidence.HIGH)
            return execution_record
        execution_record.actions_taken.append({"action": "SEND_WHATSAPP_MESSAGE", "lead_id": context.lead_id})
        execution_record.total_tool_calls += 1
        execution_record.mark_complete(f"Engagement message sent to lead {context.lead_id}.", AgentConfidence.HIGH)
        return execution_record


class FollowUpAgent(Phase2AgentContract):
    @property
    def agent_id(self): return "follow-up-agent-v2b"
    @property
    def domain(self): return AgentDomain.FOLLOW_UP
    @property
    def version(self): return AGENT_VERSION
    @property
    def purpose(self): return "Plan and execute structured follow-up sequences for qualified leads."
    @property
    def allowed_tools(self): return {"get_lead_profile", "get_followup_history", "create_followup_task", "send_followup"}
    @property
    def allowed_actions(self):
        return {
            Phase2ActionType.CREATE_INTERNAL_TASK, Phase2ActionType.SEND_FOLLOW_UP,
            Phase2ActionType.SEND_REACTIVATION_OUTREACH, Phase2ActionType.RECORD_OUTCOME,
            Phase2ActionType.NO_ACTION, Phase2ActionType.SHADOW_OBSERVE, Phase2ActionType.REQUEST_HUMAN_APPROVAL,
        }

    async def execute(self, context, execution_record, policy_engine, dry_run=False):
        execution_record.execution_state = AgentExecutionState.PLANNING
        conditions = build_conditions(context)
        task_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.CREATE_INTERNAL_TASK, conditions=conditions)
        execution_record.policy_decisions.append(task_decision.to_dict())
        if not task_decision.is_permitted or dry_run:
            execution_record.mark_complete("SHADOW: Follow-up plan staged for review.", AgentConfidence.MEDIUM)
            return execution_record
        execution_record.actions_taken.append({"action": "CREATE_INTERNAL_TASK", "task": "schedule_followup"})
        execution_record.total_tool_calls += 1
        follow_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.SEND_FOLLOW_UP, conditions=conditions)
        execution_record.policy_decisions.append(follow_decision.to_dict())
        if not follow_decision.is_permitted:
            execution_record.human_intervention_required = follow_decision.requires_approval
            execution_record.mark_complete(f"Follow-up task created. Send blocked: {follow_decision.block_reason}", AgentConfidence.HIGH)
            return execution_record
        execution_record.actions_taken.append({"action": "SEND_FOLLOW_UP", "lead_id": context.lead_id})
        execution_record.total_tool_calls += 1
        execution_record.mark_complete(f"Follow-up sent to lead {context.lead_id}.", AgentConfidence.HIGH)
        return execution_record


class VisitAgent(Phase2AgentContract):
    @property
    def agent_id(self): return "visit-agent-v2b"
    @property
    def domain(self): return AgentDomain.VISIT
    @property
    def version(self): return AGENT_VERSION
    @property
    def purpose(self): return "Propose site visit slots and stage visit scheduling for human confirmation."
    @property
    def allowed_tools(self): return {"get_lead_profile", "get_calendar_availability", "create_visit_proposal"}
    @property
    def allowed_actions(self):
        return {
            Phase2ActionType.PREPARE_VISIT_PROPOSAL, Phase2ActionType.SEND_VIEWING_INVITATION,
            Phase2ActionType.SCHEDULE_SITE_VISIT, Phase2ActionType.RECORD_OUTCOME,
            Phase2ActionType.NO_ACTION, Phase2ActionType.SHADOW_OBSERVE, Phase2ActionType.REQUEST_HUMAN_APPROVAL,
        }

    async def execute(self, context, execution_record, policy_engine, dry_run=False):
        execution_record.execution_state = AgentExecutionState.PLANNING
        conditions = build_conditions(context)
        proposal_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.PREPARE_VISIT_PROPOSAL, conditions=conditions)
        execution_record.policy_decisions.append(proposal_decision.to_dict())
        if not proposal_decision.is_permitted or dry_run:
            execution_record.mark_complete("SHADOW: Visit proposal prepared (not sent).", AgentConfidence.HIGH)
            return execution_record
        execution_record.actions_taken.append({"action": "PREPARE_VISIT_PROPOSAL", "lead_id": context.lead_id})
        execution_record.total_tool_calls += 1
        schedule_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.SCHEDULE_SITE_VISIT, conditions=conditions)
        execution_record.policy_decisions.append(schedule_decision.to_dict())
        if not schedule_decision.is_permitted:
            execution_record.human_intervention_required = schedule_decision.requires_approval
            execution_record.human_intervention_reason = schedule_decision.block_reason
            execution_record.mark_complete(f"Visit proposal ready. Schedule blocked: {schedule_decision.block_reason}", AgentConfidence.HIGH)
            return execution_record
        execution_record.actions_taken.append({"action": "SCHEDULE_SITE_VISIT", "lead_id": context.lead_id})
        execution_record.total_tool_calls += 1
        execution_record.mark_complete(f"Site visit scheduled for lead {context.lead_id}.", AgentConfidence.HIGH)
        return execution_record


class DealProgressionAgent(Phase2AgentContract):
    @property
    def agent_id(self): return "deal-progression-agent-v2b"
    @property
    def domain(self): return AgentDomain.DEAL
    @property
    def version(self): return AGENT_VERSION
    @property
    def purpose(self): return "Monitor deal progression state and propose deal next-best-actions."
    @property
    def allowed_tools(self): return {"get_deal_state", "get_negotiation_history", "prepare_negotiation_summary"}
    @property
    def allowed_actions(self):
        return {
            Phase2ActionType.PREPARE_NEGOTIATION_SUMMARY, Phase2ActionType.UPDATE_DEAL_STATUS,
            Phase2ActionType.UPDATE_NEGOTIATION_STATE, Phase2ActionType.ESCALATE_TO_MANAGER,
            Phase2ActionType.TRIGGER_HUMAN_HANDOFF, Phase2ActionType.RECORD_OUTCOME,
            Phase2ActionType.NO_ACTION, Phase2ActionType.SHADOW_OBSERVE, Phase2ActionType.REQUEST_HUMAN_APPROVAL,
        }

    async def execute(self, context, execution_record, policy_engine, dry_run=False):
        execution_record.execution_state = AgentExecutionState.PLANNING
        conditions = build_conditions(context)
        summary_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.PREPARE_NEGOTIATION_SUMMARY, conditions=conditions)
        execution_record.policy_decisions.append(summary_decision.to_dict())
        if not summary_decision.is_permitted or dry_run:
            execution_record.mark_complete("SHADOW: Negotiation summary prepared (not applied).", AgentConfidence.MEDIUM)
            return execution_record
        execution_record.actions_taken.append({"action": "PREPARE_NEGOTIATION_SUMMARY"})
        execution_record.total_tool_calls += 1
        deal_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.UPDATE_DEAL_STATUS, conditions=conditions)
        execution_record.policy_decisions.append(deal_decision.to_dict())
        if not deal_decision.is_permitted:
            execution_record.human_intervention_required = deal_decision.requires_approval
            execution_record.human_intervention_reason = deal_decision.block_reason
            execution_record.mark_complete(f"Summary prepared. Deal update blocked: {deal_decision.block_reason}", AgentConfidence.HIGH)
            return execution_record
        execution_record.actions_taken.append({"action": "UPDATE_DEAL_STATUS"})
        execution_record.total_tool_calls += 1
        execution_record.mark_complete("Deal status updated with negotiation summary.", AgentConfidence.HIGH)
        return execution_record


class RecoveryAgent(Phase2AgentContract):
    @property
    def agent_id(self): return "recovery-agent-v2b"
    @property
    def domain(self): return AgentDomain.RECOVERY
    @property
    def version(self): return AGENT_VERSION
    @property
    def purpose(self): return "Identify and reactivate cold, lost, or stale leads with targeted outreach."
    @property
    def allowed_tools(self): return {"get_lead_history", "identify_reactivation_signals", "draft_reactivation_message"}
    @property
    def allowed_actions(self):
        return {
            Phase2ActionType.SUMMARIZE_LEAD, Phase2ActionType.SEND_REACTIVATION_OUTREACH,
            Phase2ActionType.RECORD_OUTCOME, Phase2ActionType.NO_ACTION,
            Phase2ActionType.SHADOW_OBSERVE, Phase2ActionType.REQUEST_HUMAN_APPROVAL,
        }

    async def execute(self, context, execution_record, policy_engine, dry_run=False):
        execution_record.execution_state = AgentExecutionState.PLANNING
        conditions = build_conditions(context)
        summary_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.SUMMARIZE_LEAD, conditions=conditions)
        execution_record.policy_decisions.append(summary_decision.to_dict())
        if not summary_decision.is_permitted or dry_run:
            execution_record.mark_complete("SHADOW: Reactivation candidate identified (not contacted).", AgentConfidence.MEDIUM)
            return execution_record
        execution_record.actions_taken.append({"action": "SUMMARIZE_LEAD", "lead_id": context.lead_id})
        execution_record.total_tool_calls += 1
        reach_decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.SEND_REACTIVATION_OUTREACH, conditions=conditions)
        execution_record.policy_decisions.append(reach_decision.to_dict())
        if not reach_decision.is_permitted:
            execution_record.human_intervention_required = reach_decision.requires_approval
            execution_record.mark_complete(f"Reactivation ready. Outreach blocked: {reach_decision.block_reason}", AgentConfidence.MEDIUM)
            return execution_record
        execution_record.actions_taken.append({"action": "SEND_REACTIVATION_OUTREACH", "lead_id": context.lead_id})
        execution_record.total_tool_calls += 1
        execution_record.mark_complete(f"Reactivation outreach dispatched to lead {context.lead_id}.", AgentConfidence.HIGH)
        return execution_record


class RevenueIntelligenceAgent(Phase2AgentContract):
    @property
    def agent_id(self): return "revenue-intelligence-agent-v2b"
    @property
    def domain(self): return AgentDomain.REVENUE_INTELLIGENCE
    @property
    def version(self): return AGENT_VERSION
    @property
    def purpose(self): return "Analyze revenue patterns and pipeline health. No external actions."
    @property
    def allowed_tools(self): return {"get_pipeline_summary", "get_revenue_metrics", "get_attribution_data"}
    @property
    def allowed_actions(self):
        return {
            Phase2ActionType.RECORD_OUTCOME, Phase2ActionType.SUMMARIZE_LEAD,
            Phase2ActionType.NO_ACTION, Phase2ActionType.SHADOW_OBSERVE, Phase2ActionType.REQUEST_HUMAN_APPROVAL,
        }
    @property
    def forbidden_actions(self):
        return {
            Phase2ActionType.CREATE_BOOKING, Phase2ActionType.CONFIRM_BOOKING,
            Phase2ActionType.PROCESS_PAYMENT, Phase2ActionType.CANCEL_BOOKING,
            Phase2ActionType.ISSUE_REFUND, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2ActionType.SEND_EMAIL, Phase2ActionType.SEND_SMS,
        }

    async def execute(self, context, execution_record, policy_engine, dry_run=False):
        execution_record.execution_state = AgentExecutionState.PLANNING
        decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.RECORD_OUTCOME)
        execution_record.policy_decisions.append(decision.to_dict())
        if not decision.is_permitted or dry_run:
            execution_record.mark_complete(f"SHADOW: Revenue intelligence analysis complete for org {context.organization_id}.", AgentConfidence.HIGH)
            return execution_record
        execution_record.actions_taken.append({"action": "RECORD_OUTCOME", "scope": "REVENUE_ANALYSIS"})
        execution_record.total_tool_calls += 1
        execution_record.revenue_effect = "Revenue analysis recorded."
        execution_record.mark_complete(f"Revenue intelligence recorded for org {context.organization_id}.", AgentConfidence.HIGH)
        return execution_record


class ManagerIntelligenceAgent(Phase2AgentContract):
    @property
    def agent_id(self): return "manager-intelligence-agent-v2b"
    @property
    def domain(self): return AgentDomain.MANAGER_INTELLIGENCE
    @property
    def version(self): return AGENT_VERSION
    @property
    def purpose(self): return "Generate cross-portfolio intelligence summaries for sales managers. No external actions."
    @property
    def allowed_tools(self): return {"get_team_pipeline", "get_agent_performance", "get_portfolio_summary"}
    @property
    def allowed_actions(self):
        return {
            Phase2ActionType.RECORD_OUTCOME, Phase2ActionType.PREPARE_NEGOTIATION_SUMMARY,
            Phase2ActionType.ESCALATE_TO_MANAGER, Phase2ActionType.NO_ACTION,
            Phase2ActionType.SHADOW_OBSERVE, Phase2ActionType.REQUEST_HUMAN_APPROVAL,
        }
    @property
    def forbidden_actions(self):
        return {
            Phase2ActionType.CREATE_BOOKING, Phase2ActionType.CONFIRM_BOOKING,
            Phase2ActionType.PROCESS_PAYMENT, Phase2ActionType.CANCEL_BOOKING,
            Phase2ActionType.ISSUE_REFUND, Phase2ActionType.SEND_WHATSAPP_MESSAGE,
            Phase2ActionType.SEND_EMAIL, Phase2ActionType.SEND_SMS,
            Phase2ActionType.SCHEDULE_SITE_VISIT,
        }

    async def execute(self, context, execution_record, policy_engine, dry_run=False):
        execution_record.execution_state = AgentExecutionState.PLANNING
        decision = policy_engine.evaluate(context.organization_id, Phase2ActionType.PREPARE_NEGOTIATION_SUMMARY)
        execution_record.policy_decisions.append(decision.to_dict())
        if not decision.is_permitted or dry_run:
            execution_record.mark_complete(f"SHADOW: Manager intelligence summary prepared for org {context.organization_id}.", AgentConfidence.HIGH)
            return execution_record
        execution_record.actions_taken.append({"action": "PREPARE_NEGOTIATION_SUMMARY", "scope": "PORTFOLIO"})
        execution_record.total_tool_calls += 1
        execution_record.mark_complete(f"Manager portfolio intelligence ready for org {context.organization_id}.", AgentConfidence.HIGH)
        return execution_record


ALL_PHASE2B_AGENTS = [
    LeadIntelligenceAgent(),
    QualificationAgent(),
    PropertyMatchAgent(),
    EngagementAgent(),
    FollowUpAgent(),
    VisitAgent(),
    DealProgressionAgent(),
    RecoveryAgent(),
    RevenueIntelligenceAgent(),
    ManagerIntelligenceAgent(),
]

AGENT_REGISTRY: Dict[str, Phase2AgentContract] = {
    agent.agent_id: agent for agent in ALL_PHASE2B_AGENTS
}


def get_agent(agent_id: str) -> Optional[Phase2AgentContract]:
    return AGENT_REGISTRY.get(agent_id)


def get_all_agent_ids() -> List[str]:
    return list(AGENT_REGISTRY.keys())
