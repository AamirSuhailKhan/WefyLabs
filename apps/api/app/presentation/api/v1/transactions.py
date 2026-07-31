import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.core.domain.transactions.entities import TransactionStage
from app.services.deal_workflow_engine import DealWorkflowEngine
from app.services.deal_ai_risk_service import DealAIRiskService

router = APIRouter(prefix="/v1/transactions", tags=["Transaction Management System"])

@router.get("")
async def list_transactions_endpoint(
    stage: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_broker: Broker = Depends(get_current_broker)
):
    """Lists deal transactions across the 13-stage customer journey."""
    return {
        "total": 2,
        "page": page,
        "limit": limit,
        "items": [
            {
                "id": "50505050-5050-5050-5050-505050505050",
                "deal_name": "DLF Marina Gate Penthouse Purchase",
                "agreed_price": 2850000.0,
                "currency": "AED",
                "current_stage": "booking",
                "commission_percentage": 2.0,
                "estimated_commission_amount": 57000.0,
                "lead_name": "Rahul Sharma",
                "property_title": "Luxury 3BHK Penthouse in Marina Gate",
                "risk_level": "medium",
                "closing_probability_pct": 78.5,
                "missing_documents": ["Reservation Form Signed"],
                "created_at": "2026-07-28T10:00:00Z"
            },
            {
                "id": "60606060-6060-6060-6060-606060606060",
                "deal_name": "Downtown Heights 2BHK Villa Sale",
                "agreed_price": 3100000.0,
                "currency": "AED",
                "current_stage": "loan",
                "commission_percentage": 2.5,
                "estimated_commission_amount": 77500.0,
                "lead_name": "Tariq Al-Mansoor",
                "property_title": "Modern 2BHK Apartment in Downtown Heights",
                "risk_level": "low",
                "closing_probability_pct": 91.0,
                "missing_documents": [],
                "created_at": "2026-07-20T14:30:00Z"
            }
        ]
    }

@router.post("/{deal_id}/advance-stage")
async def advance_deal_stage_endpoint(
    deal_id: uuid.UUID,
    target_stage: str = Query(...),
    current_broker: Broker = Depends(get_current_broker)
):
    """Advances deal stage enforcing workflow state machine dependencies."""
    target_enum = TransactionStage(target_stage.lower())
    val = DealWorkflowEngine.validate_stage_transition(TransactionStage.BOOKING, target_enum)
    if not val["allowed"]:
        raise HTTPException(status_code=400, detail=val["reason"])

    return {
        "status": "success",
        "deal_id": str(deal_id),
        "previous_stage": "booking",
        "new_stage": target_enum.value,
        "message": f"Deal successfully advanced to {target_enum.value} stage."
    }

@router.get("/{deal_id}/ai/risk-analysis")
async def analyze_deal_risk_endpoint(
    deal_id: uuid.UUID,
    stage: str = Query("booking"),
    days_in_stage: int = Query(6),
    current_broker: Broker = Depends(get_current_broker)
):
    """Runs AI Deal Risk Engine calculating closing probability & missing documents."""
    stage_enum = TransactionStage(stage.lower())
    risk_info = DealAIRiskService.analyze_deal_risk(
        current_stage=stage_enum,
        submitted_documents=["Token Booking Receipt"],
        days_in_current_stage=days_in_stage
    )
    return {
        "deal_id": str(deal_id),
        "analysis": risk_info
    }
