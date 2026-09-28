"""
Next Best Action (NBA) Calculator — Build 07 Convergence Adapter
================================================================
REPLACES the old pipeline_stage-only stub.

This adapter bridges the Follow-Up Orchestrator (which expects a NextBestAction DB model)
to the canonical Build 06 NextBestActionEngine (which emits typed ProposedActionDTO).

Architecture:
  FollowUpOrchestratorService
    → CanonicalNBAAdapter.compute()        ← THIS FILE
      → ai_agent.NextBestActionEngine.evaluate()   ← BUILD 06 CANONICAL
    → NextBestAction (persisted)

The Follow-Up NBA is NOT a separate engine. It is an adapter.

INVARIANTS:
  1. Never returns a free-text action string when a structured type is available.
  2. Evidence is always preserved from the Build 06 engine.
  3. The LLM is NEVER consulted for NBA decisions — only for message drafting.
  4. Timing and consent remain deterministic.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.follow_up_models import NextBestAction, FollowUpPolicy

logger = logging.getLogger(__name__)

# Map Build 06 NextBestActionType enum values → human-readable strings for the DB
_ACTION_LABELS: Dict[str, str] = {
    "NO_ACTION": "No action required",
    "WAIT": "Wait for customer",
    "ASK_QUALIFICATION": "Ask qualification question",
    "SEND_PROPERTY": "Send property recommendations",
    "ANSWER_QUESTION": "Answer customer question",
    "FOLLOW_UP": "Follow up",
    "CALL": "Call customer",
    "SCHEDULE_APPOINTMENT": "Schedule site visit",
    "CONFIRM_APPOINTMENT": "Confirm appointment",
    "CONFIRM_SITE_VISIT": "Confirm site visit",
    "POST_VISIT_FOLLOW_UP": "Post-visit follow-up",
    "HANDLE_OBJECTION": "Handle objection",
    "REQUEST_DOCUMENT": "Request document",
    "HANDOFF_HUMAN": "Hand off to human agent",
    "REENGAGE": "Re-engage lead",
}


class NextBestActionEngine:
    """
    Build 07 NBA Adapter.
    Delegates to the canonical ai_agent.NextBestActionEngine and
    returns a NextBestAction model for persistence.

    Kept API-compatible with the old calculator signature so the
    FollowUpOrchestratorService requires zero changes.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_next_best_action(
        self,
        lead: Lead,
        policy: Optional[FollowUpPolicy] = None,
        target_property_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> NextBestAction:
        """
        Compute the next best action using the canonical Build 06 engine.
        Falls back to a safe WAIT action on any error.
        """
        lead_id = str(lead.id)
        org_id = str(policy.organization_id if policy else lead.organization_id or "unknown")

        try:
            from app.modules.ai_agent.next_best_action import NextBestActionEngine as CanonicalNBA
            from app.modules.ai_agent.action_policy import ActionPolicyEngine

            policy_engine = ActionPolicyEngine()
            canonical_engine = CanonicalNBA(policy_engine)

            ctx = context or {}

            # Build the context object expected by the canonical engine
            result = canonical_engine.evaluate(
                organization_id=org_id,
                lead_id=lead_id,
                customer_message=ctx.get("customer_message"),
                qualification_facts=ctx.get("qualification_facts", {}),
                missing_fields=ctx.get("missing_fields", []),
                matched_properties=ctx.get("matched_properties", []),
                conversation_context=ctx,
                is_human_active=bool(ctx.get("human_control") or ctx.get("is_human_active") or getattr(lead, "human_takeover", False)),
                is_paused=bool(ctx.get("is_paused", False)),
                opted_out=bool(ctx.get("opted_out", False) or getattr(lead, "consent_revoked", False)),
            )

            action_type = result.action_type.value if hasattr(result.action_type, "value") else str(result.action_type)
            action_label = _ACTION_LABELS.get(action_type, action_type.replace("_", " ").title())
            priority = _priority_for_type(action_type)
            confidence = result.confidence if hasattr(result, "confidence") else 0.85
            reason = result.reason if hasattr(result, "reason") else f"Determined by NBA evaluation: {action_label}"
            evidence = result.evidence if hasattr(result, "evidence") else []

            reason_full = f"{reason}"
            if evidence:
                if isinstance(evidence, dict):
                    evidence_str = "; ".join(f"{k}: {v}" for k, v in list(evidence.items())[:3])
                elif isinstance(evidence, (list, tuple)):
                    evidence_str = "; ".join(str(e) for e in evidence[:3])
                else:
                    evidence_str = str(evidence)
                reason_full = f"{reason} | Evidence: {evidence_str}"

        except Exception as exc:
            logger.warning(
                f"[NBA Adapter] Canonical NBA evaluation failed for lead {lead_id}: {exc}. "
                "Falling back to WAIT."
            )
            action_label = "Wait for customer"
            priority = 30.0
            confidence = 0.5
            reason_full = f"NBA evaluation failed ({type(exc).__name__}): defaulting to WAIT."
            action_type = "WAIT"

        nba = NextBestAction(
            lead_id=lead_id,
            organization_id=org_id,
            recommended_action=action_label,
            action_reason=reason_full,
            priority_score=priority,
            confidence=confidence,
            expected_outcome=_outcome_for_type(action_type),
            target_property_id=target_property_id,
            calculated_at=datetime.now(timezone.utc),
        )
        return nba


def _priority_for_type(action_type: str) -> float:
    """Deterministic priority score for each action type."""
    _MAP = {
        "WAIT": 20.0,
        "NO_ACTION": 0.0,
        "REENGAGE": 30.0,
        "FOLLOW_UP": 55.0,
        "CALL": 65.0,
        "HANDLE_OBJECTION": 70.0,
        "ASK_QUALIFICATION": 75.0,
        "ANSWER_QUESTION": 80.0,
        "REQUEST_DOCUMENT": 75.0,
        "SEND_PROPERTY": 80.0,
        "SCHEDULE_APPOINTMENT": 88.0,
        "CONFIRM_APPOINTMENT": 90.0,
        "CONFIRM_SITE_VISIT": 90.0,
        "POST_VISIT_FOLLOW_UP": 85.0,
        "HANDOFF_HUMAN": 92.0,
    }
    return _MAP.get(action_type, 50.0)


def _outcome_for_type(action_type: str) -> str:
    """Expected outcome description per action type."""
    _MAP = {
        "WAIT": "Customer reply",
        "NO_ACTION": "None",
        "REENGAGE": "Re-activation",
        "FOLLOW_UP": "Customer engagement",
        "CALL": "Direct conversation",
        "HANDLE_OBJECTION": "Objection resolved",
        "ASK_QUALIFICATION": "Qualification complete",
        "ANSWER_QUESTION": "Customer satisfied",
        "REQUEST_DOCUMENT": "Documents received",
        "SEND_PROPERTY": "Property shortlist confirmed",
        "SCHEDULE_APPOINTMENT": "Appointment booked",
        "CONFIRM_APPOINTMENT": "Attendance confirmed",
        "CONFIRM_SITE_VISIT": "Visit attendance confirmed",
        "POST_VISIT_FOLLOW_UP": "Interest / next step captured",
        "HANDOFF_HUMAN": "Human agent engaged",
    }
    return _MAP.get(action_type, "Action completed")
