"""
Build 08 — Sales Pipeline API Router
====================================
Canonical endpoints for:
  - /pipelines (Pipeline definitions & stages)
  - /opportunities (Lifecycle, stage progression, lost tracking, timeline)
  - /site-visits (Scheduling, state machine, outcome recording)
  - /offers (Negotiation rounds, AI draft human approval)
  - /booking-intents (Commercial commitment & price integrity)
  - /holds (Concurrency-safe unit reservation)
  - /reconciliation (Integrity check & remediation tasks)
  - /revenue-events (Immutable transaction audit log)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.deal_models import Deal, DealStage
from app.models.sales_pipeline_models import (
    SiteVisit, SiteVisitStatus, SiteVisitOutcome, NegotiationRound, BookingIntent, RevenueEvent
)
from app.modules.sales_pipeline.service import (
    PipelineConfigService,
    OpportunityStageService,
    PropertyShortlistService,
    SiteVisitService,
    NegotiationService,
    BookingIntentService,
    UnitHoldService,
    RevenueEventService,
    BookingReconciliationService,
    SalesPipelineError,
    StagePolicyViolation,
    TenantViolation,
)
from app.modules.sales_pipeline.dto import (
    PipelineCreateRequest, PipelineResponse, StageConfigResponse,
    OpportunityCreateRequest, OpportunityStageAdvanceRequest, OpportunityLostRequest,
    OpportunityStageHistoryResponse,
    ShortlistAddRequest, ShortlistUpdateRequest, ShortlistResponse,
    SiteVisitCreateRequest, SiteVisitStatusUpdateRequest, SiteVisitOutcomeRequest, SiteVisitResponse,
    NegotiationRoundRequest, NegotiationRoundResponse,
    BookingIntentCreateRequest, BookingIntentResponse,
    UnitHoldCreateRequest, UnitHoldResponse,
    ReconciliationResolveRequest, ReconciliationTaskResponse,
    RevenueEventResponse,
)

router = APIRouter(prefix="", tags=["Sales Pipeline & Deal Execution OS"])


def _get_org_id(broker: Broker) -> uuid.UUID:
    return broker.organization_id if broker.organization_id else broker.id


async def _resolve_deal(db: AsyncSession, org_id: uuid.UUID, broker_id: uuid.UUID, target_id: uuid.UUID) -> Deal:
    # 1. Check if target_id is a Deal.id
    res = await db.execute(select(Deal).where(Deal.id == target_id, Deal.organization_id == org_id, Deal.deleted_at.is_(None)))
    deal = res.scalars().first()
    if deal:
        return deal

    # 2. Check if target_id is a Lead.id and find its active deal
    res = await db.execute(select(Deal).where(Deal.lead_id == target_id, Deal.organization_id == org_id, Deal.deleted_at.is_(None)).order_by(desc(Deal.created_at)))
    deal = res.scalars().first()
    if deal:
        return deal

    # 3. If target_id is a Lead.id but has no deal yet, auto-create one
    lead_res = await db.execute(select(Lead).where(Lead.id == target_id, Lead.deleted_at.is_(None)))
    lead = lead_res.scalars().first()
    if lead:
        from app.modules.deals.services.deal_service import DealService
        deal_svc = DealService(db)
        new_deal = await deal_svc.create_deal(
            lead_id=str(lead.id),
            deal_title=f"Deal - {lead.name}",
            broker_id=str(broker_id),
            organization_id=str(org_id),
        )
        return new_deal

    raise HTTPException(status_code=404, detail=f"Opportunity or Lead {target_id} not found")


def _site_visit_to_response(sv: SiteVisit) -> SiteVisitResponse:
    outcome_text = None
    client_feedback = None
    sentiment = None
    if sv.outcome:
        outcome_text = sv.outcome.next_action or sv.attendance_status
        client_feedback = sv.outcome.customer_feedback
        sentiment = str(sv.outcome.customer_interest_level) if sv.outcome.customer_interest_level else None

    start_dt = sv.scheduled_at or sv.created_at
    end_dt = start_dt + timedelta(hours=1)

    return SiteVisitResponse(
        id=str(sv.id),
        organization_id=str(sv.organization_id),
        opportunity_id=str(sv.deal_id),
        property_id=str(sv.property_listing_id or sv.project_id or sv.unit_id or uuid.uuid4()),
        visit_number=sv.visit_number,
        status=sv.status,
        outcome=outcome_text or sv.attendance_status,
        scheduled_start=start_dt,
        scheduled_end=end_dt,
        assigned_broker_id=sv.assigned_agent_id,
        location_address=sv.location_address or sv.meeting_point,
        client_feedback=client_feedback,
        sentiment=sentiment,
        created_at=sv.created_at,
        updated_at=sv.updated_at,
    )


def _round_to_response(r: NegotiationRound) -> NegotiationRoundResponse:
    return NegotiationRoundResponse(
        id=str(r.id),
        opportunity_id=str(r.deal_id),
        round_number=r.round_number,
        actor=r.actor,
        offered_price=r.price or Decimal("0.00"),
        currency=r.currency,
        payment_terms=r.payment_plan,
        inclusions=[],
        ai_generated=(r.actor == "AI_DRAFT"),
        requires_approval=r.requires_approval,
        approved_by=r.approved_by_id,
        approved_at=r.occurred_at if r.approved_by_id else None,
        status="APPROVED" if r.approved_by_id else "PENDING" if r.requires_approval else "ACTIVE",
        created_at=r.occurred_at or datetime.now(timezone.utc),
    )


def _intent_to_response(bi: BookingIntent) -> BookingIntentResponse:
    return BookingIntentResponse(
        id=str(bi.id),
        organization_id=str(bi.organization_id),
        opportunity_id=str(bi.deal_id),
        property_id=str(bi.property_listing_id or bi.project_id or bi.unit_id or uuid.uuid4()),
        unit_id=str(bi.unit_id) if bi.unit_id else None,
        agreed_price=bi.intended_price or Decimal("0.00"),
        deposit_amount=Decimal("0.00"),
        currency=bi.currency,
        status=bi.status,
        expires_at=bi.expires_at or (datetime.now(timezone.utc) + timedelta(days=2)),
        created_at=bi.created_at,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 1. Pipelines & Stages
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/pipelines", response_model=PipelineResponse, status_code=status.HTTP_201_CREATED)
async def create_pipeline(
    req: PipelineCreateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Create a configured sales pipeline with stages."""
    org_id = _get_org_id(broker)
    svc = PipelineConfigService(db)
    try:
        pipeline = await svc.create_pipeline(
            org_id=org_id,
            name=req.name,
            pipeline_type=req.pipeline_type,
            description=req.description,
            is_default=req.is_default,
            stages=req.stages,
        )
        return pipeline
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/pipelines", response_model=List[PipelineResponse])
async def list_pipelines(
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """List all active sales pipelines for the tenant."""
    org_id = _get_org_id(broker)
    svc = PipelineConfigService(db)
    return await svc.list_pipelines(org_id)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Opportunities & Stage Advance
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/opportunities/{deal_id}/stage", response_model=Dict[str, Any])
async def advance_opportunity_stage(
    deal_id: uuid.UUID,
    req: OpportunityStageAdvanceRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Deterministically advance opportunity stage with server-side validation and audit."""
    org_id = _get_org_id(broker)
    svc = OpportunityStageService(db)
    try:
        deal = await svc.advance_stage(
            deal_id=deal_id,
            org_id=org_id,
            target_stage=req.target_stage,
            broker_id=broker.id,
            evidence=req.evidence,
            reason=req.reason,
            idempotency_key=req.idempotency_key,
        )
        return {
            "id": str(deal.id),
            "current_stage": deal.current_stage,
            "status": deal.status,
            "message": f"Advanced to stage {deal.current_stage}",
        }
    except TenantViolation as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except StagePolicyViolation as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/opportunities/{deal_id}/lost", response_model=Dict[str, Any])
async def mark_opportunity_lost(
    deal_id: uuid.UUID,
    req: OpportunityLostRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Mark opportunity as lost with controlled loss taxonomy."""
    org_id = _get_org_id(broker)
    svc = OpportunityStageService(db)
    try:
        deal = await svc.mark_lost(
            deal_id=deal_id,
            org_id=org_id,
            broker_id=broker.id,
            lost_reason=req.lost_reason,
            competitor_name=req.competitor_name,
            details=req.details,
            idempotency_key=req.idempotency_key,
        )
        return {
            "id": str(deal.id),
            "status": deal.status,
            "current_stage": deal.current_stage,
            "message": "Opportunity marked as LOST",
        }
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/opportunities/{deal_id}/timeline", response_model=List[OpportunityStageHistoryResponse])
async def get_opportunity_timeline(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Retrieve full immutable stage transition audit history."""
    org_id = _get_org_id(broker)
    svc = OpportunityStageService(db)
    try:
        return await svc.get_stage_history(deal_id=deal_id, org_id=org_id)
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 3. Property Shortlist
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/opportunities/{deal_id}/properties", response_model=List[ShortlistResponse])
async def get_opportunity_shortlist(
    deal_id: uuid.UUID,
    status_filter: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Get active property shortlist for this opportunity."""
    org_id = _get_org_id(broker)
    svc = PropertyShortlistService(db)
    try:
        return await svc.get_shortlist(deal_id=deal_id, org_id=org_id, status=status_filter)
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/opportunities/{deal_id}/properties", response_model=ShortlistResponse, status_code=status.HTTP_201_CREATED)
async def add_property_to_shortlist(
    deal_id: uuid.UUID,
    req: ShortlistAddRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Add a property to the opportunity shortlist."""
    org_id = _get_org_id(broker)
    svc = PropertyShortlistService(db)
    try:
        return await svc.add_to_shortlist(
            deal_id=deal_id,
            org_id=org_id,
            property_id=uuid.UUID(req.property_id),
            interest_level=req.interest_level,
            client_reaction=req.client_reaction,
            is_primary=req.is_primary,
            notes=req.notes,
        )
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 4. Site Visits
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/site-visits", response_model=SiteVisitResponse, status_code=status.HTTP_201_CREATED)
async def create_site_visit(
    req: SiteVisitCreateRequest,
    opportunity_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Schedule a physical site visit linked to an opportunity or lead."""
    org_id = _get_org_id(broker)
    deal = await _resolve_deal(db, org_id, broker.id, opportunity_id)
    svc = SiteVisitService(db)
    try:
        prop_uuid = None
        try:
            prop_uuid = uuid.UUID(req.property_id) if req.property_id else deal.property_id
        except Exception:
            prop_uuid = deal.property_id

        sv = await svc.create_site_visit(
            deal_id=deal.id,
            organization_id=org_id,
            lead_id=deal.lead_id,
            created_by_id=str(broker.id),
            scheduled_at=req.scheduled_start,
            location_address=req.location_address,
            property_listing_id=prop_uuid,
            assigned_agent_id=str(req.assigned_broker_id or broker.id),
            notes=req.special_requests or req.access_instructions,
            idempotency_key=req.idempotency_key,
        )
        await db.commit()
        return _site_visit_to_response(sv)
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/site-visits/{visit_id}", response_model=SiteVisitResponse)
async def update_site_visit_status(
    visit_id: uuid.UUID,
    req: SiteVisitStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Advance site visit status machine (SCHEDULED -> CONFIRMED -> IN_PROGRESS -> COMPLETED)."""
    org_id = _get_org_id(broker)
    svc = SiteVisitService(db)
    try:
        sv = await svc.transition_status(
            site_visit_id=visit_id,
            organization_id=org_id,
            new_status=req.status,
            updated_by_id=str(broker.id),
            notes=req.notes or req.cancellation_reason,
        )
        await db.commit()
        return _site_visit_to_response(sv)
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/site-visits/{visit_id}/outcome", response_model=SiteVisitResponse)
async def record_site_visit_outcome(
    visit_id: uuid.UUID,
    req: SiteVisitOutcomeRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Record completed site visit outcome and client sentiment."""
    org_id = _get_org_id(broker)
    svc = SiteVisitService(db)
    try:
        # 1. Fetch site visit
        res = await db.execute(
            select(SiteVisit).where(
                SiteVisit.id == visit_id,
                SiteVisit.organization_id == org_id,
                SiteVisit.deleted_at.is_(None)
            )
        )
        sv = res.scalars().first()
        if not sv:
            raise HTTPException(status_code=404, detail="Site visit not found")

        # 2. Determine target status
        target_status = SiteVisitStatus.COMPLETED
        if req.outcome.lower() in ("no_show", "noshow"):
            target_status = SiteVisitStatus.NO_SHOW

        # 3. Transition if not yet completed/no_show
        if sv.status not in (SiteVisitStatus.COMPLETED, SiteVisitStatus.NO_SHOW):
            if sv.status == SiteVisitStatus.REQUESTED:
                sv = await svc.transition_status(sv.id, org_id, SiteVisitStatus.CONFIRMED, str(broker.id))
            if sv.status == SiteVisitStatus.CONFIRMED:
                sv = await svc.transition_status(sv.id, org_id, SiteVisitStatus.IN_PROGRESS, str(broker.id))
            sv = await svc.transition_status(sv.id, org_id, target_status, str(broker.id), notes=req.agent_notes)

        # 4. Map sentiment to interest level (1-5)
        interest_level = 4
        s_lower = (req.sentiment or "").lower()
        if s_lower in ("high", "hot", "positive", "5"):
            interest_level = 5
        elif s_lower in ("medium", "neutral", "3"):
            interest_level = 3
        elif s_lower in ("low", "cold", "negative", "1"):
            interest_level = 1

        # 5. Record structured outcome
        await svc.record_outcome(
            site_visit_id=sv.id,
            organization_id=org_id,
            recorded_by_id=str(broker.id),
            customer_interest_level=interest_level,
            customer_feedback=req.client_feedback or req.outcome,
            next_action=req.next_action or "Follow up on property proposal",
            agent_notes=req.agent_notes,
        )
        await db.commit()
        await db.refresh(sv)
        return _site_visit_to_response(sv)
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/site-visits/opportunity/{deal_id}", response_model=List[SiteVisitResponse])
async def list_opportunity_site_visits(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """List all site visits for a given opportunity or lead."""
    org_id = _get_org_id(broker)
    deal = await _resolve_deal(db, org_id, broker.id, deal_id)
    svc = SiteVisitService(db)
    try:
        visits = await svc.get_visits_for_deal(deal_id=deal.id, organization_id=org_id)
        return [_site_visit_to_response(sv) for sv in visits]
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")


# ─────────────────────────────────────────────────────────────────────────────
# 5. Negotiation & Offers
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/offers", response_model=NegotiationRoundResponse, status_code=status.HTTP_201_CREATED)
async def submit_negotiation_round(
    req: NegotiationRoundRequest,
    opportunity_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Submit an append-only negotiation round or AI offer draft."""
    org_id = _get_org_id(broker)
    deal = await _resolve_deal(db, org_id, broker.id, opportunity_id)
    svc = NegotiationService(db)
    try:
        actor_val = (req.actor or "AGENT").upper()
        if req.ai_generated:
            actor_val = "AI_DRAFT"
        round_type_val = "CUSTOMER_OFFER" if "BUYER" in actor_val or "CUSTOMER" in actor_val else "AGENT_COUNTER"
        round_obj = await svc.add_round(
            deal_id=deal.id,
            organization_id=org_id,
            round_type=round_type_val,
            actor=actor_val,
            actor_id=str(broker.id),
            price=req.offered_price,
            currency=req.currency,
            payment_plan=req.payment_terms,
            notes=req.counter_proposal or f"Offered {req.offered_price} {req.currency}",
            requires_approval=req.ai_generated,
        )
        await db.commit()
        return _round_to_response(round_obj)
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/offers/{round_id}/approve", response_model=NegotiationRoundResponse)
async def approve_ai_negotiation_round(
    round_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Human approval gate for AI-generated negotiation rounds."""
    org_id = _get_org_id(broker)
    svc = NegotiationService(db)
    try:
        round_obj = await svc.approve_round(
            round_id=round_id,
            organization_id=org_id,
            approved_by_id=str(broker.id),
        )
        await db.commit()
        return _round_to_response(round_obj)
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/offers/opportunity/{deal_id}", response_model=List[NegotiationRoundResponse])
async def get_negotiation_history(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Get full append-only negotiation history for an opportunity or lead."""
    org_id = _get_org_id(broker)
    deal = await _resolve_deal(db, org_id, broker.id, deal_id)
    svc = NegotiationService(db)
    try:
        rounds = await svc.get_history(deal_id=deal.id, organization_id=org_id)
        return [_round_to_response(r) for r in rounds]
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")


# ─────────────────────────────────────────────────────────────────────────────
# 6. Booking Intent & Unit Holds
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/booking-intents", response_model=BookingIntentResponse, status_code=status.HTTP_201_CREATED)
async def create_booking_intent(
    req: BookingIntentCreateRequest,
    opportunity_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Create a TTL-governed commercial booking intent with agreed price snapshot."""
    org_id = _get_org_id(broker)
    deal = await _resolve_deal(db, org_id, broker.id, opportunity_id)
    svc = BookingIntentService(db)
    try:
        prop_uuid = None
        try:
            prop_uuid = uuid.UUID(req.property_id) if req.property_id else deal.property_id
        except Exception:
            prop_uuid = deal.property_id

        unit_uuid = None
        if req.unit_id:
            try:
                unit_uuid = uuid.UUID(req.unit_id)
            except Exception:
                unit_uuid = None

        intent = await svc.create_intent(
            deal_id=deal.id,
            organization_id=org_id,
            lead_id=deal.lead_id,
            created_by_id=str(broker.id),
            created_by_type="HUMAN",
            unit_id=unit_uuid,
            property_listing_id=prop_uuid,
            intended_price=req.agreed_price,
            currency=req.currency,
            expires_hours=req.ttl_hours,
            idempotency_key=req.idempotency_key,
        )

        # Advance deal to BOOKING stage
        deal.current_stage = DealStage.BOOKING
        deal.agreed_price = req.agreed_price

        # Advance Lead to closed_won
        if deal.lead_id:
            lead_res = await db.execute(select(Lead).where(Lead.id == deal.lead_id))
            lead = lead_res.scalars().first()
            if lead:
                lead.stage_name = "closed_won"
                lead.pipeline_stage = "closed_won"

        await db.commit()
        return _intent_to_response(intent)
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/holds", response_model=UnitHoldResponse, status_code=status.HTTP_201_CREATED)
async def create_unit_hold(
    req: UnitHoldCreateRequest,
    opportunity_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Place a concurrency-safe temporary hold on a property unit."""
    org_id = _get_org_id(broker)
    svc = UnitHoldService(db)
    try:
        return await svc.create_hold(
            deal_id=opportunity_id,
            org_id=org_id,
            property_id=uuid.UUID(req.property_id),
            unit_id=uuid.UUID(req.unit_id) if req.unit_id else None,
            ttl_minutes=req.ttl_minutes,
            idempotency_key=req.idempotency_key,
        )
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))


@router.post("/holds/{hold_id}/release", response_model=UnitHoldResponse)
async def release_unit_hold(
    hold_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Explicitly release an active unit hold."""
    org_id = _get_org_id(broker)
    svc = UnitHoldService(db)
    try:
        return await svc.release_hold(hold_id=hold_id, org_id=org_id)
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ─────────────────────────────────────────────────────────────────────────────
# 7. Reconciliation & Revenue Events
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/reconciliation/tasks", response_model=List[ReconciliationTaskResponse])
async def list_open_reconciliation_tasks(
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """List open reconciliation issues for audit and operations desk."""
    org_id = _get_org_id(broker)
    svc = BookingReconciliationService(db)
    return await svc.list_open_tasks(org_id)


@router.post("/reconciliation/tasks/{task_id}/resolve", response_model=ReconciliationTaskResponse)
async def resolve_reconciliation_task(
    task_id: uuid.UUID,
    req: ReconciliationResolveRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Resolve an open reconciliation task with resolution audit notes."""
    org_id = _get_org_id(broker)
    svc = BookingReconciliationService(db)
    try:
        return await svc.resolve_task(
            task_id=task_id,
            org_id=org_id,
            resolved_by=broker.id,
            resolution_notes=req.resolution_notes,
        )
    except TenantViolation:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cross-tenant access forbidden")
    except SalesPipelineError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/revenue-events/opportunity/{deal_id}", response_model=List[RevenueEventResponse])
async def get_opportunity_revenue_events(
    deal_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """Retrieve immutable revenue events emitted across the deal lifecycle."""
    org_id = _get_org_id(broker)
    deal = await _resolve_deal(db, org_id, broker.id, deal_id)
    svc = RevenueEventService(db)
    return await svc.get_events_for_deal(deal_id=deal.id, organization_id=org_id)
