"""
Master Build 06 — Canonical Next-Best-Action (NBA) Engine
=========================================================
Deterministic decision engine evaluating customer intent, qualification completeness,
inventory matches, objection states, and compliance rules to select the Next Best Action.

CRITICAL INVARIANTS:
  - 100% Deterministic and auditable priority hierarchy.
  - LLMs may propose or phrase, but NEVER override NBA decision priority.
  - Every proposed action includes full structured evidence, confidence, and risk tier.
"""
from __future__ import annotations

import re
import logging
from typing import Any, Dict, List, Optional, Tuple

from app.modules.ai_agent.action_policy import (
    NextBestActionType,
    ActionRiskTier,
    AutonomyLevel,
    ProposedActionDTO,
    ActionPolicyEngine,
)
from app.modules.ai_agent.objection_engine import (
    ObjectionIntelligenceEngine,
    ObjectionAnalysis,
)

logger = logging.getLogger(__name__)

# Intent regex patterns for fast, deterministic classification
_HUMAN_REQUEST_RE = re.compile(
    r"\b(?:talk\s+to\s+(?:a\s+)?human|speak\s+to\s+(?:a\s+)?human|human\s+agent|"
    r"speak\s+to\s+broker|connect\s+me\s+with\s+(?:a\s+)?person|real\s+person|"
    r"manager|supervisor|complaint|legal\s+notice|sue\s+you|useless|"
    r"stop\s+wasting\s+(?:my\s+)?time|terrible\s+service|angry|furious|frustrated)\b",
    re.IGNORECASE,
)

_OPT_OUT_RE = re.compile(
    r"\b(?:stop|unsubscribe|don't\s+message|do\s+not\s+message|remove\s+my\s+number|"
    r"leave\s+me\s+alone|spam|opt\s*out)\b",
    re.IGNORECASE,
)

_APPOINTMENT_INTENT_RE = re.compile(
    r"\b(?:schedule|book|visit|viewing|site\s+visit|meet|come\s+over|"
    r"tomorrow|saturday|sunday|monday|tuesday|wednesday|thursday|friday|"
    r"at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?|let's\s+meet)\b",
    re.IGNORECASE,
)

_QUESTION_INTENT_RE = re.compile(
    r"\b(?:what|where|how\s+much|when|is\s+there|are\s+there|price|cost|amenities|"
    r"floor\s+plan|maintenance|payment\s+plan|developer|rera|sqft|possession)\b",
    re.IGNORECASE,
)


