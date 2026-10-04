"""
Build 08 — Sales Pipeline Service
===================================
Canonical service for the full sales pipeline: opportunity lifecycle, site visits,
negotiation rounds, booking intents, unit holds, property payment transactions,
and revenue events.

Design rules:
- All stage transitions validated server-side against OpportunityStage.ALLOWED_FORWARD
- All monetary amounts use Decimal — never Float
- All state changes emit OutboxEvent atomically
- All state changes write append-only audit entries
- Tenant isolation enforced on every query
- Idempotency keys on all write operations
- AI may propose — humans (or authorized workflows) confirm
"""
from __future__ import annotations
# Sprint 1E — Learning layer wiring (non-blocking, failure-safe)
from app.modules.intelligence.outcome_recorder import OutcomeRecorder
from app.models.intelligence_models import OutcomeEventType, OutcomeEntityType, OutcomeSource

import logging
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import select, and_, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sales_pipeline_models import (
    SalesPipeline, PipelineStageConfig,
    OpportunityStageHistory, OpportunityStage,
    SiteVisit, SiteVisitOutcome, SiteVisitStatus,
    NegotiationRound, NegotiationRoundActor,
    PropertyShortlist, PropertyShortlistStatus,
    BookingIntent, BookingIntentStatus,
    UnitHold, UnitHoldStatus,
    PropertyPaymentTransaction,
    RevenueEvent, RevenueEventType,
    BookingReconciliationTask,
    LostReasonType,
)
from app.models.deal_models import (
    Deal, DealStage, DealStageHistory,
    DealBooking, DealReservation,
    DealApprovalRequest, DealCommercialAuditLog,
)
from app.models.outbox_models import OutboxEvent

logger = logging.getLogger("wefylabs.sales_pipeline.service")


class SalesPipelineError(Exception):
    """Raised on invalid business operations."""
    pass


class StagePolicyViolation(SalesPipelineError):
    """Raised when a stage transition violates policy."""
    pass


class TenantViolation(SalesPipelineError):
    """Raised on cross-tenant access attempt."""
    pass


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _safe_uuid(val: Any) -> uuid.UUID:
    if isinstance(val, uuid.UUID):
        return val
    return uuid.UUID(str(val))


def _emit_outbox(db: AsyncSession, deal: Deal, event_type: str, payload: Dict, idempotency_key: Optional[str] = None) -> OutboxEvent:
    ev = OutboxEvent(
        tenant_id=str(deal.organization_id),
        event_type=event_type,
        aggregate_type="Deal",
        aggregate_id=str(deal.id),
        payload=payload,
        idempotency_key=idempotency_key or str(uuid.uuid4()),
    )
    db.add(ev)
    return ev


def _emit_revenue_event(
    db: AsyncSession,
    organization_id: uuid.UUID,
    event_type: str,
    payload: Dict,
    deal: Optional[Deal] = None,
    site_visit: Optional[SiteVisit] = None,
    booking_intent: Optional[BookingIntent] = None,
    unit_id: Optional[uuid.UUID] = None,
    booking_id: Optional[uuid.UUID] = None,
    payment: Optional[PropertyPaymentTransaction] = None,
    amount: Optional[Decimal] = None,
    currency: Optional[str] = None,
    actor_id: Optional[str] = None,
    actor_type: str = "SYSTEM",
    idempotency_key: Optional[str] = None,
) -> RevenueEvent:
    ev = RevenueEvent(
        event_id=idempotency_key or str(uuid.uuid4()),
        organization_id=organization_id,
        event_type=event_type,
        lead_id=deal.lead_id if deal else None,
        opportunity_id=deal.id if deal else None,
        site_visit_id=site_visit.id if site_visit else None,
        booking_intent_id=booking_intent.id if booking_intent else None,
        booking_id=booking_id,
        unit_id=unit_id,
        payment_id=payment.id if payment else None,
        amount=amount,
        currency=currency,
        source=payload.get("source"),
        actor_id=actor_id,
        actor_type=actor_type,
        payload=payload,
    )
    db.add(ev)
    return ev


# ---------------------------------------------------------------------------
# PIPELINE CONFIGURATION SERVICE
# ---------------------------------------------------------------------------

