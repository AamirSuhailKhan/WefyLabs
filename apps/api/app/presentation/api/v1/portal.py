import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.services.customer_portal_service import CustomerPortalService

router = APIRouter(prefix="/v1/portal", tags=["Zillow & Airbnb Grade Customer Self-Service Portal"])

class AskAIPropertyRequest(BaseModel):
    question: str
    property_title: Optional[str] = "DLF Marina Gate Penthouse"

@router.get("/dashboard")
async def get_customer_portal_dashboard(
    customer_id: uuid.UUID = Query(uuid.UUID("22222222-2222-2222-2222-222222222222")),
    current_broker: Broker = Depends(get_current_broker)
):
    """Returns self-service buyer portal dashboard (Deal progress, assigned broker, saved properties)."""
    portal = CustomerPortalService.get_customer_dashboard(customer_id)
    return {
        "customer": {
            "name": portal.name,
            "email": portal.email,
            "phone": portal.phone,
            "role": portal.role.value,
            "saved_properties_count": portal.saved_properties_count
        },
        "assigned_broker": {
            "name": portal.assigned_broker_name,
            "phone": portal.assigned_broker_phone
        },
        "active_deal": {
            "deal_id": str(portal.active_deal.deal_id),
            "property_title": portal.active_deal.property_title,
            "agreed_price": portal.active_deal.agreed_price,
            "current_stage": portal.active_deal.current_stage,
            "booking_deposit_paid": portal.active_deal.booking_deposit_paid,
            "loan_approval_status": portal.active_deal.loan_approval_status,
            "legal_noc_status": portal.active_deal.legal_noc_status,
            "estimated_registration_date": portal.active_deal.estimated_registration_date,
            "completion_percentage": portal.active_deal.completion_percentage
        } if portal.active_deal else None
    }

@router.post("/ai/ask-property")
async def ask_ai_property_advisor_endpoint(
    req: AskAIPropertyRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """AI Property Advisor for customers (Mortgage estimation, legal fees, ROI advice)."""
    res = CustomerPortalService.ask_ai_property_advisor(req.question, req.property_title or "")
    return res