class NextBestActionEngine:
    """
    Deterministic Next Best Action engine orchestrating the AI Sales decision flow.
    """

    def __init__(self, policy_engine: Optional[ActionPolicyEngine] = None):
        self.policy_engine = policy_engine or ActionPolicyEngine()
        self.objection_engine = ObjectionIntelligenceEngine()

    def evaluate(
        self,
        *,
        organization_id: str,
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
        Executes strict priority ordering to select the optimal next action:
          Priority 1: Human Escalation / Handoff
          Priority 2: Consent Revocation / Opt-out
          Priority 3: Active Objections (Price, Location, etc.)
          Priority 4: Appointment Scheduling / Confirmation Intent
          Priority 5: Factual Question Answering
          Priority 6: Qualification Gap Collection
          Priority 7: Property Recommendations
          Priority 8: Proactive Follow-up
          Priority 9: Wait
        """
        msg = (customer_message or "").strip()
        facts = qualification_facts or {}
        missing = missing_fields or []
        props = matched_properties or []
        ctx = conversation_context or {}

        # ── 1. Priority 1: Human Escalation ──────────────────────────────────
        if is_human_active:
            return self._build_proposal(
                organization_id=organization_id,
                action_type=NextBestActionType.WAIT,
                risk_tier=ActionRiskTier.LOW,
                reason="Human broker is currently active in this conversation.",
                evidence={"human_active": True},
                confidence=1.0,
                urgency="low",
                expected_outcome="AI pauses autonomous sends while human converses.",
                is_human_active=True,
                is_paused=is_paused,
            )

        if msg and _HUMAN_REQUEST_RE.search(msg):
            return self._build_proposal(
                organization_id=organization_id,
                action_type=NextBestActionType.HANDOFF_HUMAN,
                risk_tier=ActionRiskTier.LOW,
                reason="Customer explicitly requested a human broker or raised a sensitive issue.",
                evidence={"trigger_message": msg, "trigger_pattern": "HUMAN_REQUEST"},
                confidence=0.98,
                urgency="high",
                expected_outcome="Create escalation briefing and transfer control to human broker.",
                is_human_active=is_human_active,
                is_paused=is_paused,
            )

        # ── 2. Priority 2: Opt-out / Consent Revocation ───────────────────────
        if opted_out or (msg and _OPT_OUT_RE.search(msg)):
            return self._build_proposal(
                organization_id=organization_id,
                action_type=NextBestActionType.WAIT,
                risk_tier=ActionRiskTier.LOW,
                reason="Customer opted_out or requested communication cessation.",
                evidence={"opted_out": True, "trigger_message": msg},
                confidence=1.0,
                urgency="high",
                expected_outcome="Halt all automated communication and record consent revocation.",
                parameters={"update_consent": "REVOKED"},
                is_human_active=is_human_active,
                is_paused=is_paused,
            )

        # ── 3. Priority 3: Active Objection Handling ─────────────────────────
        objection = self.objection_engine.analyze(msg)
        if objection.detected:
            return self._build_proposal(
                organization_id=organization_id,
                action_type=NextBestActionType.HANDLE_OBJECTION,
                risk_tier=ActionRiskTier.MEDIUM,
                reason=f"Customer raised a {objection.category.value} objection.",
                evidence={
                    "category": objection.category.value,
                    "matched_phrase": objection.matched_phrase,
                },
                confidence=objection.confidence,
                urgency="high",
                expected_outcome="Deliver consultative 5-step objection response with real alternatives.",
                parameters={"objection_category": objection.category.value},
                is_human_active=is_human_active,
                is_paused=is_paused,
            )

        # ── 4. Priority 4: Appointment Scheduling / Confirmation Intent ───────
        if msg and _APPOINTMENT_INTENT_RE.search(msg):
            # If properties are discussed or shortlisted, scheduling is high value
            return self._build_proposal(
                organization_id=organization_id,
                action_type=NextBestActionType.SCHEDULE_APPOINTMENT,
                risk_tier=ActionRiskTier.HIGH,
                reason="Customer indicated intent to schedule a site visit or viewing.",
                evidence={"trigger_message": msg, "properties_shortlisted": len(props)},
                confidence=0.88,
                urgency="high",
                expected_outcome="Verify agent/property availability, propose viewing slot, request authorization.",
                parameters={"preferred_intent": msg},
                is_human_active=is_human_active,
                is_paused=is_paused,
            )

        # ── 5. Priority 5: Factual Question Answering ────────────────────────
        if msg and (_QUESTION_INTENT_RE.search(msg) or "?" in msg):
            return self._build_proposal(
                organization_id=organization_id,
                action_type=NextBestActionType.ANSWER_QUESTION,
                risk_tier=ActionRiskTier.LOW,
                reason="Customer asked a factual property or knowledge inquiry.",
                evidence={"query": msg},
                confidence=0.85,
                urgency="medium",
                expected_outcome="Retrieve grounded evidence via RAG/Property Intelligence and answer accurately.",
                parameters={"query": msg},
                is_human_active=is_human_active,
                is_paused=is_paused,
            )

        # ── 6. Priority 6: Missing Qualification Gaps ────────────────────────
        CRITICAL_QUAL_FIELDS = ["budget_max", "bedrooms", "timeline"]
        missing_critical = list(missing) if missing else []
        for f in CRITICAL_QUAL_FIELDS:
            if not facts.get(f) and f not in missing_critical:
                missing_critical.append(f)
        if not (facts.get("location") or facts.get("preferred_locations")) and "location" not in missing_critical:
            missing_critical.append("location")

        if missing_critical:
            target_field = missing_critical[0]
            return self._build_proposal(
                organization_id=organization_id,
                action_type=NextBestActionType.ASK_QUALIFICATION,
                risk_tier=ActionRiskTier.MEDIUM,
                reason=f"Missing essential qualification fact: {target_field}.",
                evidence={"missing_fields": missing_critical, "target_field": target_field},
                confidence=0.90,
                urgency="medium",
                expected_outcome="Ask a conversational, single-focus qualification question to narrow down inventory.",
                parameters={"target_field": target_field},
                is_human_active=is_human_active,
                is_paused=is_paused,
            )

        # ── 7. Priority 7: Property Recommendations ───────────────────────────
        if props or (not missing_critical and facts.get("budget_max")):
            return self._build_proposal(
                organization_id=organization_id,
                action_type=NextBestActionType.SEND_PROPERTY,
                risk_tier=ActionRiskTier.MEDIUM,
                reason="Customer is qualified and matching verified properties are ready.",
                evidence={"matched_count": len(props), "qualification_complete": True},
                confidence=0.92,
                urgency="medium",
                expected_outcome="Present top matched properties with structured match reasons and trade-offs.",
                parameters={"property_ids": [p.get("id") or p.get("property_id") for p in props[:3]]} if props else {},
                is_human_active=is_human_active,
                is_paused=is_paused,
            )

        # ── 8. Priority 8: Follow-up ─────────────────────────────────────────
        if ctx.get("follow_up_due"):
            return self._build_proposal(
                organization_id=organization_id,
                action_type=NextBestActionType.FOLLOW_UP,
                risk_tier=ActionRiskTier.HIGH,
                reason="Scheduled follow-up due for re-engagement.",
                evidence={"due_at": ctx.get("follow_up_due_at")},
                confidence=0.80,
                urgency="low",
                expected_outcome="Send policy-governed re-engagement message.",
                is_human_active=is_human_active,
                is_paused=is_paused,
            )

        # ── 9. Fallback: Wait ────────────────────────────────────────────────
        return self._build_proposal(
            organization_id=organization_id,
            action_type=NextBestActionType.WAIT,
            risk_tier=ActionRiskTier.LOW,
            reason="No immediate action required; awaiting customer response.",
            evidence={},
            confidence=0.75,
            urgency="low",
            expected_outcome="Maintain active listen state.",
            is_human_active=is_human_active,
            is_paused=is_paused,
        )

    def _build_proposal(
        self,
        *,
        organization_id: str,
        action_type: NextBestActionType,
        risk_tier: ActionRiskTier,
        reason: str,
        evidence: Dict[str, Any],
        confidence: float,
        urgency: str,
        expected_outcome: str,
        parameters: Optional[Dict[str, Any]] = None,
        is_human_active: bool = False,
        is_paused: bool = False,
    ) -> ProposedActionDTO:
        autonomy, requires_auth, policy_reason = self.policy_engine.evaluate_autonomy(
            organization_id=organization_id,
            action_type=action_type,
            is_human_active=is_human_active,
            is_paused=is_paused,
        )

        params = parameters or {}
        return ProposedActionDTO(
            action_type=action_type,
            risk_tier=risk_tier,
            reason=f"{reason} Policy note: {policy_reason}",
            evidence=evidence,
            confidence=confidence,
            urgency=urgency,
            expected_outcome=expected_outcome,
            parameters=params,
            requires_authorization=requires_auth,
            authorization_id=None,
        )
