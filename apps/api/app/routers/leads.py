from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_
from app.database import get_db
from app.models.models import Broker, Lead, Conversation, Score
from app.schemas.schemas import LeadCreate, LeadResponse, LeadDetailResponse, LeadListResponse, LeadUpdateStatus

router = APIRouter(prefix="/leads", tags=["leads"])

def get_or_create_default_broker(db: Session) -> Broker:
    broker = db.query(Broker).first()
    if not broker:
        broker = Broker(
            name="Rahul Sharma",
            email="rahul@bengaluru-homes.in",
            phone="+919876543210",
            agency_name="Apex Realty Bengaluru",
            city="Bengaluru",
            whatsapp_number="+919876543210"
        )
        db.add(broker)
        db.commit()
        db.refresh(broker)
    return broker

@router.get("", response_model=LeadListResponse)
def list_leads(
    score: Optional[str] = Query(None, description="Filter by score: hot, warm, cold, spam"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status"),
    search: Optional[str] = Query(None, description="Search phone or name"),
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    broker = get_or_create_default_broker(db)
    query = db.query(Lead).filter(Lead.broker_id == broker.id)
    
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

@router.post("", response_model=LeadResponse)
def create_lead(lead_in: LeadCreate, db: Session = Depends(get_db)):
    broker = get_or_create_default_broker(db)
    
    lead = Lead(
        broker_id=broker.id,
        phone=lead_in.phone,
        name=lead_in.name or "New Lead",
        source=lead_in.source or "manual",
        status="pending",
        score="pending"
    )
    db.add(lead)
    db.commit()
    db.refresh(lead)
    
    # Add initial system message if notes exist
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

@router.get("/{lead_id}", response_model=LeadDetailResponse)
def get_lead_detail(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    latest_score = db.query(Score).filter(Score.lead_id == lead_id).order_by(desc(Score.created_at)).first()
    
    response = LeadDetailResponse.model_validate(lead)
    if latest_score:
        response.latest_score = latest_score
        
    return response

@router.patch("/{lead_id}/status", response_model=LeadResponse)
def update_lead_status(lead_id: str, status_in: LeadUpdateStatus, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
        
    lead.status = status_in.status
    db.commit()
    db.refresh(lead)
    return lead