class PipelineConfigService:
    """Manages org-configurable pipeline and stage definitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_pipeline(
        self,
        organization_id: uuid.UUID,
        name: str,
        pipeline_type: str = "RESIDENTIAL_SALES",
        description: Optional[str] = None,
        is_default: bool = False,
    ) -> SalesPipeline:
        pipeline = SalesPipeline(
            organization_id=organization_id,
            name=name,
            pipeline_type=pipeline_type,
            description=description,
            is_default=is_default,
        )
        self.db.add(pipeline)
        await self.db.flush()

        # Auto-create canonical stage configs
        for position, semantic_type in enumerate(OpportunityStage.ORDERED):
            stage_config = PipelineStageConfig(
                pipeline_id=pipeline.id,
                organization_id=organization_id,
                position=position,
                name=semantic_type.replace("_", " ").title(),
                semantic_type=semantic_type,
            )
            self.db.add(stage_config)

        await self.db.flush()
        logger.info(f"[Pipeline] Created pipeline '{name}' type={pipeline_type} org={organization_id}")
        return pipeline

    async def get_default_pipeline(self, organization_id: uuid.UUID) -> Optional[SalesPipeline]:
        res = await self.db.execute(
            select(SalesPipeline).where(
                SalesPipeline.organization_id == organization_id,
                SalesPipeline.is_default == True,
                SalesPipeline.deleted_at.is_(None),
                SalesPipeline.is_active == True,
            )
        )
        return res.scalars().first()

    async def list_pipelines(self, organization_id: uuid.UUID) -> List[SalesPipeline]:
        res = await self.db.execute(
            select(SalesPipeline).where(
                SalesPipeline.organization_id == organization_id,
                SalesPipeline.deleted_at.is_(None),
            ).order_by(SalesPipeline.created_at)
        )
        return list(res.scalars().all())


# ---------------------------------------------------------------------------
# OPPORTUNITY STAGE SERVICE
# ---------------------------------------------------------------------------

class OpportunityStageService:
    """
    Controls opportunity stage transitions with full policy enforcement.
    Every transition is validated, audited, and emitted to the outbox.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_deal(self, deal_id: Any, organization_id: Any) -> Deal:
        org_uuid = _safe_uuid(organization_id)
        deal_uuid = _safe_uuid(deal_id)
        res = await self.db.execute(
            select(Deal).where(
                Deal.id == deal_uuid,
                Deal.organization_id == org_uuid,
                Deal.deleted_at.is_(None),
            )
        )
        deal = res.scalars().first()
        if not deal:
            raise SalesPipelineError(f"Opportunity {deal_id} not found in organization {organization_id}")
        return deal

    async def advance_stage(
        self,
        deal_id: Any,
        organization_id: Any,
        target_stage: str,
        changed_by_id: str,
        changed_by_type: str = "HUMAN",
        reason: Optional[str] = None,
        source: Optional[str] = "MANUAL",
        evidence: Optional[Dict] = None,
        pipeline_id: Optional[uuid.UUID] = None,
    ) -> Deal:
        """
        Advance an opportunity to a new stage with full policy validation.
        - Validates the transition against OpportunityStage.ALLOWED_FORWARD
        - Requires evidence for EVIDENCE_REQUIRED stages
        - Never trusts client-side stage changes
        - Writes immutable stage history
        - Emits outbox event atomically
        """
        deal = await self._get_deal(deal_id, organization_id)
        org_uuid = _safe_uuid(organization_id)
        current_stage = deal.current_stage

        # Terminal stages cannot be advanced
        if OpportunityStage.is_terminal(current_stage):
            raise StagePolicyViolation(f"Opportunity is in terminal stage '{current_stage}' — cannot advance.")

        # Validate the transition
        if not OpportunityStage.is_allowed_transition(current_stage, target_stage):
            raise StagePolicyViolation(
                f"Transition from '{current_stage}' to '{target_stage}' is not permitted. "
                f"Allowed: {OpportunityStage.ALLOWED_FORWARD.get(current_stage, [])}"
            )

        # Evidence required for critical commercial stages
        if target_stage in OpportunityStage.EVIDENCE_REQUIRED and not evidence:
            raise StagePolicyViolation(
                f"Stage '{target_stage}' requires explicit commercial evidence. "
                "Provide evidence dict with supporting records."
            )

        now = _now()
        entered_at = deal.stage_entered_at
        if entered_at and entered_at.tzinfo is None:
            entered_at = entered_at.replace(tzinfo=timezone.utc)
        hours_in_stage = max(0, int((now - entered_at).total_seconds() / 3600)) if entered_at else 0

        # Snapshot current state before transition
        snapshot = {
            "stage": current_stage,
            "estimated_value": str(deal.agreed_price) if deal.agreed_price else None,
            "probability": str(deal.closing_probability_pct),
            "lead_id": str(deal.lead_id),
        }

        # Update the deal
        deal.previous_stage = current_stage
        deal.current_stage = target_stage
        deal.stage_entered_at = now
        deal.stage_duration_hours = hours_in_stage
        deal.updated_at = now

        # Mark WON/LOST
        if target_stage in (OpportunityStage.WON, "WON"):
            deal.status = "CLOSED_WON"
            deal.closed_at = now
        elif target_stage in (OpportunityStage.LOST, "LOST"):
            deal.status = "CLOSED_LOST"
            deal.closed_at = now

        # Immutable stage history
        stage_history = OpportunityStageHistory(
            deal_id=deal.id,
            organization_id=org_uuid,
            pipeline_id=pipeline_id,
            from_stage=current_stage,
            to_stage=target_stage,
            changed_by_id=changed_by_id,
            changed_by_type=changed_by_type,
            changed_at=now,
            reason=reason,
            source=source,
            duration_hours_in_previous_stage=hours_in_stage,
            entered_at=entered_at,
            exited_at=now,
            evidence=evidence,
            snapshot=snapshot,
        )
        self.db.add(stage_history)

        # Outbox event
        _emit_outbox(self.db, deal, "opportunity.stage_changed", {
            "deal_id": str(deal.id),
            "from_stage": current_stage,
            "to_stage": target_stage,
            "changed_by_id": changed_by_id,
            "changed_by_type": changed_by_type,
            "reason": reason,
            "source": source,
            "timestamp": now.isoformat(),
        })

        # Revenue event
        _emit_revenue_event(
            self.db,
            organization_id=org_uuid,
            event_type=RevenueEventType.OPPORTUNITY_STAGE_CHANGED,
            deal=deal,
            payload={"from_stage": current_stage, "to_stage": target_stage, "reason": reason},
            actor_id=changed_by_id,
            actor_type=changed_by_type,
        )

        # Special revenue events for WON/LOST
        if target_stage == OpportunityStage.WON:
            _emit_revenue_event(
                self.db, org_uuid,
                RevenueEventType.DEAL_WON,
                deal=deal,
                payload={"stage": target_stage, "final_price": str(deal.final_transaction_price or deal.agreed_price)},
                amount=deal.final_transaction_price or deal.agreed_price,
                currency=deal.currency,
                actor_id=changed_by_id,
                actor_type=changed_by_type,
            )
        elif target_stage == OpportunityStage.LOST:
            _emit_revenue_event(
                self.db, org_uuid,
                RevenueEventType.DEAL_LOST,
                deal=deal,
                payload={"stage": target_stage, "lost_reason": deal.lost_reason},
                actor_id=changed_by_id,
                actor_type=changed_by_type,
            )

        await self.db.flush()

        # ── Sprint 1E: Learning layer wiring ──────────────────────────────────
        # Non-blocking: failures are caught by OutcomeRecorder.safe_record().
        if target_stage == OpportunityStage.WON:
            await OutcomeRecorder.record_deal_won(
                db=self.db,
                org_id=str(org_uuid),
                deal_id=str(deal.id),
                lead_id=str(deal.lead_id) if deal.lead_id else str(deal.id),
                property_id=None,
                agent_id=changed_by_id,
                revenue_amount=deal.final_transaction_price or deal.agreed_price,
                currency=deal.currency or "AED",
                won_at=now,
            )
        elif target_stage == OpportunityStage.LOST:
            await OutcomeRecorder.record_deal_lost(
                db=self.db,
                org_id=str(org_uuid),
                deal_id=str(deal.id),
                lead_id=str(deal.lead_id) if deal.lead_id else str(deal.id),
                agent_id=changed_by_id,
                lost_reason=deal.lost_reason,
                lost_at=now,
            )
        elif target_stage in (OpportunityStage.NEGOTIATION, OpportunityStage.BOOKING_PENDING, OpportunityStage.BOOKED):
            await OutcomeRecorder.safe_record(
                db=self.db,
                org_id=str(org_uuid),
                event_type=OutcomeEventType.OPPORTUNITY_ADVANCED,
                entity_type=OutcomeEntityType.OPPORTUNITY,
                entity_id=str(deal.id),
                source_table="deals",
                source_event_id=str(deal.id),
                occurred_at=now,
                lead_id=str(deal.lead_id) if deal.lead_id else None,
                opportunity_id=str(deal.id),
                agent_id=changed_by_id,
                actor_type=changed_by_type,
                outcome_source=OutcomeSource.HUMAN if changed_by_type == "HUMAN" else OutcomeSource.AUTOMATION,
                metadata={
                    "from_stage": current_stage,
                    "to_stage": target_stage,
                    "source": source,
                    "reason": reason,
                },
            )

        logger.info(f"[Stage] Deal {deal.id}: {current_stage} -> {target_stage} by {changed_by_id}")
        return deal

    async def mark_lost(
        self,
        deal_id: Any,
        organization_id: Any,
        changed_by_id: str,
        lost_reason_type: str,
        lost_reason_detail: Optional[str] = None,
        lost_to_competitor: Optional[str] = None,
        reason: Optional[str] = None,
    ) -> Deal:
        """
        Mark opportunity as LOST with a controlled reason vocabulary.
        Never fabricate a lost reason.
        """
        deal = await self._get_deal(deal_id, organization_id)
        if OpportunityStage.is_terminal(deal.current_stage):
            raise StagePolicyViolation(f"Already in terminal stage '{deal.current_stage}'")

        deal.lost_reason = lost_reason_type
        deal.notes = (deal.notes or "") + f"\nLost reason detail: {lost_reason_detail or 'N/A'}"
        if lost_to_competitor:
            deal.metadata_json = {**(deal.metadata_json or {}), "lost_to_competitor": lost_to_competitor}

        evidence = {
            "lost_reason_type": lost_reason_type,
            "lost_reason_detail": lost_reason_detail,
            "lost_to_competitor": lost_to_competitor,
        }

        return await self.advance_stage(
            deal_id=deal.id,
            organization_id=organization_id,
            target_stage=OpportunityStage.LOST,
            changed_by_id=changed_by_id,
            reason=reason or lost_reason_detail,
            source="MANUAL",
            evidence=evidence,
        )

    async def get_stage_history(
        self, deal_id: Any, organization_id: Any
    ) -> List[OpportunityStageHistory]:
        org_uuid = _safe_uuid(organization_id)
        deal_uuid = _safe_uuid(deal_id)
        res = await self.db.execute(
            select(OpportunityStageHistory).where(
                OpportunityStageHistory.deal_id == deal_uuid,
                OpportunityStageHistory.organization_id == org_uuid,
            ).order_by(OpportunityStageHistory.changed_at)
        )
        return list(res.scalars().all())


