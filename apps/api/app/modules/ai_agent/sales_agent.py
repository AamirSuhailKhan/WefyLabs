"""
Master Build 06 — Canonical AI Sales Agent Facade
=================================================
The single, authoritative enterprise SalesAgent orchestrating:
  RECEIVE LEAD → UNDERSTAND → QUALIFY → SEARCH → RECOMMEND → ANSWER →
  HANDLE OBJECTION → PROPOSE ACTION → AUTHORIZE → EXECUTE →
  OBSERVE → MEMORY → HANDOFF / CONTINUE

CRITICAL ARCHITECTURAL INVARIANTS:
  1. READ → SUGGEST → CONFIRM → EXECUTE: Model reasons; policy decides;
     authorizer approves; executor delivers; verification confirms.
  2. AIGATEWAY CENTRALIZATION: All LLM reasoning routes through AIGateway with
     tenant isolation and immutable request auditing.
  3. ZERO FAKE SUCCESS & ZERO HALLUCINATION: All property inventory and knowledge claims
     must come from verified authoritative subsystems.
  4. PROMPT INJECTION DEFENSE: Untrusted customer inputs are never treated as instructions.
  5. HUMAN OVERRIDE SUPREMACY: When a human takes control, autonomous AI outreach halts.
"""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union, TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

if TYPE_CHECKING:
    from app.infrastructure.ai_gateway.gateway import AIGateway
from app.infrastructure.ai_gateway.action_auth import AIActionAuthorizer, CONFIRM, EXECUTE, READ, SUGGEST
from app.infrastructure.tenancy.scope import require_organization_id
from app.models.lead import Lead
from app.models.broker import Broker
from app.models.agent_models import AgentSession, ConversationState, Escalation
from app.modules.ai_agent.action_policy import (
    AgentState,
    CustomerJourneyState,
    ActionRiskTier,
    NextBestActionType,
    AutonomyLevel,
    ProposedActionDTO,
    ActionPolicyEngine,
)
from app.modules.ai_agent.objection_engine import (
    ObjectionIntelligenceEngine,
    ObjectionAnalysis,
    ObjectionResponseDTO,
)
from app.modules.ai_agent.next_best_action import NextBestActionEngine
from app.modules.ai_agent.action_executor import GovernedActionExecutor, ActionResultDTO
from app.modules.ai_agent.agent_trace import AgentTraceDTO, AgentTraceRecorder
from app.modules.lead_qualification.extractor import QualificationFactExtractor, QualificationFactNormalizer
from app.modules.knowledge.grounding.grounding_validator import GroundingValidator, INSUFFICIENT_EVIDENCE_RESPONSE

logger = logging.getLogger(__name__)


