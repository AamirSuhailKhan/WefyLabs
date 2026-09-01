"""
Part 21.5 — Deterministic Sales Action Policy & Priority Engine
===============================================================
Evaluates lead state, qualification snapshots, verified property matches,
conversation history, consent, quiet hours, and fatigue to determine the Next Best Action.

NON-NEGOTIABLE PRINCIPLE:
Decision priority is 100% deterministic and auditable.
AI may phrase messages, but NEVER decides policy authorization or permissions.
"""
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple

from app.models.lead import Lead
from app.models.follow_up_models import FollowUpPolicy, FollowUpExecution
from app.models.calendar_models import SchedulingMeeting as Meeting
from app.modules.lead_qualification.dto import QualificationSnapshotDTO
from app.modules.sales_action.taxonomies import (
    SalesActionType,
    SalesActionStatus,
    CommunicationChannel,
    ConsentStatus,
    HandoffReason,
)
from app.modules.sales_action.dto import SalesActionDecisionDTO, SalesBriefDTO
from app.modules.sales_action.guards.human_approval_guard import HumanApprovalGuard

logger = logging.getLogger(__name__)


class SalesActionPolicyEngine:
    """
    Core deterministic Next Best Action decision engine.
    """

    POLICY_VERSION = "v1.0-sales-action"

    @classmethod
    def evaluate_decision(
        cls,
        lead: Lead,
        organization_id: str,
        qualification_snapshot: Optional[QualificationSnapshotDTO] = None,
        active_facts_summary: Optional[Dict[str, Any]] = None,
        has_blocking_conflicts: bool = False,
        latest_customer_message: Optional[str] = None,
        matched_properties: Optional[List[Dict[str, Any]]] = None,
        viewings: Optional[List[Meeting]] = None,
        policy: Optional[FollowUpPolicy] = None,
        consent_status: ConsentStatus = ConsentStatus.GRANTED,
        consent_blocked_reason: Optional[str] = None,
        is_timing_permitted: bool = True,
        scheduled_for_utc: Optional[datetime] = None,
        customer_timezone: str = "UTC",
        timing_reason: Optional[str] = None,
        is_fatigued: bool = False,
        fatigue_score: float = 0.0,
        fatigue_reason: Optional[str] = None,
        is_dormant_candidate: bool = False,
        previous_executions: Optional[List[FollowUpExecution]] = None,
    ) -> SalesActionDecisionDTO:
        """
        Executes strict, audited priority ordering to produce an immutable SalesActionDecisionDTO.
        """
        eval_time = datetime.now(timezone.utc)
        prev_execs = previous_executions or []
        facts = active_facts_summary or {}
        props = matched_properties or []
        props_count = len(props)

        # ── 1. Priority 1: Customer Trigger / Urgent Human Escalation ─────────
        req_msg, msg_handoff_reason, msg_exp = HumanApprovalGuard.check_message_triggers(latest_customer_message)
        if req_msg:
            brief = cls._build_sales_brief(
                lead=lead,
                facts=facts,
                matched_props_count=props_count,
                handoff_reason=msg_handoff_reason.value if msg_handoff_reason else "CUSTOMER_REQUEST",
                latest_msg=latest_customer_message,
                recommended_action="Contact client directly via phone/WhatsApp to address specific inquiry.",
            )
            return SalesActionDecisionDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                action_type=SalesActionType.HUMAN_HANDOFF,
                status=SalesActionStatus.HUMAN_REVIEW,
                reason=msg_exp or "Customer message requires human broker intervention.",
                priority=100.0,
                confidence=0.95,
                recommended_channel=CommunicationChannel.HUMAN_CALL,
                automation_allowed=False,
                human_approval_required=True,
                customer_timezone=customer_timezone,
                sales_brief=brief,
                policy_version=cls.POLICY_VERSION,
                evaluated_at=eval_time,
            )

        # Unresolved qualification conflicts
        if has_blocking_conflicts:
            brief = cls._build_sales_brief(
                lead=lead,
                facts=facts,
                matched_props_count=props_count,
                handoff_reason=HandoffReason.QUALIFICATION_CONFLICT.value,
                latest_msg=latest_customer_message,
                recommended_action="Review contradictory qualification facts and clarify with client.",
            )
            return SalesActionDecisionDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                action_type=SalesActionType.HUMAN_HANDOFF,
                status=SalesActionStatus.HUMAN_REVIEW,
                reason="Unresolved qualification facts conflict detected requiring human review.",
                priority=95.0,
                confidence=0.90,
                recommended_channel=CommunicationChannel.HUMAN_CALL,
                automation_allowed=False,
                human_approval_required=True,
                customer_timezone=customer_timezone,
                sales_brief=brief,
                policy_version=cls.POLICY_VERSION,
                evaluated_at=eval_time,
            )

        # ── 2. Priority 2: Consent Denied or Revoked ─────────────────────────
        if consent_status in (ConsentStatus.DENIED, ConsentStatus.REVOKED):
            return SalesActionDecisionDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                action_type=SalesActionType.PAUSE_OUTREACH,
                status=SalesActionStatus.BLOCKED,
                reason=consent_blocked_reason or f"Outreach blocked: consent is {consent_status.value}.",
                priority=90.0,
                confidence=1.0,
                recommended_channel=CommunicationChannel.WHATSAPP,
                automation_allowed=False,
                human_approval_required=False,
                blocked_reason=consent_blocked_reason or f"Consent {consent_status.value}",
                customer_timezone=customer_timezone,
                policy_version=cls.POLICY_VERSION,
                evaluated_at=eval_time,
            )

        # ── 3. Priority 3: Terminal Pipeline States ───────────────────────────
        stage = (lead.pipeline_stage or lead.status or "new").upper()
        if stage in ("CONVERTED", "LOST", "DO_NOT_CONTACT", "CLOSED"):
            return SalesActionDecisionDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                action_type=SalesActionType.NO_ACTION,
                status=SalesActionStatus.COMPLETED,
                reason=f"Lead is in terminal lifecycle state '{stage}'. Automated sales outreach stopped.",
                priority=0.0,
                confidence=1.0,
                recommended_channel=CommunicationChannel.WHATSAPP,
                automation_allowed=False,
                human_approval_required=False,
                customer_timezone=customer_timezone,
                policy_version=cls.POLICY_VERSION,
                evaluated_at=eval_time,
            )

        # ── 4. Priority 4: Dormancy & Fatigue Suppression ────────────────────
        if is_dormant_candidate:
            return SalesActionDecisionDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                action_type=SalesActionType.MARK_DORMANT,
                status=SalesActionStatus.APPROVED,
                reason=fatigue_reason or "Maximum consecutive unanswered follow-ups reached. Marking dormant.",
                priority=80.0,
                confidence=0.95,
                recommended_channel=CommunicationChannel.WHATSAPP,
                automation_allowed=True,
                human_approval_required=False,
                customer_timezone=customer_timezone,
                policy_version=cls.POLICY_VERSION,
                evaluated_at=eval_time,
            )

        if is_fatigued:
            return SalesActionDecisionDTO(
                lead_id=str(lead.id),
                organization_id=organization_id,
                action_type=SalesActionType.NO_ACTION,
                status=SalesActionStatus.BLOCKED,
                reason=fatigue_reason or "Communication fatigue threshold exceeded.",
                priority=40.0,
                confidence=0.90,
                recommended_channel=CommunicationChannel.WHATSAPP,
                automation_allowed=False,
                human_approval_required=False,
                blocked_reason=fatigue_reason,
                customer_timezone=customer_timezone,
                policy_version=cls.POLICY_VERSION,
                evaluated_at=eval_time,
            )

        # ── 5. Priority 5: Active Viewing & Appointment Lifecycle ─────────────
        if viewings:
            now_utc = datetime.now(timezone.utc)
            # Check for upcoming viewing in next 24h
            upcoming = [v for v in viewings if v.status == "CONFIRMED" and v.start_utc > now_utc and v.start_utc <= now_utc + timedelta(hours=24)]
            if upcoming:
                v_target = upcoming[0]
                return cls._create_action(
                    lead=lead,
                    organization_id=organization_id,
                    action_type=SalesActionType.VIEWING_REMINDER,
                    reason=f"Upcoming property viewing scheduled for {v_target.start_utc.strftime('%Y-%m-%d %H:%M UTC')}.",
                    priority=88.0,
                    confidence=0.95,
                    props=props,
                    policy=policy,
                    is_timing_permitted=is_timing_permitted,
                    scheduled_for_utc=scheduled_for_utc,
                    customer_timezone=customer_timezone,
                    timing_reason=timing_reason,
                    consent_status=consent_status,
                )

            # Check for recently completed viewing in last 48h
            completed = [v for v in viewings if v.status == "COMPLETED" and v.end_utc and v.end_utc >= now_utc - timedelta(hours=48)]
            if completed:
                # Ensure post viewing follow up was not already sent
                sent_post = any(e.reason_type == SalesActionType.POST_VIEWING_FOLLOW_UP.value for e in prev_execs)
                if not sent_post:
                    return cls._create_action(
                        lead=lead,
                        organization_id=organization_id,
                        action_type=SalesActionType.POST_VIEWING_FOLLOW_UP,
                        reason="Property viewing was completed recently. Follow up to capture buyer feedback and offer intent.",
                        priority=85.0,
                        confidence=0.90,
                        props=props,
                        policy=policy,
                        is_timing_permitted=is_timing_permitted,
                        scheduled_for_utc=scheduled_for_utc,
                        customer_timezone=customer_timezone,
                        timing_reason=timing_reason,
                        consent_status=consent_status,
                    )

        # ── 6. Priority 6: Qualified Lead $\to$ Offer Viewing or Property Recommendations ────
        qual_state = qualification_snapshot.state if qualification_snapshot else "NEW"
        missing_reqs = qualification_snapshot.missing_fields if qualification_snapshot else []

        # Check if customer recently inquired about viewing or accepted viewing prompt
        if latest_customer_message and any(w in latest_customer_message.lower() for w in ["book viewing", "visit tomorrow", "see the property", "schedule visit", "come see"]):
            if qual_state == "QUALIFIED":
                return cls._create_action(
                    lead=lead,
                    organization_id=organization_id,
                    action_type=SalesActionType.BOOK_VIEWING,
                    reason="Qualified client requested or agreed to schedule a site viewing.",
                    priority=90.0,
                    confidence=0.92,
                    props=props,
                    policy=policy,
                    is_timing_permitted=is_timing_permitted,
                    scheduled_for_utc=scheduled_for_utc,
                    customer_timezone=customer_timezone,
                    timing_reason=timing_reason,
                    consent_status=consent_status,
                )

        if qual_state == "QUALIFIED":
            if props_count > 0:
                # Offer private viewing on verified matches
                return cls._create_action(
                    lead=lead,
                    organization_id=organization_id,
                    action_type=SalesActionType.OFFER_VIEWING,
                    reason=f"Lead is qualified and {props_count} verified matching properties are available within budget.",
                    priority=82.0,
                    confidence=0.90,
                    props=props,
                    policy=policy,
                    is_timing_permitted=is_timing_permitted,
                    scheduled_for_utc=scheduled_for_utc,
                    customer_timezone=customer_timezone,
                    timing_reason=timing_reason,
                    consent_status=consent_status,
                )

        # If lead has matching properties and hasn't received recommendations yet
        has_sent_props = any(e.reason_type in (SalesActionType.SEND_PROPERTY_RECOMMENDATIONS.value, "PROPERTY_RECOMMENDATION") for e in prev_execs)
        if props_count > 0 and not has_sent_props and qual_state in ("QUALIFIED", "PARTIALLY_QUALIFIED"):
            return cls._create_action(
                lead=lead,
                organization_id=organization_id,
                action_type=SalesActionType.SEND_PROPERTY_RECOMMENDATIONS,
                reason=f"{props_count} verified matching properties found for lead criteria.",
                priority=78.0,
                confidence=0.88,
                props=props,
                policy=policy,
                is_timing_permitted=is_timing_permitted,
                scheduled_for_utc=scheduled_for_utc,
                customer_timezone=customer_timezone,
                timing_reason=timing_reason,
                consent_status=consent_status,
            )

        # ── 7. Priority 7: Missing Qualification Information ──────────────────
        if qual_state in ("NEW", "COLLECTING_INFORMATION", "PARTIALLY_QUALIFIED") or len(missing_reqs) > 0:
            first_missing = missing_reqs[0] if missing_reqs else "intent"
            return cls._create_action(
                lead=lead,
                organization_id=organization_id,
                action_type=SalesActionType.ASK_QUALIFICATION,
                reason=f"Required qualification information '{first_missing}' is missing.",
                priority=75.0,
                confidence=0.85,
                props=props,
                required_facts=[first_missing],
                policy=policy,
                is_timing_permitted=is_timing_permitted,
                scheduled_for_utc=scheduled_for_utc,
                customer_timezone=customer_timezone,
                timing_reason=timing_reason,
                consent_status=consent_status,
            )

        # ── 8. Priority 8: Follow-Up on Prior Unanswered Actions ─────────────
        if has_sent_props:
            # Check if property recommendation was sent > 24h ago with no reply
            last_prop_exec = next((e for e in reversed(prev_execs) if e.reason_type in (SalesActionType.SEND_PROPERTY_RECOMMENDATIONS.value, "PROPERTY_RECOMMENDATION")), None)
            if last_prop_exec and last_prop_exec.executed_at:
                delta = eval_time - last_prop_exec.executed_at
                if delta >= timedelta(hours=24):
                    return cls._create_action(
                        lead=lead,
                        organization_id=organization_id,
                        action_type=SalesActionType.FOLLOW_UP_PROPERTY_SENT,
                        reason="Property recommendations were shared >24h ago without customer response.",
                        priority=65.0,
                        confidence=0.82,
                        props=props,
                        policy=policy,
                        is_timing_permitted=is_timing_permitted,
                        scheduled_for_utc=scheduled_for_utc,
                        customer_timezone=customer_timezone,
                        timing_reason=timing_reason,
                        consent_status=consent_status,
                    )

        # If general inquiry was sent > 24h ago with no reply
        if prev_execs:
            last_e = prev_execs[-1]
            if last_e.executed_at and (eval_time - last_e.executed_at) >= timedelta(hours=24):
                return cls._create_action(
                    lead=lead,
                    organization_id=organization_id,
                    action_type=SalesActionType.FOLLOW_UP_NO_RESPONSE,
                    reason="Previous outbound outreach unanswered after 24h interval.",
                    priority=60.0,
                    confidence=0.80,
                    props=props,
                    policy=policy,
                    is_timing_permitted=is_timing_permitted,
                    scheduled_for_utc=scheduled_for_utc,
                    customer_timezone=customer_timezone,
                    timing_reason=timing_reason,
                    consent_status=consent_status,
                )

        # ── 9. Default Fallback: NO ACTION ───────────────────────────────────
        return SalesActionDecisionDTO(
            lead_id=str(lead.id),
            organization_id=organization_id,
            action_type=SalesActionType.NO_ACTION,
            status=SalesActionStatus.COMPLETED,
            reason="No sales action currently required. Lead state is up to date.",
            priority=10.0,
            confidence=0.90,
            recommended_channel=CommunicationChannel.WHATSAPP,
            automation_allowed=False,
            human_approval_required=False,
            customer_timezone=customer_timezone,
            policy_version=cls.POLICY_VERSION,
            evaluated_at=eval_time,
        )

    @classmethod
    def _create_action(
        cls,
        lead: Lead,
        organization_id: str,
        action_type: SalesActionType,
        reason: str,
        priority: float,
        confidence: float,
        props: List[Dict[str, Any]],
        policy: Optional[FollowUpPolicy],
        is_timing_permitted: bool,
        scheduled_for_utc: Optional[datetime],
        customer_timezone: str,
        timing_reason: Optional[str],
        consent_status: ConsentStatus,
        required_facts: Optional[List[str]] = None,
    ) -> SalesActionDecisionDTO:
        """Helper to assemble SalesActionDecisionDTO with governance guards."""
        req_approval, approval_reason, _ = HumanApprovalGuard.evaluate_approval_requirement(
            lead=lead,
            policy=policy,
            confidence_score=confidence,
        )

        status = SalesActionStatus.APPROVED
        blocked_reason = None
        automation_allowed = True

        # Check consent block
        if consent_status == ConsentStatus.UNKNOWN:
            status = SalesActionStatus.BLOCKED
            blocked_reason = "No explicit opt-in consent recorded."
            automation_allowed = False
        elif consent_status in (ConsentStatus.DENIED, ConsentStatus.REVOKED):
            status = SalesActionStatus.BLOCKED
            blocked_reason = f"Consent {consent_status.value}"
            automation_allowed = False
        elif req_approval:
            status = SalesActionStatus.HUMAN_REVIEW
            automation_allowed = False
        elif not is_timing_permitted:
            status = SalesActionStatus.QUEUED
            blocked_reason = timing_reason

        return SalesActionDecisionDTO(
            lead_id=str(lead.id),
            organization_id=organization_id,
            action_type=action_type,
            status=status,
            reason=reason,
            priority=priority,
            confidence=confidence,
            recommended_channel=CommunicationChannel.WHATSAPP,
            automation_allowed=automation_allowed,
            human_approval_required=req_approval,
            blocked_reason=blocked_reason,
            scheduled_for_utc=scheduled_for_utc if not is_timing_permitted else None,
            customer_timezone=customer_timezone,
            required_facts=required_facts or [],
            matched_properties_count=len(props),
            matched_properties_summary=props[:3] if props else None,
            policy_version=cls.POLICY_VERSION,
            evaluated_at=datetime.now(timezone.utc),
            next_evaluation_at=scheduled_for_utc if not is_timing_permitted else datetime.now(timezone.utc) + timedelta(hours=24),
        )

    @classmethod
    def _build_sales_brief(
        cls,
        lead: Lead,
        facts: Dict[str, Any],
        matched_props_count: int,
        handoff_reason: str,
        latest_msg: Optional[str],
        recommended_action: str,
    ) -> SalesBriefDTO:
        """Constructs a factual sales brief for human brokers."""
        loc = facts.get("location") or (", ".join(lead.preferred_locations) if lead.preferred_locations else "Not Specified")
        ptype = facts.get("property_type") or lead.property_type or "Not Specified"
        b_max = facts.get("budget_max") or lead.budget_max or 0
        if isinstance(b_max, dict):
            b_max = b_max.get("amount", 0)
        try:
            b_val = float(b_max)
            budget_str = f"Up to {b_val:,.0f} {facts.get('budget_currency', 'AED')}" if b_val > 0 else "Not Specified"
        except (ValueError, TypeError):
            budget_str = str(b_max) if b_max else "Not Specified"

        return SalesBriefDTO(
            lead_id=str(lead.id),
            lead_name=lead.name or "WhatsApp Client",
            lead_intent=facts.get("intent") or (lead.transaction_type.upper() if lead.transaction_type else "UNKNOWN"),
            budget_range=budget_str,
            preferred_location=loc,
            property_type=ptype,
            timeline=facts.get("timeline") or lead.timeline or "Not Specified",
            financing=facts.get("financing") or lead.loan_status or "Not Specified",
            matched_properties_count=matched_props_count,
            handoff_reason=handoff_reason,
            recent_conversation_summary=latest_msg or "No recent message content",
            recommended_human_action=recommended_action,
        )
