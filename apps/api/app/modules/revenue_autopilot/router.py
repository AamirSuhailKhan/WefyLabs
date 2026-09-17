"""
Part 35 — AI Real Estate Revenue Autopilot FastAPI REST Router
===============================================================
Endpoints:
    GET  /api/v1/revenue/action-queue          # Prioritized action queue ("DO THIS NOW")
    GET  /api/v1/revenue/opportunities         # Filtered & paginated opportunity list
    GET  /api/v1/revenue/opportunities/{id}    # Detailed opportunity with provenance
    GET  /api/v1/revenue/briefing              # Grounded daily revenue briefing
    GET  /api/v1/revenue/demand-intelligence   # Segment demand gaps vs inventory supply
    POST /api/v1/revenue/opportunities/{id}/action   # Approve and execute action
    POST /api/v1/revenue/opportunities/{id}/dismiss  # Dismiss opportunity with reason
    POST /api/v1/revenue/opportunities/{id}/feedback # Submit recommendation feedback
    POST /api/v1/revenue/opportunities/{id}/complete # Mark opportunity completed
    POST /api/v1/revenue/opportunities/{id}/outreach # Generate grounded AI outreach
    POST /api/v1/revenue/evaluate              # Trigger on-demand tenant evaluation
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc, func

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.revenue_autopilot_models import RevenueOpportunity
from app.modules.revenue_autopilot.engine import RevenueAutopilotEngine
from app.modules.revenue_autopilot.action_handler import RevenueActionHandler
from app.modules.revenue_autopilot.outreach_generator import RevenueOutreachGenerator
from app.modules.revenue_autopilot.dto import (
    ActionQueueItemDTO,
    ActionQueueResponseDTO,
    RevenueOpportunityDTO,
    OpportunityListResponseDTO,
    DismissOpportunityRequestDTO,
    ActionOpportunityRequestDTO,
    FeedbackOpportunityRequestDTO,
    OutreachDraftDTO,
    DemandIntelligenceResponseDTO,
    RevenueBriefingDTO,
)

from sqlalchemy.orm import selectinload
logger = logging.getLogger("beetlelabs.revenue_autopilot.router")

router = APIRouter(prefix="/revenue", tags=["AI Real Estate Revenue Autopilot"])


def _opp_to_action_dto(opp: RevenueOpportunity) -> ActionQueueItemDTO:
    # Use __dict__ to avoid triggering async lazy load on unloaded relationships
    lead = opp.__dict__.get("lead")
    prop = opp.__dict__.get("property_listing")
    snap = opp.recommended_property_snapshot or {}

    return ActionQueueItemDTO(
        id=str(opp.id),
        opportunity_type=opp.opportunity_type,
        priority=opp.priority,
        urgency=opp.urgency,
        opportunity_score=opp.opportunity_score,
        match_score=opp.match_score,
        confidence=opp.confidence,
        lead_id=str(opp.lead_id),
        lead_name=lead.name if lead and getattr(lead, "name", None) else "Qualified Buyer",
        lead_phone=lead.phone if lead and getattr(lead, "phone", None) else "",
        lead_score=lead.score if lead and getattr(lead, "score", None) else "warm",
        lead_stage=lead.pipeline_stage if lead and getattr(lead, "pipeline_stage", None) else None,
        property_id=str(opp.property_id) if opp.property_id else None,
        property_title=prop.title if prop and getattr(prop, "title", None) else snap.get("title"),
        property_price=prop.price if prop and getattr(prop, "price", None) is not None else snap.get("price"),
        property_currency=(prop.currency_code or "INR") if prop and getattr(prop, "currency_code", None) else snap.get("currency", "INR"),
        property_locality=(prop.locality or prop.city) if prop and getattr(prop, "locality", None) else snap.get("locality"),
        property_bedrooms=prop.bedrooms if prop and getattr(prop, "bedrooms", None) is not None else snap.get("bedrooms"),
        property_status=prop.status if prop and getattr(prop, "status", None) else snap.get("status"),
        reason=opp.reason,
        why_now=opp.why_now,
        why_property=opp.why_property,
        risk_of_inactivity=opp.risk_of_inactivity,
        recommended_action=opp.recommended_action,
        recommended_channel=opp.recommended_channel,
        positive_signals=opp.positive_signals or [],
        negative_signals=opp.negative_signals or [],
        data_freshness=opp.data_freshness or {},
        status=opp.status,
        created_at=opp.created_at.isoformat() if opp.created_at else datetime.now(timezone.utc).isoformat(),
        expires_at=opp.expires_at.isoformat() if opp.expires_at else None,
    )



def _opp_to_full_dto(opp: RevenueOpportunity) -> RevenueOpportunityDTO:
    base = _opp_to_action_dto(opp)
    return RevenueOpportunityDTO(
        **base.model_dump(),
        recommended_property_snapshot=opp.recommended_property_snapshot or {},
        alternative_properties=opp.alternative_properties or [],
        call_brief=opp.call_brief or {},
        email_draft=opp.email_draft or {},
        provenance=opp.provenance or [],
        scoring_version=opp.scoring_version or "v1",
        dedup_key=opp.dedup_key or "",
        actioned_at=opp.actioned_at.isoformat() if opp.actioned_at else None,
        completed_at=opp.completed_at.isoformat() if opp.completed_at else None,
        dismissed_at=opp.dismissed_at.isoformat() if opp.dismissed_at else None,
        dismissal_reason=opp.dismissal_reason,
        feedback_rating=opp.feedback_rating,
        feedback_notes=opp.feedback_notes,
        actual_outcome=opp.actual_outcome,
    )


@router.get(
    "/action-queue",
    response_model=ActionQueueResponseDTO,
    summary="Get Prioritized Revenue Action Queue ('DO THIS NOW')",
)
async def get_action_queue_endpoint(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Primary operational directive: returns the highest-value actions
    the sales agent should perform right now.
    Includes empty-state metadata: active_leads_count, active_properties_count,
    completed_today_count so the UI can distinguish zero-data from all-caught-up states.
    """
    from app.models.lead import Lead
    from app.models.property_models import PropertyListing
    broker_uuid = uuid.UUID(str(current_broker.id))
    engine = RevenueAutopilotEngine(db)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    # 1. Fetch active recommended / new opportunities
    stmt = (
        select(RevenueOpportunity)
        .options(selectinload(RevenueOpportunity.lead), selectinload(RevenueOpportunity.property_listing))
        .where(
            and_(
                RevenueOpportunity.broker_id == broker_uuid,
                RevenueOpportunity.status.in_(["NEW", "RECOMMENDED", "ACTIONED"]),
                RevenueOpportunity.deleted_at.is_(None)
            )
        )
        .order_by(
            # Put CRITICAL urgency first, then rank by opportunity_score descending
            desc(RevenueOpportunity.urgency == "CRITICAL"),
            desc(RevenueOpportunity.opportunity_score),
            desc(RevenueOpportunity.created_at)
        )
        .limit(limit)
    )
    opps = list((await db.execute(stmt)).scalars().all())

    # If empty, evaluate on the fly to provide immediate value
    if not opps:
        generated = await engine.evaluate_tenant_opportunities(current_broker)
        # Re-query
        opps = list((await db.execute(stmt)).scalars().all())

    # 2. Empty-state intelligence metadata queries (Part 35.1)
    active_leads_stmt = select(func.count(Lead.id)).where(
        and_(
            Lead.broker_id == broker_uuid,
            Lead.deleted_at.is_(None),
            Lead.status.in_(["pending", "active", "qualified"])
        )
    )
    active_props_stmt = select(func.count(PropertyListing.id)).where(
        and_(
            PropertyListing.broker_id == broker_uuid,
            PropertyListing.deleted_at.is_(None),
            PropertyListing.status == "available"
        )
    )
    completed_today_stmt = select(func.count(RevenueOpportunity.id)).where(
        and_(
            RevenueOpportunity.broker_id == broker_uuid,
            RevenueOpportunity.status.in_(["COMPLETED", "ACTIONED", "DISMISSED"]),
            RevenueOpportunity.updated_at >= today_start,
            RevenueOpportunity.deleted_at.is_(None)
        )
    )
    active_leads_count = (await db.execute(active_leads_stmt)).scalar() or 0
    active_props_count = (await db.execute(active_props_stmt)).scalar() or 0
    completed_today = (await db.execute(completed_today_stmt)).scalar() or 0

    items = [_opp_to_action_dto(o) for o in opps]
    critical_count = sum(1 for o in items if o.urgency == "CRITICAL" or o.priority == "CRITICAL")
    high_count = sum(1 for o in items if o.priority == "HIGH")

    headline = (
        f"You have {len(items)} high-value sales actions requiring attention."
        if items else
        "No priority actions right now. Add more active leads or property listings to generate opportunities."
    )

    return ActionQueueResponseDTO(
        items=items,
        total_count=len(items),
        critical_count=critical_count,
        high_count=high_count,
        briefing_headline=headline,
        active_leads_count=active_leads_count,
        active_properties_count=active_props_count,
        completed_today_count=completed_today,
        last_scan_at=now.isoformat(),
    )