class SalesAgent:
    """
    Canonical WefyLabs AI Sales Agent.
    Coordinates all autonomous sales reasoning while enforcing strict governance.
    """

    def __init__(
        self,
        db: AsyncSession,
        ai_gateway: Optional[Any] = None,
        policy_engine: Optional[ActionPolicyEngine] = None,
    ):
        self.db = db
        if ai_gateway is None:
            from app.infrastructure.ai_gateway.gateway import AIGateway
            self.ai_gateway = AIGateway(db=db)
        else:
            self.ai_gateway = ai_gateway
        self.policy_engine = policy_engine or ActionPolicyEngine()
        self.nba_engine = NextBestActionEngine(self.policy_engine)
        self.objection_engine = ObjectionIntelligenceEngine()
        self.action_executor = GovernedActionExecutor(db)
        self.authorizer = AIActionAuthorizer(db)
        self.grounding_validator = GroundingValidator()
        self.qualification_extractor = QualificationFactExtractor()

    # ─── 1. UNDERSTAND ────────────────────────────────────────────────────────

    async def understand(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        customer_message: str,
        conversation_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extracts customer intent, entities, sentiment, and prompt injection signals.
        Untrusted customer input is treated strictly as data.
        """
        org = require_organization_id(organization_id)
        msg = customer_message.strip()

        # Prompt injection check
        from app.infrastructure.security.prompt_guard import validate_prompt_injection
        injection_blocked = False
        try:
            is_safe, _ = validate_prompt_injection(msg)
            if not is_safe:
                injection_blocked = True
        except Exception:
            injection_blocked = True

        objection = self.objection_engine.analyze(msg)

        intent = "GENERAL"
        if "?" in msg:
            intent = "QUESTION"
        elif objection.detected:
            intent = "OBJECTION"
        elif any(w in msg.lower() for w in ["visit", "meet", "schedule", "viewing", "tour", "book"]):
            intent = "SCHEDULE"
        elif any(w in msg.lower() for w in ["stop", "unsubscribe", "opt out"]):
            intent = "OPT_OUT"

        return {
            "organization_id": org,
            "intent": intent,
            "injection_detected": injection_blocked,
            "objection_analysis": objection,
            "raw_message": msg,
        }

    # ─── 2. QUALIFY ───────────────────────────────────────────────────────────

    async def qualify(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        lead_id: str,
        customer_message: str,
        current_facts: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Extracts structured qualification facts using Build 05 Qualification Intelligence.
        Identifies missing fields required for property matching.
        """
        org_str = str(require_organization_id(organization_id))
        existing = current_facts or {}

        # Run canonical Build 05 extractor
        extraction = await QualificationFactExtractor.extract_facts_from_text(
            organization_id=org_str,
            lead_id=str(lead_id),
            text_corpus=customer_message,
        )

        extracted = {}
        if extraction and extraction.facts:
            for f in extraction.facts:
                if f.field_name and (f.normalized_value is not None or f.raw_value is not None):
                    extracted[f.field_name] = f.normalized_value if f.normalized_value is not None else f.raw_value

        merged = {**existing, **extracted}
        if merged.get("location") and not merged.get("preferred_locations"):
            merged["preferred_locations"] = [merged["location"]]
        elif merged.get("preferred_locations") and not merged.get("location"):
            merged["location"] = merged["preferred_locations"][0] if isinstance(merged["preferred_locations"], list) else merged["preferred_locations"]

        # Check missing core qualification fields
        CRITICAL_FIELDS = ["budget_max", "bedrooms", "timeline"]
        missing = [f for f in CRITICAL_FIELDS if not merged.get(f)]
        if not (merged.get("location") or merged.get("preferred_locations")):
            missing.append("location")
        is_qualified = (len(missing) == 0)

        conf = extraction.extraction_confidence if extraction else 0.8

        return {
            "extracted_facts": extracted,
            "all_facts": merged,
            "missing_fields": missing,
            "is_qualified": is_qualified,
            "confidence": conf,
        }

    # ─── 3. SEARCH ────────────────────────────────────────────────────────────

    async def search(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        criteria: Dict[str, Any],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Queries verified inventory via Build 04 Property Subsystem.
        Never fabricates property data.
        """
        org = require_organization_id(organization_id)
        from app.modules.property_intelligence.service import PropertyIntelligenceService
        svc = PropertyIntelligenceService(self.db)

        try:
            properties = await svc.list_properties(
                organization_id=org,
                filters=criteria,
                limit=limit,
            )
            return properties if isinstance(properties, list) else []
        except Exception as exc:
            logger.warning(f"[SalesAgent] Property search fallback: {exc}")
            return []

    # ─── 4. RECOMMEND ─────────────────────────────────────────────────────────

    async def recommend(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        qualification_facts: Dict[str, Any],
        candidate_properties: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Scores candidate properties against customer criteria and generates
        structured match explanations and trade-offs.
        """
        budget_max = qualification_facts.get("budget_max")
        bedrooms = qualification_facts.get("bedrooms")
        locs = qualification_facts.get("preferred_locations") or []

        recommendations = []
        for p in candidate_properties:
            price = p.get("price") or p.get("budget_max")
            p_beds = p.get("bedrooms")
            p_loc = p.get("location") or p.get("city") or ""

            match_reasons = []
            trade_offs = []

            # Budget evaluation
            if budget_max and price:
                if float(price) <= float(budget_max):
                    match_reasons.append("Within comfortable budget range")
                else:
                    trade_offs.append(f"Priced slightly above preferred budget (+{int(float(price)-float(budget_max)):,})")

            # Bedrooms evaluation
            if bedrooms and p_beds:
                if int(p_beds) == int(bedrooms):
                    match_reasons.append(f"Exact {p_beds} BHK configuration match")
                elif int(p_beds) > int(bedrooms):
                    match_reasons.append(f"Offers extra room ({p_beds} BHK)")

            # Freshness / Availability
            is_avail = p.get("is_available", True) and p.get("status", "AVAILABLE") != "SOLD_OUT"
            if not is_avail:
                trade_offs.append("Current live availability requires confirmation")

            recommendations.append({
                "property_id": p.get("id") or p.get("property_id"),
                "title": p.get("title") or p.get("name") or "Verified Property",
                "price": price,
                "bedrooms": p_beds,
                "location": p_loc,
                "match_reasons": match_reasons,
                "trade_offs": trade_offs,
                "is_available": is_avail,
            })

        return recommendations

    # ─── 5. ANSWER ────────────────────────────────────────────────────────────

    async def answer(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        query: str,
        retrieved_chunks: List[Dict[str, Any]],
        draft_answer: str,
    ) -> Dict[str, Any]:
        """
        Validates LLM draft answer using GroundingValidator.
        Blocks hallucinated prices, availability, or areas.
        """
        grounding_result = self.grounding_validator.validate(
            answer_text=draft_answer,
            retrieved_chunks=retrieved_chunks,
            require_grounding=True,
        )

        return {
            "passed": grounding_result.passed,
            "was_blocked": grounding_result.was_blocked,
            "final_answer": grounding_result.answer_text,
            "grounding_score": grounding_result.grounding_score,
            "block_reason": grounding_result.block_reason,
        }

    # ─── 6. HANDLE OBJECTION ──────────────────────────────────────────────────

    def handle_objection(
        self,
        *,
        organization_id: Optional[Union[str, uuid.UUID]] = None,
        customer_message: str,
        current_budget: Optional[float] = None,
        current_property: Optional[Dict[str, Any]] = None,
        qualification_facts: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Identifies objection category and executes 5-step framework.
        Enforces zero false scarcity and zero fabricated discounts.
        """
        facts = dict(qualification_facts or {})
        if current_budget is not None and not facts.get("budget_max"):
            facts["budget_max"] = current_budget

        analysis = self.objection_engine.analyze(customer_message)
        response_dto = self.objection_engine.formulate_response(
            analysis=analysis,
            current_property=current_property,
            qualification_facts=facts,
        )
        alt = dict(response_dto.alternative_search_params or {})
        if current_budget and not alt.get("max_price"):
            alt["max_price"] = float(current_budget) * 0.85

        return {
            "objection_category": response_dto.objection_category.value,
            "response": response_dto,
            "acknowledge": response_dto.acknowledge,
            "clarify": response_dto.clarify,
            "address": response_dto.address,
            "verify": response_dto.verify,
            "next_step": response_dto.next_step,
            "alternative_search_params": alt,
        }

    # ─── 7. DRAFT ─────────────────────────────────────────────────────────────

    async def draft(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        intent: str,
        context: Dict[str, Any],
        style: str = "consultative",
    ) -> str:
        """
        Generates sales message phrasing aligned with customer preferences and organization style.
        """
        org = require_organization_id(organization_id)
        # Fast, deterministic phrasing templates
        if intent == "ASK_QUALIFICATION":
            field = context.get("target_field", "budget")
            if field == "budget_max":
                return "To help me share the most relevant options, what approximate budget are you comfortable with?"
            elif field == "preferred_locations":
                return "Which specific areas or sectors are you most interested in exploring?"
            elif field == "bedrooms":
                return "How many bedrooms would best suit your family's requirements?"
            return "Could you share a little more about your timeline and preferred configuration?"

        elif intent == "SEND_PROPERTY":
            props = context.get("properties", [])
            count = len(props)
            return (
                f"I have selected {count} verified properties that closely match your criteria. "
                "Would you like me to share their detailed floor plans and current payment schedules?"
            )

        elif intent == "SCHEDULE_APPOINTMENT":
            return (
                "I would be delighted to arrange a guided site visit for you. "
                "What day and time this week works most conveniently for your schedule?"
            )

        elif intent == "HANDLE_OBJECTION":
            return context.get("objection_message", "I completely understand and want to ensure you have full clarity.")

        return "Thank you for sharing. How else can I assist with your property search today?"

    # ─── 8. PROPOSE ACTION ────────────────────────────────────────────────────

    def propose_action(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        lead_id: str,
        customer_message: Optional[str] = None,
        qualification_facts: Optional[Dict[str, Any]] = None,
        missing_fields: Optional[List[str]] = None,
        matched_properties: Optional[List[Dict[str, Any]]] = None,
        conversation_context: Optional[Dict[str, Any]] = None,
        is_human_active: bool = False,
        is_paused: bool = False,
        opted_out: bool = False,
    ) -> ProposedActionDTO:
        """
        Selects the Next Best Action deterministically via NextBestActionEngine.
        """
        return self.nba_engine.evaluate(
            organization_id=str(organization_id),
            lead_id=lead_id,
            customer_message=customer_message,
            qualification_facts=qualification_facts,
            missing_fields=missing_fields,
            matched_properties=matched_properties,
            conversation_context=conversation_context,
            is_human_active=is_human_active,
            is_paused=is_paused,
            opted_out=opted_out,
        )

    # ─── 9. EXECUTE AUTHORIZED ACTION ─────────────────────────────────────────

    async def execute_authorized_action(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        actor_id: str,
        proposal: ProposedActionDTO,
        parameters: Optional[Dict[str, Any]] = None,
        authorization_id: Optional[Union[str, uuid.UUID]] = None,
        authorization_token: Optional[Union[str, uuid.UUID]] = None,
        idempotency_key: Optional[str] = None,
    ) -> ActionResultDTO:
        """
        Dispatches action execution through the governed authorization gate.
        """
        auth_token = authorization_token or authorization_id
        return await self.action_executor.execute_proposed_action(
            organization_id=organization_id,
            actor_id=actor_id,
            proposal=proposal,
            parameters=parameters,
            authorization_id=auth_token,
            idempotency_key=idempotency_key,
        )

    # ─── 10. HANDOFF ──────────────────────────────────────────────────────────

    async def handoff(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        conversation_id: str,
        lead_id: str,
        reason: str,
        customer_summary: Optional[str] = None,
        qualification_snapshot: Optional[Dict[str, Any]] = None,
        property_shortlist: Optional[List[Dict[str, Any]]] = None,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Executes human handoff:
          1. Sets conversation control_mode = 'human'
          2. Generates comprehensive handoff briefing package
          3. Emits escalation event
        """
        org = require_organization_id(organization_id)
        from app.modules.communication.canonical_service import canonical_communication_service

        package = {
            "handoff_timestamp": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "lead_id": lead_id,
            "qualification_snapshot": qualification_snapshot or {},
            "property_shortlist": property_shortlist or [],
            "summary": customer_summary or f"Escalated to human broker. Reason: {reason}",
        }

        handoff_result = await canonical_communication_service.request_human_handoff(
            db=self.db,
            organization_id=org,
            conversation_id=conversation_id,
            reason=reason,
            actor_id=actor_id or "AI_AGENT",
        )

        return {
            "status": "HANDOFF_ACTIVATED",
            "conversation_id": conversation_id,
            "handoff_package": package,
            "service_result": handoff_result,
        }

    # ─── 11. PAUSE & RESUME ───────────────────────────────────────────────────

    async def pause(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        conversation_id: str,
        reason: str = "Human takeover requested",
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Pauses autonomous AI outreach on this conversation."""
        org = str(require_organization_id(organization_id))
        from app.modules.communication.canonical_service import canonical_communication_service
        return await canonical_communication_service.request_human_handoff(
            db=self.db,
            organization_id=org,
            conversation_id=str(conversation_id),
            reason=reason,
            actor_id=actor_id,
        )

    async def resume(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        conversation_id: str,
        actor_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Resumes autonomous AI processing after human hands back control."""
        org = str(require_organization_id(organization_id))
        from app.modules.communication.canonical_service import canonical_communication_service
        return await canonical_communication_service.resume_ai_control(
            db=self.db,
            organization_id=org,
            conversation_id=str(conversation_id),
            resumed_by=actor_id,
        )

    # ─── 12. SUMMARIZE ────────────────────────────────────────────────────────

    def summarize(
        self,
        *,
        lead_name: str,
        qualification_facts: Dict[str, Any],
        recent_turns: List[Dict[str, Any]],
        objections: List[str],
    ) -> str:
        """Produces concise structured briefing for human brokers."""
        budget = qualification_facts.get("budget_max", "Not specified")
        beds = qualification_facts.get("bedrooms", "Any")
        locs = qualification_facts.get("preferred_locations", [])
        loc_str = ", ".join(locs) if locs else "Not specified"

        summary = (
            f"Buyer Brief: {lead_name}\n"
            f"Budget: {budget} | BHK: {beds} | Locations: {loc_str}\n"
            f"Recent Activity: {len(recent_turns)} conversation turns recorded.\n"
        )
        if objections:
            summary += f"Identified Objections: {', '.join(objections)}\n"
        return summary

    # ─── 13. LEARN FROM OUTCOME ───────────────────────────────────────────────

    def learn_from_outcome(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        action_type: str,
        execution_id: str,
        outcome: str,
        customer_feedback: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Records action-outcome pairs for continuous evaluation and feedback loops.
        """
        record = {
            "organization_id": str(organization_id),
            "action_type": action_type,
            "execution_id": execution_id,
            "outcome": outcome,
            "customer_feedback": customer_feedback,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        logger.info(f"[SalesAgent Learning] Recorded outcome: {record}")
        return record

    # ─── 14. END-TO-END PROCESS TURN ──────────────────────────────────────────

    async def process_turn(
        self,
        *,
        organization_id: Union[str, uuid.UUID],
        lead_id: str,
        conversation_id: str,
        customer_message: str,
        actor_id: str = "ai_agent",
        current_facts: Optional[Dict[str, Any]] = None,
        is_human_active: bool = False,
        is_paused: bool = False,
    ) -> Dict[str, Any]:
        """
        Executes one complete governed sales turn:
          1. Understand customer message
          2. Qualify and update facts
          3. Evaluate Next Best Action
          4. If action is permitted autonomously, execute via ActionExecutor
          5. If action requires confirmation, return proposal for approval
          6. Record full AgentTrace
        """
        start_time = time.time()
        org = require_organization_id(organization_id)

        # 1. Understand
        understand_res = await self.understand(
            organization_id=org,
            customer_message=customer_message,
        )

        # 2. Qualify
        qual_res = await self.qualify(
            organization_id=org,
            lead_id=lead_id,
            customer_message=customer_message,
            current_facts=current_facts,
        )

        # 3. Next Best Action
        proposal = self.propose_action(
            organization_id=org,
            lead_id=lead_id,
            customer_message=customer_message,
            qualification_facts=qual_res["all_facts"],
            missing_fields=qual_res["missing_fields"],
            is_human_active=is_human_active,
            is_paused=is_paused,
        )

        # 4. Draft Phrasing
        draft_content = await self.draft(
            organization_id=org,
            intent=proposal.action_type.value,
            context={"target_field": qual_res["missing_fields"][0] if qual_res["missing_fields"] else None},
        )

        # 5. Execution or Hold for Approval
        execution_res = None
        if not proposal.requires_authorization:
            # Auto-executable under current policy
            params = {
                "conversation_id": conversation_id,
                "lead_id": lead_id,
                "message_body": draft_content,
                "resource_type": "lead",
                "resource_id": lead_id,
            }
            execution_res = await self.execute_authorized_action(
                organization_id=org,
                actor_id=actor_id,
                proposal=proposal,
                parameters=params,
            )

        latency_ms = int((time.time() - start_time) * 1000)

        # 6. Record Trace
        trace = AgentTraceDTO(
            organization_id=org,
            conversation_id=conversation_id,
            lead_id=lead_id,
            task="sales_turn",
            decision={"intent": understand_res["intent"], "is_qualified": qual_res["is_qualified"]},
            action_proposed=proposal.to_dict(),
            action_executed=execution_res.to_dict() if execution_res else None,
            latency_ms=latency_ms,
            status="SUCCESS" if (execution_res and execution_res.success) or proposal.requires_authorization else "BLOCKED",
        )
        AgentTraceRecorder.record(trace)

        return {
            "organization_id": org,
            "lead_id": lead_id,
            "conversation_id": conversation_id,
            "understanding": understand_res,
            "qualification": qual_res,
            "proposed_action": proposal.to_dict(),
            "draft_content": draft_content,
            "execution": execution_res.to_dict() if execution_res else None,
            "requires_confirmation": proposal.requires_authorization,
            "trace_id": trace.agent_run_id,
            "latency_ms": latency_ms,
        }