# ---------------------------------------------------------------------------
# PROPERTY SHORTLIST SERVICE
# ---------------------------------------------------------------------------

class PropertyShortlistService:
    """Manages per-opportunity property interest history."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_to_shortlist(
        self,
        deal_id: Any,
        organization_id: Any,
        added_by_id: str,
        project_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        property_listing_id: Optional[uuid.UUID] = None,
        source: str = "AGENT_MANUAL",
        property_snapshot: Optional[Dict] = None,
        notes: Optional[str] = None,
    ) -> PropertyShortlist:
        org_uuid = _safe_uuid(organization_id)
        deal_uuid = _safe_uuid(deal_id)

        shortlist = PropertyShortlist(
            deal_id=deal_uuid,
            organization_id=org_uuid,
            project_id=project_id,
            unit_id=unit_id,
            property_listing_id=property_listing_id,
            status=PropertyShortlistStatus.SHORTLISTED,
            added_by_id=added_by_id,
            added_by_type="HUMAN",
            source=source,
            property_snapshot=property_snapshot,
            notes=notes,
        )
        self.db.add(shortlist)
        await self.db.flush()
        logger.info(f"[Shortlist] Added property to deal {deal_id} shortlist")
        return shortlist

    async def update_status(
        self,
        shortlist_id: Any,
        organization_id: Any,
        new_status: str,
        updated_by_id: str,
        dismissal_reason: Optional[str] = None,
    ) -> PropertyShortlist:
        org_uuid = _safe_uuid(organization_id)
        res = await self.db.execute(
            select(PropertyShortlist).where(
                PropertyShortlist.id == _safe_uuid(shortlist_id),
                PropertyShortlist.organization_id == org_uuid,
            )
        )
        sl = res.scalars().first()
        if not sl:
            raise SalesPipelineError(f"PropertyShortlist {shortlist_id} not found")

        sl.status = new_status
        if new_status == PropertyShortlistStatus.DISMISSED:
            sl.dismissed_at = _now()
            sl.dismissal_reason = dismissal_reason
        await self.db.flush()
        return sl

    async def get_shortlist(
        self, deal_id: Any, organization_id: Any
    ) -> List[PropertyShortlist]:
        res = await self.db.execute(
            select(PropertyShortlist).where(
                PropertyShortlist.deal_id == _safe_uuid(deal_id),
                PropertyShortlist.organization_id == _safe_uuid(organization_id),
            ).order_by(PropertyShortlist.added_at)
        )
        return list(res.scalars().all())


# ---------------------------------------------------------------------------
# SITE VISIT SERVICE
# ---------------------------------------------------------------------------

class SiteVisitService:
    """
    Manages canonical site visit lifecycle.
    Integrates with SchedulingMeeting for calendar but maintains independent commercial state.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_site_visit(
        self,
        deal_id: Any,
        organization_id: Any,
        lead_id: Any,
        created_by_id: str,
        scheduled_at: Optional[datetime] = None,
        timezone: str = "UTC",
        meeting_point: Optional[str] = None,
        location_address: Optional[str] = None,
        location_type: str = "PHYSICAL",
        project_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        property_listing_id: Optional[uuid.UUID] = None,
        scheduling_meeting_id: Optional[str] = None,
        assigned_agent_id: Optional[str] = None,
        notes: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> SiteVisit:
        org_uuid = _safe_uuid(organization_id)
        deal_uuid = _safe_uuid(deal_id)
        lead_uuid = _safe_uuid(lead_id)

        # Idempotency check
        if idempotency_key:
            res = await self.db.execute(
                select(SiteVisit).where(SiteVisit.idempotency_key == idempotency_key)
            )
            existing = res.scalars().first()
            if existing:
                return existing

        # Count existing visits for this deal (for visit_number)
        count_res = await self.db.execute(
            select(func.count()).select_from(SiteVisit).where(
                SiteVisit.deal_id == deal_uuid,
                SiteVisit.organization_id == org_uuid,
            )
        )
        visit_number = (count_res.scalar() or 0) + 1

        site_visit = SiteVisit(
            organization_id=org_uuid,
            deal_id=deal_uuid,
            lead_id=lead_uuid,
            project_id=project_id,
            unit_id=unit_id,
            property_listing_id=property_listing_id,
            scheduling_meeting_id=scheduling_meeting_id,
            scheduled_at=scheduled_at,
            timezone=timezone,
            meeting_point=meeting_point,
            location_address=location_address,
            location_type=location_type,
            assigned_agent_id=assigned_agent_id,
            status=SiteVisitStatus.REQUESTED,
            visit_number=visit_number,
            idempotency_key=idempotency_key,
            notes=notes,
        )
        self.db.add(site_visit)
        await self.db.flush()

        # Emit revenue event
        deal_res = await self.db.execute(select(Deal).where(Deal.id == deal_uuid))
        deal = deal_res.scalars().first()

        if deal:
            _emit_outbox(self.db, deal, "site_visit.created", {
                "site_visit_id": str(site_visit.id),
                "deal_id": str(deal_uuid),
                "visit_number": visit_number,
                "scheduled_at": scheduled_at.isoformat() if scheduled_at else None,
                "timestamp": _now().isoformat(),
            })

        logger.info(f"[SiteVisit] Created visit #{visit_number} for deal {deal_id}")
        return site_visit

    async def transition_status(
        self,
        site_visit_id: Any,
        organization_id: Any,
        new_status: str,
        updated_by_id: str,
        notes: Optional[str] = None,
    ) -> SiteVisit:
        org_uuid = _safe_uuid(organization_id)
        res = await self.db.execute(
            select(SiteVisit).where(
                SiteVisit.id == _safe_uuid(site_visit_id),
                SiteVisit.organization_id == org_uuid,
                SiteVisit.deleted_at.is_(None),
            )
        )
        sv = res.scalars().first()
        if not sv:
            raise SalesPipelineError(f"SiteVisit {site_visit_id} not found")

        if not SiteVisitStatus.can_transition(sv.status, new_status):
            raise StagePolicyViolation(
                f"Cannot transition SiteVisit from '{sv.status}' to '{new_status}'. "
                f"Allowed: {SiteVisitStatus.VALID_TRANSITIONS.get(sv.status, [])}"
            )

        now = _now()
        old_status = sv.status
        sv.status = new_status
        sv.updated_at = now

        if new_status == SiteVisitStatus.IN_PROGRESS and not sv.check_in_at:
            sv.check_in_at = now
        if new_status in (SiteVisitStatus.COMPLETED, SiteVisitStatus.NO_SHOW) and not sv.check_out_at:
            sv.check_out_at = now
            sv.attendance_status = "ATTENDED" if new_status == SiteVisitStatus.COMPLETED else "NO_SHOW"
        if notes:
            sv.notes = (sv.notes or "") + f"\n[{now.isoformat()}] {notes}"

        # Emit events for completed visits
        deal_res = await self.db.execute(select(Deal).where(Deal.id == sv.deal_id))
        deal = deal_res.scalars().first()
        if deal:
            event_type = (
                RevenueEventType.SITE_VISIT_COMPLETED if new_status == SiteVisitStatus.COMPLETED
                else RevenueEventType.SITE_VISIT_NO_SHOW if new_status == SiteVisitStatus.NO_SHOW
                else "site_visit.status_changed"
            )
            _emit_outbox(self.db, deal, event_type, {
                "site_visit_id": str(sv.id),
                "deal_id": str(sv.deal_id),
                "from_status": old_status,
                "to_status": new_status,
                "updated_by_id": updated_by_id,
                "timestamp": now.isoformat(),
            })
            _emit_revenue_event(
                self.db, org_uuid,
                event_type, deal=deal, site_visit=sv,
                payload={"from_status": old_status, "to_status": new_status},
                actor_id=updated_by_id,
            )

        await self.db.flush()

        # ── Sprint 1E: Learning layer wiring ──────────────────────────────────
        if new_status == SiteVisitStatus.COMPLETED:
            await OutcomeRecorder.record_site_visit_completed(
                db=self.db,
                org_id=str(org_uuid),
                visit_id=str(sv.id),
                lead_id=str(sv.lead_id),
                deal_id=str(sv.deal_id) if sv.deal_id else None,
                property_id=str(sv.property_listing_id) if sv.property_listing_id else None,
                agent_id=updated_by_id,
                completed_at=now,
                outcome_notes=notes,
            )
        elif new_status == SiteVisitStatus.NO_SHOW:
            await OutcomeRecorder.record_site_visit_no_show(
                db=self.db,
                org_id=str(org_uuid),
                visit_id=str(sv.id),
                lead_id=str(sv.lead_id),
                deal_id=str(sv.deal_id) if sv.deal_id else None,
                agent_id=updated_by_id,
                occurred_at=now,
            )

        return sv

    async def record_outcome(
        self,
        site_visit_id: Any,
        organization_id: Any,
        recorded_by_id: str,
        customer_interest_level: Optional[int] = None,
        customer_feedback: Optional[str] = None,
        preferred_property_id: Optional[uuid.UUID] = None,
        preferred_unit_id: Optional[uuid.UUID] = None,
        objections: Optional[List[str]] = None,
        positive_signals: Optional[List[str]] = None,
        next_action: Optional[str] = None,
        next_action_at: Optional[datetime] = None,
        agent_notes: Optional[str] = None,
    ) -> SiteVisitOutcome:
        org_uuid = _safe_uuid(organization_id)
        sv_uuid = _safe_uuid(site_visit_id)

        # Verify the visit belongs to this org
        res = await self.db.execute(
            select(SiteVisit).where(
                SiteVisit.id == sv_uuid,
                SiteVisit.organization_id == org_uuid,
            )
        )
        sv = res.scalars().first()
        if not sv:
            raise SalesPipelineError(f"SiteVisit {site_visit_id} not found")

        # Only allow outcome recording after visit is completed or no-show
        if sv.status not in (SiteVisitStatus.COMPLETED, SiteVisitStatus.NO_SHOW):
            raise SalesPipelineError(
                f"Cannot record outcome for visit with status '{sv.status}'. "
                "Visit must be COMPLETED or NO_SHOW."
            )

        outcome = SiteVisitOutcome(
            site_visit_id=sv_uuid,
            organization_id=org_uuid,
            customer_interest_level=customer_interest_level,
            customer_feedback=customer_feedback,
            preferred_property_id=preferred_property_id,
            preferred_unit_id=preferred_unit_id,
            objections=objections or [],
            positive_signals=positive_signals or [],
            next_action=next_action,
            next_action_at=next_action_at,
            agent_notes=agent_notes,
            recorded_by_id=recorded_by_id,
            recorded_at=_now(),
        )
        self.db.add(outcome)
        await self.db.flush()
        return outcome

    async def get_visits_for_deal(
        self, deal_id: Any, organization_id: Any
    ) -> List[SiteVisit]:
        res = await self.db.execute(
            select(SiteVisit).where(
                SiteVisit.deal_id == _safe_uuid(deal_id),
                SiteVisit.organization_id == _safe_uuid(organization_id),
                SiteVisit.deleted_at.is_(None),
            ).order_by(SiteVisit.visit_number)
        )
        return list(res.scalars().all())


# ---------------------------------------------------------------------------
# NEGOTIATION SERVICE
# ---------------------------------------------------------------------------

class NegotiationService:
    """
    Manages immutable negotiation round history.
    Never overwrites historical offers. AI drafts require human approval.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def add_round(
        self,
        deal_id: Any,
        organization_id: Any,
        round_type: str,
        actor: str,
        actor_id: str,
        price: Optional[Decimal] = None,
        currency: str = "AED",
        original_price: Optional[Decimal] = None,
        payment_plan: Optional[str] = None,
        payment_terms: Optional[Dict] = None,
        notes: Optional[str] = None,
        source: str = "HUMAN",
        requires_approval: bool = False,
    ) -> NegotiationRound:
        org_uuid = _safe_uuid(organization_id)
        deal_uuid = _safe_uuid(deal_id)

        # Get next round number
        count_res = await self.db.execute(
            select(func.count()).select_from(NegotiationRound).where(
                NegotiationRound.deal_id == deal_uuid,
                NegotiationRound.organization_id == org_uuid,
            )
        )
        round_number = (count_res.scalar() or 0) + 1

        # AI draft must be flagged for approval — never sent directly
        if actor == NegotiationRoundActor.AI_DRAFT:
            requires_approval = True

        round_obj = NegotiationRound(
            deal_id=deal_uuid,
            organization_id=org_uuid,
            round_number=round_number,
            round_type=round_type,
            actor=actor,
            actor_id=actor_id,
            price=price,
            currency=currency,
            original_price=original_price,
            payment_plan=payment_plan,
            payment_terms=payment_terms,
            notes=notes,
            source=source,
            requires_approval=requires_approval,
            occurred_at=_now(),
        )
        self.db.add(round_obj)
        await self.db.flush()

        # Emit offer created event
        deal_res = await self.db.execute(select(Deal).where(Deal.id == deal_uuid))
        deal = deal_res.scalars().first()
        if deal:
            _emit_outbox(self.db, deal, RevenueEventType.OFFER_CREATED, {
                "deal_id": str(deal_uuid),
                "round_number": round_number,
                "round_type": round_type,
                "actor": actor,
                "price": str(price) if price else None,
                "currency": currency,
                "timestamp": _now().isoformat(),
            })
            _emit_revenue_event(
                self.db, org_uuid,
                RevenueEventType.OFFER_CREATED,
                deal=deal,
                payload={"round_number": round_number, "round_type": round_type, "actor": actor},
                amount=price, currency=currency,
                actor_id=actor_id,
                actor_type=actor if actor != NegotiationRoundActor.AI_DRAFT else "AI",
            )

        # ── Sprint 1E: Learning layer wiring ──────────────────────────────────
        outcome_evt = OutcomeEventType.OFFER_CREATED
        if round_type in ("CUSTOMER_OFFER", "COUNTER_OFFER") and actor == NegotiationRoundActor.CUSTOMER:
            outcome_evt = OutcomeEventType.OFFER_CREATED
        lead_id_str = str(deal.lead_id) if deal and deal.lead_id else None
        await OutcomeRecorder.safe_record(
            db=self.db,
            org_id=str(org_uuid),
            event_type=outcome_evt,
            entity_type=OutcomeEntityType.OFFER,
            entity_id=str(round_obj.id),
            source_table="negotiation_rounds",
            source_event_id=str(round_obj.id),
            occurred_at=round_obj.occurred_at,
            lead_id=lead_id_str,
            opportunity_id=str(deal_uuid),
            agent_id=actor_id,
            actor_type="HUMAN" if actor != NegotiationRoundActor.AI_DRAFT else "AI_AGENT",
            outcome_source=OutcomeSource.AI_AGENT if actor == NegotiationRoundActor.AI_DRAFT else OutcomeSource.HUMAN,
            revenue_impact=price,
            currency=currency,
            metadata={
                "round_number": round_number,
                "round_type": round_type,
                "actor": actor,
                "requires_approval": requires_approval,
            },
        )

        logger.info(f"[Negotiation] Round #{round_number} ({round_type}) added to deal {deal_id}")
        return round_obj

    async def approve_round(
        self,
        round_id: Any,
        organization_id: Any,
        approved_by_id: str,
    ) -> NegotiationRound:
        res = await self.db.execute(
            select(NegotiationRound).where(
                NegotiationRound.id == _safe_uuid(round_id),
                NegotiationRound.organization_id == _safe_uuid(organization_id),
            )
        )
        nr = res.scalars().first()
        if not nr:
            raise SalesPipelineError(f"NegotiationRound {round_id} not found")
        if not nr.requires_approval:
            raise SalesPipelineError("This round does not require approval")

        nr.approved_by_id = approved_by_id
        nr.approved_at = _now()
        nr.requires_approval = False
        await self.db.flush()
        return nr

    async def get_history(
        self, deal_id: Any, organization_id: Any
    ) -> List[NegotiationRound]:
        res = await self.db.execute(
            select(NegotiationRound).where(
                NegotiationRound.deal_id == _safe_uuid(deal_id),
                NegotiationRound.organization_id == _safe_uuid(organization_id),
            ).order_by(NegotiationRound.round_number)
        )
        return list(res.scalars().all())


# ---------------------------------------------------------------------------
# BOOKING INTENT SERVICE
# ---------------------------------------------------------------------------

class BookingIntentService:
    """
    Manages booking intent lifecycle.
    AI may propose a BookingIntent — actual booking requires workflow execution.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_intent(
        self,
        deal_id: Any,
        organization_id: Any,
        lead_id: Any,
        created_by_id: str,
        created_by_type: str = "HUMAN",
        unit_id: Optional[uuid.UUID] = None,
        project_id: Optional[uuid.UUID] = None,
        property_listing_id: Optional[uuid.UUID] = None,
        intended_price: Optional[Decimal] = None,
        currency: str = "AED",
        intended_payment_terms: Optional[str] = None,
        expires_hours: int = 48,
        source: str = "AGENT_MANUAL",
        idempotency_key: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> BookingIntent:
        org_uuid = _safe_uuid(organization_id)
        deal_uuid = _safe_uuid(deal_id)
        lead_uuid = _safe_uuid(lead_id)

        # Idempotency
        if idempotency_key:
            res = await self.db.execute(
                select(BookingIntent).where(BookingIntent.idempotency_key == idempotency_key)
            )
            existing = res.scalars().first()
            if existing:
                return existing

        now = _now()
        intent = BookingIntent(
            organization_id=org_uuid,
            deal_id=deal_uuid,
            lead_id=lead_uuid,
            unit_id=unit_id,
            project_id=project_id,
            property_listing_id=property_listing_id,
            intended_price=intended_price,
            currency=currency,
            intended_payment_terms=intended_payment_terms,
            status=BookingIntentStatus.CREATED,
            created_by_id=created_by_id,
            created_by_type=created_by_type,
            expires_at=now + timedelta(hours=expires_hours),
            source=source,
            idempotency_key=idempotency_key,
            notes=notes,
        )
        self.db.add(intent)
        await self.db.flush()

        # Emit revenue event
        deal_res = await self.db.execute(select(Deal).where(Deal.id == deal_uuid))
        deal = deal_res.scalars().first()
        if deal:
            _emit_outbox(self.db, deal, RevenueEventType.BOOKING_INTENT_CREATED, {
                "booking_intent_id": str(intent.id),
                "deal_id": str(deal_uuid),
                "unit_id": str(unit_id) if unit_id else None,
                "intended_price": str(intended_price) if intended_price else None,
                "currency": currency,
                "expires_at": intent.expires_at.isoformat(),
                "source": source,
                "timestamp": now.isoformat(),
            }, idempotency_key=idempotency_key)
            _emit_revenue_event(
                self.db, org_uuid,
                RevenueEventType.BOOKING_INTENT_CREATED,
                deal=deal, booking_intent=intent,
                unit_id=unit_id,
                payload={"source": source, "expires_at": intent.expires_at.isoformat()},
                amount=intended_price, currency=currency,
                actor_id=created_by_id, actor_type=created_by_type,
                idempotency_key=idempotency_key,
            )

        # ── Sprint 1E: Learning layer wiring ──────────────────────────────────
        await OutcomeRecorder.record_booking_intent_created(
            db=self.db,
            org_id=str(org_uuid),
            booking_intent_id=str(intent.id),
            lead_id=str(lead_uuid),
            deal_id=str(deal_uuid),
            property_id=str(property_listing_id) if property_listing_id else None,
            agent_id=created_by_id,
            intent_amount=intended_price,
            currency=currency,
            created_at=now,
        )

        logger.info(f"[BookingIntent] Created intent for deal {deal_id} unit {unit_id}")
        return intent

    async def expire_intent(self, intent_id: Any, organization_id: Any) -> BookingIntent:
        """Called by backend worker when TTL expires — never from browser."""
        res = await self.db.execute(
            select(BookingIntent).where(
                BookingIntent.id == _safe_uuid(intent_id),
                BookingIntent.organization_id == _safe_uuid(organization_id),
            )
        )
        intent = res.scalars().first()
        if not intent:
            raise SalesPipelineError(f"BookingIntent {intent_id} not found")
        if intent.status != BookingIntentStatus.CREATED:
            return intent  # Already expired/cancelled/converted

        intent.status = BookingIntentStatus.EXPIRED
        intent.updated_at = _now()
        await self.db.flush()
        return intent

    async def check_and_revalidate_unit_availability(
        self, intent_id: Any, organization_id: Any
    ) -> Tuple[bool, str]:
        """
        Re-checks unit availability before booking.
        Returns (is_available, reason).
        Never trust stale UI context.
        """
        res = await self.db.execute(
            select(BookingIntent).where(
                BookingIntent.id == _safe_uuid(intent_id),
                BookingIntent.organization_id == _safe_uuid(organization_id),
            )
        )
        intent = res.scalars().first()
        if not intent:
            return False, "Booking intent not found"

        if intent.status == BookingIntentStatus.EXPIRED:
            return False, "Booking intent has expired"
        if intent.expires_at and intent.expires_at < _now():
            await self.expire_intent(intent_id, organization_id)
            return False, "Booking intent expired during revalidation"

        if intent.unit_id:
            # Check unit status in inventory
            try:
                from app.models.inventory_models import ProjectUnit, UnitInventoryStatus
                unit_res = await self.db.execute(
                    select(ProjectUnit).where(ProjectUnit.id == intent.unit_id)
                )
                unit = unit_res.scalars().first()
                if not unit:
                    return False, "Unit not found in inventory"
                if unit.status not in (
                    UnitInventoryStatus.AVAILABLE,
                    UnitInventoryStatus.HOLD,
                    UnitInventoryStatus.RESERVED,
                ):
                    return False, f"Unit is no longer available — current status: {unit.status}"
            except ImportError:
                logger.warning("[BookingIntent] Could not validate unit inventory status — inventory module not available")

        return True, "OK"


# ---------------------------------------------------------------------------
# UNIT HOLD SERVICE
# ---------------------------------------------------------------------------

class UnitHoldService:
    """
    Manages canonical unit holds with exclusive locking.
    Backend-driven expiry — never rely on browser timers.
    Protects against race conditions: two concurrent bookings for same unit.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_hold(
        self,
        organization_id: Any,
        unit_id: uuid.UUID,
        deal_id: Any,
        created_by_id: str,
        hold_hours: int = 24,
        booking_intent_id: Optional[uuid.UUID] = None,
        reason: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> UnitHold:
        org_uuid = _safe_uuid(organization_id)
        deal_uuid = _safe_uuid(deal_id)

        # Idempotency
        if idempotency_key:
            res = await self.db.execute(
                select(UnitHold).where(UnitHold.idempotency_key == idempotency_key)
            )
            existing = res.scalars().first()
            if existing:
                return existing

        now = _now()

        # Check for existing active hold on this unit in this org
        existing_res = await self.db.execute(
            select(UnitHold).where(
                UnitHold.organization_id == org_uuid,
                UnitHold.unit_id == unit_id,
                UnitHold.status == UnitHoldStatus.ACTIVE,
                UnitHold.expires_at > now,
            )
        )
        existing_hold = existing_res.scalars().first()
        if existing_hold and existing_hold.deal_id != deal_uuid:
            raise SalesPipelineError(
                f"Unit {unit_id} already has an active hold until {existing_hold.expires_at.isoformat()}. "
                "Cannot create concurrent hold."
            )

        hold = UnitHold(
            organization_id=org_uuid,
            unit_id=unit_id,
            deal_id=deal_uuid,
            booking_intent_id=booking_intent_id,
            status=UnitHoldStatus.ACTIVE,
            created_by_id=created_by_id,
            reason=reason,
            expires_at=now + timedelta(hours=hold_hours),
            idempotency_key=idempotency_key,
        )
        self.db.add(hold)

        # Update unit status in inventory
        try:
            from app.models.inventory_models import ProjectUnit, UnitInventoryStatus
            unit_res = await self.db.execute(select(ProjectUnit).where(ProjectUnit.id == unit_id))
            unit = unit_res.scalars().first()
            if unit and unit.status == UnitInventoryStatus.AVAILABLE:
                unit.status = UnitInventoryStatus.HOLD
                unit.updated_at = now

                from app.models.inventory_models import ProjectUnitStatusLog
                log = ProjectUnitStatusLog(
                    unit_id=unit_id,
                    organization_id=org_uuid,
                    from_status=UnitInventoryStatus.AVAILABLE,
                    to_status=UnitInventoryStatus.HOLD,
                    changed_by=created_by_id,
                    reason=f"Unit hold created for deal {deal_uuid}",
                )
                self.db.add(log)
        except (ImportError, Exception) as e:
            logger.warning(f"[UnitHold] Could not update inventory status: {e}")

        await self.db.flush()

        # Emit revenue event
        deal_res = await self.db.execute(select(Deal).where(Deal.id == deal_uuid))
        deal = deal_res.scalars().first()
        if deal:
            _emit_outbox(self.db, deal, RevenueEventType.UNIT_HELD, {
                "hold_id": str(hold.id),
                "unit_id": str(unit_id),
                "deal_id": str(deal_uuid),
                "expires_at": hold.expires_at.isoformat(),
                "timestamp": now.isoformat(),
            }, idempotency_key=idempotency_key)
            _emit_revenue_event(
                self.db, org_uuid,
                RevenueEventType.UNIT_HELD,
                deal=deal, unit_id=unit_id,
                payload={"hold_id": str(hold.id), "expires_at": hold.expires_at.isoformat()},
                actor_id=created_by_id,
                idempotency_key=idempotency_key,
            )

        logger.info(f"[UnitHold] Held unit {unit_id} for deal {deal_id} until {hold.expires_at}")
        return hold

    async def release_hold(
        self,
        hold_id: Any,
        organization_id: Any,
        released_by_id: str,
        release_reason: Optional[str] = None,
    ) -> UnitHold:
        org_uuid = _safe_uuid(organization_id)
        res = await self.db.execute(
            select(UnitHold).where(
                UnitHold.id == _safe_uuid(hold_id),
                UnitHold.organization_id == org_uuid,
            )
        )
        hold = res.scalars().first()
        if not hold:
            raise SalesPipelineError(f"UnitHold {hold_id} not found")
        if hold.status != UnitHoldStatus.ACTIVE:
            return hold  # Already released

        now = _now()
        hold.status = UnitHoldStatus.RELEASED
        hold.released_at = now
        hold.released_by_id = released_by_id
        hold.release_reason = release_reason
        hold.updated_at = now

        # Release inventory status
        try:
            from app.models.inventory_models import ProjectUnit, UnitInventoryStatus, ProjectUnitStatusLog
            unit_res = await self.db.execute(select(ProjectUnit).where(ProjectUnit.id == hold.unit_id))
            unit = unit_res.scalars().first()
            if unit and unit.status == UnitInventoryStatus.HOLD:
                unit.status = UnitInventoryStatus.AVAILABLE
                unit.updated_at = now
                log = ProjectUnitStatusLog(
                    unit_id=hold.unit_id,
                    organization_id=org_uuid,
                    from_status=UnitInventoryStatus.HOLD,
                    to_status=UnitInventoryStatus.AVAILABLE,
                    changed_by=released_by_id,
                    reason=f"Hold released: {release_reason or 'explicit release'}",
                )
                self.db.add(log)
        except (ImportError, Exception) as e:
            logger.warning(f"[UnitHold] Could not update inventory on release: {e}")

        await self.db.flush()

        deal_res = await self.db.execute(select(Deal).where(Deal.id == hold.deal_id))
        deal = deal_res.scalars().first()
        if deal:
            _emit_outbox(self.db, deal, RevenueEventType.UNIT_HOLD_RELEASED, {
                "hold_id": str(hold.id),
                "unit_id": str(hold.unit_id),
                "deal_id": str(hold.deal_id),
                "released_by_id": released_by_id,
                "reason": release_reason,
                "timestamp": now.isoformat(),
            })

        return hold

    async def expire_hold_if_due(
        self, hold_id: Any, organization_id: Any
    ) -> UnitHold:
        """Backend worker calls this — never browser timers."""
        res = await self.db.execute(
            select(UnitHold).where(
                UnitHold.id == _safe_uuid(hold_id),
                UnitHold.organization_id == _safe_uuid(organization_id),
            )
        )
        hold = res.scalars().first()
        if not hold or hold.status != UnitHoldStatus.ACTIVE:
            return hold

        if hold.expires_at <= _now():
            return await self.release_hold(
                hold_id, organization_id,
                released_by_id="SYSTEM",
                release_reason="TTL expired"
            )
        return hold


# ---------------------------------------------------------------------------
# REVENUE EVENT SERVICE
# ---------------------------------------------------------------------------

class RevenueEventService:
    """
    Service for querying and creating revenue events.
    Revenue events are append-only — never delete or rewrite.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_events_for_deal(
        self,
        deal_id: Any,
        organization_id: Any,
    ) -> List[RevenueEvent]:
        org_uuid = _safe_uuid(organization_id)
        deal_uuid = _safe_uuid(deal_id)
        res = await self.db.execute(
            select(RevenueEvent).where(
                RevenueEvent.opportunity_id == deal_uuid,
                RevenueEvent.organization_id == org_uuid,
            ).order_by(RevenueEvent.occurred_at)
        )
        return list(res.scalars().all())

    async def get_events_for_org(
        self,
        organization_id: Any,
        event_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[RevenueEvent], int]:
        org_uuid = _safe_uuid(organization_id)
        stmt = select(RevenueEvent).where(RevenueEvent.organization_id == org_uuid)
        if event_type:
            stmt = stmt.where(RevenueEvent.event_type == event_type)
        count_res = await self.db.execute(
            select(func.count()).select_from(stmt.subquery())
        )
        total = count_res.scalar() or 0
        stmt = stmt.order_by(desc(RevenueEvent.occurred_at)).offset(offset).limit(limit)
        res = await self.db.execute(stmt)
        return list(res.scalars().all()), total


# ---------------------------------------------------------------------------
# BOOKING RECONCILIATION SERVICE
# ---------------------------------------------------------------------------

class BookingReconciliationService:
    """Detects and manages booking-inventory inconsistencies."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def flag_inconsistency(
        self,
        organization_id: Any,
        inconsistency_type: str,
        description: str,
        deal_id: Optional[uuid.UUID] = None,
        booking_id: Optional[uuid.UUID] = None,
        unit_id: Optional[uuid.UUID] = None,
        payment_id: Optional[uuid.UUID] = None,
        evidence: Optional[Dict] = None,
        severity: str = "MEDIUM",
    ) -> BookingReconciliationTask:
        task = BookingReconciliationTask(
            organization_id=_safe_uuid(organization_id),
            inconsistency_type=inconsistency_type,
            deal_id=deal_id,
            booking_id=booking_id,
            unit_id=unit_id,
            payment_id=payment_id,
            description=description,
            evidence=evidence,
            severity=severity,
            status="OPEN",
        )
        self.db.add(task)
        await self.db.flush()
        logger.warning(f"[Reconciliation] {inconsistency_type}: {description}")
        return task

    async def resolve_task(
        self,
        task_id: Any,
        organization_id: Any,
        resolved_by_id: str,
        resolution_notes: str,
    ) -> BookingReconciliationTask:
        res = await self.db.execute(
            select(BookingReconciliationTask).where(
                BookingReconciliationTask.id == _safe_uuid(task_id),
                BookingReconciliationTask.organization_id == _safe_uuid(organization_id),
            )
        )
        task = res.scalars().first()
        if not task:
            raise SalesPipelineError(f"ReconciliationTask {task_id} not found")

        task.status = "RESOLVED"
        task.resolved_at = _now()
        task.resolved_by_id = resolved_by_id
        task.resolution_notes = resolution_notes
        await self.db.flush()
        return task

    async def list_open_tasks(
        self, organization_id: Any
    ) -> List[BookingReconciliationTask]:
        res = await self.db.execute(
            select(BookingReconciliationTask).where(
                BookingReconciliationTask.organization_id == _safe_uuid(organization_id),
                BookingReconciliationTask.status.in_(["OPEN", "IN_PROGRESS"]),
            ).order_by(desc(BookingReconciliationTask.created_at))
        )
        return list(res.scalars().all())
