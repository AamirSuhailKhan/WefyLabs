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
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.models.deal_models import Deal
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
    """Schedule a physical site visit linked to an opportunity."""
    org_id = _get_org_id(broker)
    svc = SiteVisitService(db)
    try:
        return await svc.create_site_visit(
            deal_id=opportunity_id,
            org_id=org_id,
            property_id=uuid.UUID(req.property_id),
            scheduled_start=req.scheduled_start,
            scheduled_end=req.scheduled_end,
            assigned_broker_id=uuid.UUID(req.assigned_broker_id) if req.assigned_broker_id else broker.id,
            location_address=req.location_address,
            access_instructions=req.access_instructions,
            special_requests=req.special_requests,
            idempotency_key=req.idempotency_key,
        )
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
        return await svc.transition_status(
            visit_id=visit_id,
            org_id=org_id,
            new_status=req.status,
            cancellation_reason=req.cancellation_reason,
            notes=req.notes,
        )
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
        return await svc.record_outcome(
            visit_id=visit_id,
            org_id=org_id,
            outcome=req.outcome,
            sentiment=req.sentiment,
            client_feedback=req.client_feedback,
            next_action=req.next_action,
            agent_notes=req.agent_notes,
            follow_up_scheduled=req.follow_up_scheduled,
        )
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
    """List all site visits for a given opportunity."""
    org_id = _get_org_id(broker)
    svc = SiteVisitService(db)
    try:
        return await svc.get_visits_for_deal(deal_id=deal_id, org_id=org_id)
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
    svc = NegotiationService(db)
    try:
        return await svc.add_round(
            deal_id=opportunity_id,
            org_id=org_id,
            actor=req.actor,
            offered_price=req.offered_price,
            currency=req.currency,
            round_number=req.round_number,
            payment_terms=req.payment_terms,
            inclusions=req.inclusions,
            valid_until=req.valid_until,
            counter_proposal=req.counter_proposal,
            ai_generated=req.ai_generated,
            idempotency_key=req.idempotency_key,
        )
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
        return await svc.approve_round(
            round_id=round_id,
            org_id=org_id,
            approved_by=broker.id,
        )
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
    """Get full append-only negotiation history for an opportunity."""
    org_id = _get_org_id(broker)
    svc = NegotiationService(db)
    try:
        return await svc.get_history(deal_id=deal_id, org_id=org_id)
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
    svc = BookingIntentService(db)
    try:
        return await svc.create_intent(
            deal_id=opportunity_id,
            org_id=org_id,
            property_id=uuid.UUID(req.property_id),
            agreed_price=req.agreed_price,
            deposit_amount=req.deposit_amount,
            unit_id=uuid.UUID(req.unit_id) if req.unit_id else None,
            currency=req.currency,
            ttl_hours=req.ttl_hours,
            customer_national_id=req.customer_national_id,
            idempotency_key=req.idempotency_key,
        )
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
    svc = RevenueEventService(db)
    return await svc.get_events_for_deal(deal_id=deal_id, org_id=org_id)