@router.get(
    "/opportunities",
    response_model=OpportunityListResponseDTO,
    summary="List Revenue Opportunities with Rich Filtering",
)
async def list_opportunities_endpoint(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    urgency_filter: Optional[str] = Query(None, alias="urgency"),
    opportunity_type: Optional[str] = Query(None),
    lead_id: Optional[str] = Query(None),
    property_id: Optional[str] = Query(None),
    min_score: Optional[float] = Query(None, ge=0.0, le=100.0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Returns filtered, paginated list of revenue opportunities.
    """
    broker_uuid = uuid.UUID(str(current_broker.id))
    filters = [
        RevenueOpportunity.broker_id == broker_uuid,
        RevenueOpportunity.deleted_at.is_(None),
    ]

    if status_filter and status_filter.lower() != "all":
        filters.append(RevenueOpportunity.status == status_filter.upper())
    else:
        # Default: hide dismissed and expired unless explicitly asked
        filters.append(RevenueOpportunity.status.notin_(["DISMISSED", "EXPIRED", "INVALIDATED"]))

    if priority_filter and priority_filter.lower() != "all":
        filters.append(RevenueOpportunity.priority == priority_filter.upper())

    if urgency_filter and urgency_filter.lower() != "all":
        filters.append(RevenueOpportunity.urgency == urgency_filter.upper())

    if opportunity_type and opportunity_type.lower() != "all":
        filters.append(RevenueOpportunity.opportunity_type == opportunity_type)

    if lead_id:
        filters.append(RevenueOpportunity.lead_id == uuid.UUID(str(lead_id)))

    if property_id:
        filters.append(RevenueOpportunity.property_id == uuid.UUID(str(property_id)))

    if min_score is not None:
        filters.append(RevenueOpportunity.opportunity_score >= min_score)

    # Count total
    count_stmt = select(func.count(RevenueOpportunity.id)).where(and_(*filters))
    total_count = (await db.execute(count_stmt)).scalar() or 0

    # Query items
    offset = (page - 1) * page_size
    query_stmt = (
        select(RevenueOpportunity)
        .options(selectinload(RevenueOpportunity.lead), selectinload(RevenueOpportunity.property_listing))
        .where(and_(*filters))
        .order_by(desc(RevenueOpportunity.opportunity_score), desc(RevenueOpportunity.created_at))
        .offset(offset)
        .limit(page_size)
    )
    opps = list((await db.execute(query_stmt)).scalars().all())

    items = [_opp_to_full_dto(o) for o in opps]
    has_more = (offset + len(items)) < total_count

    return OpportunityListResponseDTO(
        items=items,
        total_count=total_count,
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.get(
    "/opportunities/{id}",
    response_model=RevenueOpportunityDTO,
    summary="Get Revenue Opportunity Details with Full Provenance",
)
async def get_opportunity_endpoint(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Returns single opportunity with complete explainability, signals, and outreach drafts.
    """
    broker_uuid = uuid.UUID(str(current_broker.id))
    opp_uuid = uuid.UUID(str(id))

    stmt = (
        select(RevenueOpportunity)
        .options(selectinload(RevenueOpportunity.lead), selectinload(RevenueOpportunity.property_listing))
        .where(
            and_(
                RevenueOpportunity.id == opp_uuid,
                RevenueOpportunity.broker_id == broker_uuid,
                RevenueOpportunity.deleted_at.is_(None)
            )
        )
    )
    opp = (await db.execute(stmt)).scalars().first()
    if not opp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Opportunity {id} not found."
        )

    return _opp_to_full_dto(opp)


@router.post(
    "/opportunities/{id}/action",
    summary="Approve and Execute Revenue Action",
)
async def action_opportunity_endpoint(
    id: str,
    dto: ActionOpportunityRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Agent approves and executes an action (Call, Email, Property Recommendation, Site Visit).
    """
    handler = RevenueActionHandler(db)
    return await handler.execute_action(opportunity_id=id, broker=current_broker, dto=dto)


@router.post(
    "/opportunities/{id}/dismiss",
    summary="Dismiss Revenue Opportunity",
)
async def dismiss_opportunity_endpoint(
    id: str,
    dto: DismissOpportunityRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Dismisses an opportunity with structured reason and feeds back into the engine.
    """
    handler = RevenueActionHandler(db)
    return await handler.dismiss_opportunity(opportunity_id=id, broker=current_broker, dto=dto)


@router.post(
    "/opportunities/{id}/feedback",
    summary="Submit Recommendation Feedback & Actual Outcome",
)
async def feedback_opportunity_endpoint(
    id: str,
    dto: FeedbackOpportunityRequestDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Records agent feedback (YES / NO / NOT_SURE) and actual commercial deal outcomes.
    """
    handler = RevenueActionHandler(db)
    return await handler.submit_feedback(opportunity_id=id, broker=current_broker, dto=dto)


@router.post(
    "/opportunities/{id}/complete",
    summary="Mark Opportunity Completed",
)
async def complete_opportunity_endpoint(
    id: str,
    notes: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Transitions opportunity to COMPLETED state.
    """
    opp_uuid = uuid.UUID(str(id))
    broker_uuid = uuid.UUID(str(current_broker.id))

    stmt = select(RevenueOpportunity).where(
        and_(RevenueOpportunity.id == opp_uuid, RevenueOpportunity.broker_id == broker_uuid)
    )
    opp = (await db.execute(stmt)).scalars().first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    opp.status = "COMPLETED"
    opp.completed_at = datetime.now(timezone.utc)
    if notes:
        opp.feedback_notes = notes
    await db.commit()
    return {"opportunity_id": str(opp.id), "status": "COMPLETED"}


@router.get(
    "/opportunities/{id}/outreach",
    response_model=OutreachDraftDTO,
    summary="Get Grounded Outreach (Call Brief & Email)",
)
@router.post(
    "/opportunities/{id}/outreach",
    response_model=OutreachDraftDTO,
    summary="Generate or Regenerate Grounded Outreach (Call Brief & Email)",
)
async def generate_outreach_endpoint(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Generates grounded AI call briefing and email draft.
    Falls back gracefully to deterministic templates if Gemini is unavailable.
    """
    broker_uuid = uuid.UUID(str(current_broker.id))
    opp_uuid = uuid.UUID(str(id))

    stmt = select(RevenueOpportunity).where(
        and_(RevenueOpportunity.id == opp_uuid, RevenueOpportunity.broker_id == broker_uuid)
    )
    opp = (await db.execute(stmt)).scalars().first()
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")

    lead = await db.get(Lead, opp.lead_id)
    prop = await db.get(PropertyListing, opp.property_id) if opp.property_id else None

    cb, ed, is_ai, model = await RevenueOutreachGenerator.generate_outreach(lead, prop, opp)

    opp.call_brief = cb
    opp.email_draft = ed
    await db.commit()

    return OutreachDraftDTO(
        opportunity_id=str(opp.id),
        lead_name=lead.name if lead and lead.name else "Client",
        channel=opp.recommended_channel,
        call_brief=cb,
        email_draft=ed,
        is_ai_generated=is_ai,
        model_used=model,
    )


@router.get(
    "/demand-intelligence",
    response_model=DemandIntelligenceResponseDTO,
    summary="Get Inventory Demand Gap Intelligence",
)
async def get_demand_intelligence_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Aggregates active buyer preferences against current property listings,
    identifying high-demand supply deficit gaps.
    """
    engine = RevenueAutopilotEngine(db)
    return await engine.get_demand_gap_intelligence(current_broker)


@router.get(
    "/briefing",
    response_model=RevenueBriefingDTO,
    summary="Get Daily Revenue Briefing",
)
async def get_revenue_briefing_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Synthesizes a grounded daily revenue briefing narrative.
    """
    broker_uuid = uuid.UUID(str(current_broker.id))
    now = datetime.now(timezone.utc)

    # Fetch active counts
    active_stmt = select(RevenueOpportunity).where(
        and_(
            RevenueOpportunity.broker_id == broker_uuid,
            RevenueOpportunity.status.in_(["NEW", "RECOMMENDED", "ACTIONED"]),
            RevenueOpportunity.deleted_at.is_(None)
        )
    ).order_by(desc(RevenueOpportunity.opportunity_score)).limit(10)
    opps = list((await db.execute(active_stmt)).scalars().all())

    critical_count = sum(1 for o in opps if o.urgency == "CRITICAL" or o.priority == "CRITICAL")
    hot_count = sum(1 for o in opps if o.opportunity_type in ("HOT_LEAD_NEEDS_CONTACT", "NEW_HIGH_VALUE_MATCH"))

    top_opp = opps[0] if opps else None
    if top_opp:
        rec_text = f"Start with {top_opp.lead.name if top_opp.lead else 'your top lead'}: {top_opp.reason} ({top_opp.recommended_action.replace('_', ' ').title()})."
    else:
        rec_text = "All priority opportunities have been actioned. Review inventory or add new leads to generate fresh actions."

    evidence = [
        f"{len(opps)} active revenue opportunities identified.",
        f"{critical_count} critical urgency items requiring immediate agent contact.",
        f"{hot_count} high-intent buyer actions queued."
    ]

    return RevenueBriefingDTO(
        greeting=f"Good day, {current_broker.name or 'Agent'}.",
        headline=f"You have {len(opps)} actions deserving attention today.",
        immediate_actions_count=len(opps),
        critical_actions_count=critical_count,
        hot_leads_count=hot_count,
        top_recommendation_text=rec_text,
        evidence_points=evidence,
        generated_at=now.isoformat(),
    )


@router.post(
    "/evaluate",
    summary="Trigger On-Demand Opportunity Recalculation for Current Broker",
)
async def trigger_evaluate_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Forces an immediate evaluation scan across the broker's active leads and inventory.
    """
    engine = RevenueAutopilotEngine(db)
    generated = await engine.evaluate_tenant_opportunities(current_broker)
    return {
        "status": "success",
        "evaluated_opportunities_count": len(generated),
        "message": f"Generated or refreshed {len(generated)} opportunities for {current_broker.name}."
    }
