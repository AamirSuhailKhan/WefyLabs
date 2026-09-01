import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.customer_success_models import CustomerHealthRecord, SupportTicket

router = APIRouter(prefix="/customer-success", tags=["Customer Success & Retention Platform"])

# --- Schemas ---
class FeedbackSubmissionRequest(BaseModel):
    nps_score: Optional[int] = Field(None, ge=0, le=10)
    csat_score: Optional[int] = Field(None, ge=1, le=5)
    feedback_notes: Optional[str] = None

class CreateSupportTicketRequest(BaseModel):
    subject: str = Field(..., max_length=255)
    description: str
    priority: str = Field("medium", max_length=20) # low | medium | high | urgent

class CustomerHealthResponse(BaseModel):
    broker_id: str
    health_score: int # 0-100
    health_status: str # healthy | warning | at_risk
    churn_risk_pct: float
    onboarding_completed_pct: int
    nps_score: Optional[int] = None
    csat_score: Optional[int] = None
    retention_recommendations: List[str]

class SupportTicketResponse(BaseModel):
    id: str
    subject: str
    priority: str
    status: str
    created_at: str


# --- Endpoints ---

@router.get("/health", response_model=CustomerHealthResponse)
async def get_customer_health_score(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """
    Computes real-time Customer Health Score, Churn Risk %, and Onboarding Progress
    by analyzing lead activity, trial days remaining, and feature adoption.
    """
    # Query workspace leads
    stmt = select(func.count(Lead.id)).where(Lead.broker_id == current_broker.id, Lead.deleted_at.is_(None))
    res = await db.execute(stmt)
    lead_count = res.scalar() or 0

    # Calculate onboarding completion %
    onboarding_pct = 40
    if lead_count > 0: onboarding_pct += 30
    if current_broker.whatsapp_number: onboarding_pct += 30
    onboarding_pct = min(100, onboarding_pct)

    # Health Score Calculation
    base_score = 70
    if lead_count >= 5: base_score += 20
    if current_broker.subscription_status == "active": base_score += 10
    elif current_broker.trial_days_remaining <= 2: base_score -= 25

    health_score = max(10, min(100, base_score))
    
    if health_score >= 80:
        health_status = "healthy"
        churn_risk = 5.0
    elif health_score >= 50:
        health_status = "warning"
        churn_risk = 25.0
    else:
        health_status = "at_risk"
        churn_risk = 75.0

    recommendations = []
    if lead_count == 0:
        recommendations.append("Import or capture your first WhatsApp lead to boost workspace health.")
    if onboarding_pct < 100:
        recommendations.append("Complete WhatsApp Meta Cloud API setup in Settings.")
    if current_broker.subscription_status == "trial":
        recommendations.append(f"Upgrade subscription before 7-day trial ends ({current_broker.trial_days_remaining} days left).")

    return CustomerHealthResponse(
        broker_id=str(current_broker.id),
        health_score=health_score,
        health_status=health_status,
        churn_risk_pct=churn_risk,
        onboarding_completed_pct=onboarding_pct,
        retention_recommendations=recommendations or ["Workspace operating at peak performance."]
    )


@router.post("/feedback", status_code=status.HTTP_200_OK)
async def submit_customer_feedback(
    req: FeedbackSubmissionRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Submits NPS (0-10) or CSAT (1-5) customer sentiment feedback."""
    stmt = select(CustomerHealthRecord).where(CustomerHealthRecord.broker_id == current_broker.id)
    res = await db.execute(stmt)
    record = res.scalars().first()

    if not record:
        record = CustomerHealthRecord(broker_id=current_broker.id)
        db.add(record)

    if req.nps_score is not None:
        record.nps_score = req.nps_score
    if req.csat_score is not None:
        record.csat_score = req.csat_score

    await db.commit()
    return {"status": "success", "message": "Feedback recorded successfully"}


@router.post("/support/tickets", response_model=SupportTicketResponse, status_code=status.HTTP_201_CREATED)
async def create_support_ticket(
    req: CreateSupportTicketRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new customer support ticket in the Support Console."""
    ticket = SupportTicket(
        broker_id=current_broker.id,
        subject=req.subject,
        description=req.description,
        priority=req.priority.lower(),
        status="open"
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    return SupportTicketResponse(
        id=str(ticket.id),
        subject=ticket.subject,
        priority=ticket.priority,
        status=ticket.status,
        created_at=ticket.created_at.isoformat() if ticket.created_at else ""
    )


@router.get("/support/tickets", response_model=List[SupportTicketResponse])
async def list_support_tickets(
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Lists all support tickets submitted by the current broker."""
    stmt = select(SupportTicket).where(SupportTicket.broker_id == current_broker.id).order_by(SupportTicket.created_at.desc())
    res = await db.execute(stmt)
    tickets = res.scalars().all()

    return [
        SupportTicketResponse(
            id=str(t.id),
            subject=t.subject,
            priority=t.priority,
            status=t.status,
            created_at=t.created_at.isoformat() if t.created_at else ""
        )
        for t in tickets
    ]
