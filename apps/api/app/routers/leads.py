"""
Legacy Leads Router (DEPRECATED)
================================
This router is deprecated and retained strictly for legacy backward compatibility.
Canonical lead operations must use `/api/v1/leads` (app.modules.leads.router).

Security Enforcement:
- Unauthenticated access is rejected (401 via get_current_broker).
- get_or_create_default_broker() is REMOVED to prevent tenant isolation bypass.
- All operations are strictly scoped to the authenticated broker (IDOR prevention).
"""
import uuid
import warnings
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.score import Score
from app.schemas.schemas import LeadCreate, LeadResponse, LeadDetailResponse, LeadListResponse, LeadUpdateStatus

router = APIRouter(prefix="/leads", tags=["leads-legacy (deprecated)"])

DEPRECATION_WARNING = "The /leads endpoint is deprecated. Please migrate to /api/v1/leads."


def _add_deprecation_header(response: Response) -> None:
    response.headers["X-API-Deprecation"] = DEPRECATION_WARNING
    response.headers["Deprecation"] = "true"


@router.get("", response_model=LeadListResponse, deprecated=True)
def list_leads(
    response: Response,
    score: Optional[str] = Query(None, description="Filter by score: hot, warm, cold, spam"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    search: Optional[str] = Query(None, description="Search phone or name"),
    skip: int = 0,
    limit: int = 50,
    current_broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    """List leads scoped strictly to the authenticated broker."""
    _add_deprecation_header(response)
    query = db.query(Lead).filter(
        Lead.broker_id == current_broker.id,
        Lead.deleted_at.is_(None)
    )
    
    if score:
        query = query.filter(Lead.score == score.lower())
    if status_filter:
        query = query.filter(Lead.status == status_filter.lower())
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(Lead.phone.like(search_term), Lead.name.like(search_term))
        )
        
    total = query.count()
    items = query.order_by(desc(Lead.created_at)).offset(skip).limit(limit).all()
    
    return {"total": total, "items": items}


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED, deprecated=True)
def create_lead(
    lead_in: LeadCreate,
    response: Response,
    current_broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    """Create lead scoped strictly to the authenticated broker."""
    _add_deprecation_header(response)
    lead = Lead(
        broker_id=current_broker.id,
        phone=lead_in.phone,
        name=lead_in.name or "New Lead",
        source=lead_in.source or "manual",
        status="pending",
        score="pending"
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    
    # Add initial message if notes exist
    if lead_in.notes:
        conv = Conversation(
            lead_id=lead.id,
            direction="inbound",
            sender_type="broker",
            message=f"Notes: {lead_in.notes}"
        )
        db.add(conv)
        db.commit()
        
    return lead


@router.get("/{lead_id}", response_model=LeadDetailResponse, deprecated=True)
def get_lead_detail(
    lead_id: uuid.UUID,
    response: Response,
    current_broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    """Get lead detail scoped strictly to authenticated broker (IDOR prevention)."""
    _add_deprecation_header(response)
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.broker_id == current_broker.id,
        Lead.deleted_at.is_(None)
    ).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        
    latest_score = db.query(Score).filter(Score.lead_id == lead_id).order_by(desc(Score.created_at)).first()
    
    lead_resp = LeadDetailResponse.model_validate(lead)
    if latest_score:
        lead_resp.latest_score = latest_score
        
    return lead_resp


@router.patch("/{lead_id}/status", response_model=LeadResponse, deprecated=True)
def update_lead_status(
    lead_id: uuid.UUID,
    status_in: LeadUpdateStatus,
    response: Response,
    current_broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    """Update lead status scoped strictly to authenticated broker (IDOR prevention)."""
    _add_deprecation_header(response)
    lead = db.query(Lead).filter(
        Lead.id == lead_id,
        Lead.broker_id == current_broker.id,
        Lead.deleted_at.is_(None)
    ).first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")
        
    lead.status = status_in.status
    db.commit()
    db.refresh(lead)
    return lead
