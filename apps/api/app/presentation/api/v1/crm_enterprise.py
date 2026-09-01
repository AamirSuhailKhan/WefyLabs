import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.score import Score
from app.services.duplicate_detection_service import DuplicateDetectionService
from app.services.lead_routing_service import LeadRoutingService
from app.services.commission_service import CommissionCalculatorService, CommissionBreakdown

router = APIRouter(prefix="/crm/enterprise", tags=["Enterprise CRM Features"])

# --- Request / Response Schemas ---
class DeduplicateCheckRequest(BaseModel):
    phone: str
    email: Optional[str] = None
    country_code: Optional[str] = "+91"

class DeduplicateCheckResponse(BaseModel):
    is_duplicate: bool
    matching_lead_id: Optional[str] = None
    matching_phone: Optional[str] = None
    matching_name: Optional[str] = None

class RouteLeadRequest(BaseModel):
    lead_id: uuid.UUID
    agent_ids: List[uuid.UUID]
    last_index: int = 0

class RouteLeadResponse(BaseModel):
    assigned_agent_id: str
    next_index: int

class CommissionCalculateRequest(BaseModel):
    property_sale_price: int = Field(..., gt=0)
    gross_commission_rate_pct: float = Field(2.0, ge=0.1, le=10.0)
    agent_split_pct: float = Field(70.0, ge=0.0, le=100.0)

class ActivityTimelineItem(BaseModel):
    id: str
    type: str  # conversation | score | stage_change | system
    timestamp: str
    title: str
    description: str

class TimelineResponse(BaseModel):
    lead_id: str
    activities: List[ActivityTimelineItem]


# --- Endpoints ---

@router.post("/deduplicate/check", response_model=DeduplicateCheckResponse)
async def check_duplicate_lead(
    req: DeduplicateCheckRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Checks if an incoming lead's phone or email matches any existing records
    for the current broker's organization using E.164 normalization.
    """
    stmt = select(Lead).where(Lead.broker_id == current_broker.id, Lead.deleted_at.is_(None))
    res = await db.execute(stmt)
    leads = res.scalars().all()

    existing_dicts = [
        {"id": str(l.id), "phone": l.phone, "name": l.name, "email": getattr(l, "email", None)}
        for l in leads
    ]

    match = DuplicateDetectionService.find_duplicate_match(
        target_phone=req.phone,
        target_email=req.email,
        existing_leads=existing_dicts,
        default_country_code=req.country_code or "+91"
    )

    if match:
        return DeduplicateCheckResponse(
            is_duplicate=True,
            matching_lead_id=match["id"],
            matching_phone=match["phone"],
            matching_name=match.get("name")
        )

    return DeduplicateCheckResponse(is_duplicate=False)


@router.post("/routing/round-robin", response_model=RouteLeadResponse)
async def route_lead_round_robin_endpoint(
    req: RouteLeadRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Executes automated round-robin lead routing across team agents.
    """
    if not req.agent_ids:
        raise HTTPException(status_code=400, detail="agent_ids list cannot be empty")

    assigned_id, next_idx = LeadRoutingService.assign_lead_round_robin(
        lead_id=req.lead_id,
        available_agent_ids=req.agent_ids,
        last_assigned_index=req.last_index
    )

    return RouteLeadResponse(
        assigned_agent_id=str(assigned_id),
        next_index=next_idx
    )


@router.post("/commission/calculate", response_model=CommissionBreakdown)
async def calculate_commission_endpoint(
    req: CommissionCalculateRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Calculates Gross Commission Income (GCI), Brokerage split, and Agent Net payout.
    """
    return CommissionCalculatorService.calculate_deal_commission(
        property_sale_price=req.property_sale_price,
        gross_commission_rate_pct=req.gross_commission_rate_pct,
        agent_split_pct=req.agent_split_pct
    )


@router.get("/leads/{lead_id}/timeline", response_model=TimelineResponse)
async def get_lead_activity_timeline(
    lead_id: uuid.UUID,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns a unified chronological activity timeline for a lead
    combining conversations, AI qualification scores, and system stage updates.
    """
    lead_stmt = select(Lead).where(Lead.id == lead_id, Lead.broker_id == current_broker.id)
    lead_res = await db.execute(lead_stmt)
    lead = lead_res.scalars().first()

    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")

    activities: List[ActivityTimelineItem] = []

    # 1. Lead Created Activity
    activities.append(ActivityTimelineItem(
        id=f"created_{lead.id}",
        type="system",
        timestamp=lead.created_at.isoformat() if lead.created_at else "",
        title="Lead Captured",
        description=f"Lead captured via {lead.source.upper()} channel."
    ))

    # 2. Conversations Timeline
    conv_stmt = select(Conversation).where(Conversation.lead_id == lead_id).order_by(Conversation.created_at.asc())
    conv_res = await db.execute(conv_stmt)
    conversations = conv_res.scalars().all()

    for conv in conversations:
        sender_label = "Lead" if conv.sender_type == "lead" else ("AI Assistant" if conv.sender_type == "bot" else "Broker")
        activities.append(ActivityTimelineItem(
            id=f"conv_{conv.id}",
            type="conversation",
            timestamp=conv.created_at.isoformat() if conv.created_at else "",
            title=f"Message from {sender_label}",
            description=conv.message
        ))

    # 3. AI Score Timeline
    score_stmt = select(Score).where(Score.lead_id == lead_id).order_by(Score.created_at.asc())
    score_res = await db.execute(score_stmt)
    scores = score_res.scalars().all()

    for sc in scores:
        activities.append(ActivityTimelineItem(
            id=f"score_{sc.id}",
            type="score",
            timestamp=sc.created_at.isoformat() if sc.created_at else "",
            title=f"AI Qualified: {sc.score.upper()} Lead",
            description=sc.reasoning or f"Confidence score: {int(sc.confidence * 100)}%"
        ))

    # Sort all chronologically ascending
    activities.sort(key=lambda x: x.timestamp)

    return TimelineResponse(
        lead_id=str(lead_id),
        activities=activities
    )
