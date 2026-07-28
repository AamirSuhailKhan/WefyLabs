from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Broker
from app.schemas.schemas import BrokerCreate, BrokerLogin, BrokerResponse, BrokerUpdate

router = APIRouter(prefix="/auth", tags=["auth"])
broker_router = APIRouter(prefix="/brokers", tags=["brokers"])

@router.post("/register", response_model=BrokerResponse)
def register_broker(broker_in: BrokerCreate, db: Session = Depends(get_db)):
    existing = db.query(Broker).filter(
        (Broker.email == broker_in.email) | (Broker.phone == broker_in.phone)
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Broker with this email or phone already exists")
    
    trial_ends = datetime.now(timezone.utc) + timedelta(days=7)
    broker = Broker(
        name=broker_in.name,
        email=broker_in.email,
        phone=broker_in.phone,
        agency_name=broker_in.agency_name or f"{broker_in.name}'s Agency",
        city=broker_in.city or "Bengaluru",
        whatsapp_number=broker_in.whatsapp_number or broker_in.phone,
        subscription_status="trial",
        trial_ends_at=trial_ends
    )
    db.add(broker)
    db.commit()
    db.refresh(broker)
    return broker

@router.post("/login", response_model=BrokerResponse)
def login_broker(login_in: BrokerLogin, db: Session = Depends(get_db)):
    broker = db.query(Broker).filter(Broker.email == login_in.email).first()
    if not broker:
        # Auto-create demo broker for seamless testing experience
        trial_ends = datetime.now(timezone.utc) + timedelta(days=7)
        broker = Broker(
            name=login_in.email.split("@")[0].capitalize(),
            email=login_in.email,
            phone="+919876543210",
            agency_name=f"{login_in.email.split('@')[0].capitalize()} Realty",
            city="Bengaluru",
            whatsapp_number="+919876543210",
            subscription_status="trial",
            trial_ends_at=trial_ends
        )
        db.add(broker)
        db.commit()
        db.refresh(broker)
    return broker

@broker_router.get("/me", response_model=BrokerResponse)
def get_current_broker(db: Session = Depends(get_db)):
    # Returns default or first broker for single-tenant MVP session mode
    broker = db.query(Broker).first()
    if not broker:
        broker = Broker(
            name="Rahul Sharma",
            email="rahul@bengaluru-homes.in",
            phone="+919876543210",
            agency_name="Apex Realty Bengaluru",
            city="Bengaluru",
            whatsapp_number="+919876543210",
            subscription_status="trial",
            trial_ends_at=datetime.now(timezone.utc) + timedelta(days=7)
        )
        db.add(broker)
        db.commit()
        db.refresh(broker)
    return broker

@broker_router.patch("/me", response_model=BrokerResponse)
def update_broker_profile(broker_update: BrokerUpdate, db: Session = Depends(get_db)):
    broker = db.query(Broker).first()
    if not broker:
        raise HTTPException(status_code=404, detail="Broker profile not found")
    
    if broker_update.name:
        broker.name = broker_update.name
    if broker_update.agency_name:
        broker.agency_name = broker_update.agency_name
    if broker_update.city:
        broker.city = broker_update.city
    if broker_update.whatsapp_number:
        broker.whatsapp_number = broker_update.whatsapp_number
        
    db.commit()
    db.refresh(broker)
    return broker
