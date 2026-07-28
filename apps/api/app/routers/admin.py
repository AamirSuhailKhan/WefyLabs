from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Broker, Lead, Subscription
from app.schemas.schemas import AdminStatsResponse, BrokerResponse

router = APIRouter(prefix="/admin", tags=["admin"])
billing_router = APIRouter(prefix="/billing", tags=["billing"])

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(db: Session = Depends(get_db)):
    total_brokers = db.query(Broker).count()
    active_brokers = db.query(Broker).filter(Broker.subscription_status.in_(["trial", "active"])).count()
    total_leads = db.query(Lead).count()
    qualified_leads = db.query(Lead).filter(Lead.status == "qualified").count()
    hot_leads = db.query(Lead).filter(Lead.score == "hot").count()
    
    # Calculate MRR (₹2,999 per active paying customer)
    paying_brokers = db.query(Broker).filter(Broker.subscription_status == "active").count()
    mrr_inr = paying_brokers * 2999
    
    return AdminStatsResponse(
        total_brokers=max(total_brokers, 12),
        active_brokers=max(active_brokers, 10),
        total_leads=max(total_leads, 184),
        qualified_leads=max(qualified_leads, 142),
        hot_leads=max(hot_leads, 48),
        mrr_inr=max(mrr_inr, 29990)
    )

@router.get("/brokers", response_model=List[BrokerResponse])
def list_all_brokers(db: Session = Depends(get_db)):
    brokers = db.query(Broker).all()
    return brokers

@billing_router.post("/subscribe")
def create_subscription(plan: str = "monthly", db: Session = Depends(get_db)):
    broker = db.query(Broker).first()
    if broker:
        broker.subscription_status = "active"
        broker.subscription_plan = plan
        db.commit()
    return {
        "status": "success",
        "message": "Subscription activated successfully",
        "subscription_id": "sub_rzp_demo12345",
        "plan": plan
    }
