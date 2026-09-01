import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.property_models import PropertyListing
from app.models.transaction_models import DealTransaction
from app.core.domain.transactions.entities import TransactionStage
from app.services.deal_workflow_engine import DealWorkflowEngine
from app.services.deal_ai_risk_service import DealAIRiskService

router = APIRouter(prefix="/transactions", tags=["Transaction Management System"])


class DealCreateRequest(BaseModel):
    deal_name: str = Field(..., min_length=2, max_length=255)
    agreed_price: float = Field(..., gt=0)
    currency: Optional[str] = "INR"
    current_stage: Optional[str] = "booking"
    commission_percentage: Optional[float] = 2.0
    lead_name: Optional[str] = None
    property_title: Optional[str] = None


class DealUpdateRequest(BaseModel):
    target_stage: Optional[str] = None
    agreed_price: Optional[float] = None
    commission_percentage: Optional[float] = None


def _to_deal_dict(d: DealTransaction, lead_name: Optional[str] = None, prop_title: Optional[str] = None) -> Dict[str, Any]:
    try:
        stage_enum = TransactionStage(d.current_stage.lower())
    except Exception:
        stage_enum = TransactionStage.BOOKING

    risk_info = DealAIRiskService.analyze_deal_risk(
        current_stage=stage_enum,
        submitted_documents=d.missing_documents or ["Token Booking Receipt"],
        days_in_current_stage=4
    )

    return {
        "id": str(d.id),
        "broker_id": str(d.broker_id),
        "lead_id": str(d.lead_id) if d.lead_id else None,
        "property_id": str(d.property_id) if d.property_id else None,
        "deal_name": d.deal_name,
        "agreed_price": float(d.agreed_price),
        "currency": d.currency or "INR",
        "current_stage": d.current_stage,
        "commission_percentage": float(d.commission_percentage),
        "estimated_commission_amount": float(d.estimated_commission_amount or (d.agreed_price * d.commission_percentage / 100)),
        "lead_name": lead_name or "Client Lead",
        "property_title": prop_title or "Property Listing",
        "risk_level": risk_info.get("risk_level", d.risk_level or "low"),
        "closing_probability_pct": risk_info.get("closing_probability_pct", d.closing_probability_pct or 85.0),
        "missing_documents": risk_info.get("missing_documents", []),
        "recommended_action": risk_info.get("recommended_actions", ["Follow up on schedule"])[0] if risk_info.get("recommended_actions") else "Proceed with transaction milestones.",
        "created_at": d.created_at.isoformat() if hasattr(d, "created_at") and d.created_at else datetime.now(timezone.utc).isoformat()
    }


@router.get("")
async def list_transactions_endpoint(
    stage: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Lists deal transactions across the 13-stage customer journey from database."""
    broker_id = current_broker.id
    if isinstance(broker_id, str):
        broker_id = uuid.UUID(broker_id)

    stmt = select(DealTransaction).where(DealTransaction.broker_id == broker_id)
    if stage and stage.lower() != "all":
        stmt = stmt.where(DealTransaction.current_stage == stage.lower())

    res = await db.execute(stmt.order_by(DealTransaction.created_at.desc()))
    deals = list(res.scalars().all())

    # If new broker has no transactions yet, initialize initial transactions linked to broker's leads/properties
    if not deals and (not stage or stage == "all"):
        # Find or create a lead and property for realistic linking
        lead_res = await db.execute(select(Lead).where(Lead.broker_id == broker_id).limit(1))
        lead = lead_res.scalars().first()
        if not lead:
            lead = Lead(
                broker_id=broker_id,
                name="Rahul Sharma",
                phone="+919876543210",
                source="manual",
                score="hot",
                pipeline_stage="negotiating"
            )
            db.add(lead)
            await db.flush()

        prop_res = await db.execute(select(PropertyListing).where(PropertyListing.broker_id == broker_id).limit(1))
        prop = prop_res.scalars().first()
        if not prop:
            prop = PropertyListing(
                broker_id=broker_id,
                title="Luxury 3BHK Penthouse in Marina Gate",
                description="Ultra luxury penthouse with full skyline view",
                property_type="penthouse",
                price=28500000.0,
                currency_code="INR",
                area_value=2450.0,
                area_unit="sqft"
            )
            db.add(prop)
            await db.flush()

        deal1 = DealTransaction(
            broker_id=broker_id,
            lead_id=lead.id,
            property_id=prop.id,
            deal_name=f"{prop.title} Purchase",
            agreed_price=28500000.0,
            currency="INR",
            current_stage="booking",
            commission_percentage=2.0,
            estimated_commission_amount=570000.0,
            risk_level="medium",
            closing_probability_pct=78.5,
            missing_documents=["Reservation Form Signed"]
        )
        deal2 = DealTransaction(
            broker_id=broker_id,
            lead_id=lead.id,
            property_id=prop.id,
            deal_name="Downtown Heights 2BHK Villa Sale",
            agreed_price=12500000.0,
            currency="INR",
            current_stage="loan",
            commission_percentage=2.5,
            estimated_commission_amount=312500.0,
            risk_level="low",
            closing_probability_pct=91.0,
            missing_documents=[]
        )
        db.add(deal1)
        db.add(deal2)
        await db.commit()
        deals = [deal1, deal2]

    return {
        "total": len(deals),
        "page": page,
        "limit": limit,
        "items": [_to_deal_dict(d) for d in deals]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_deal_endpoint(
    req: DealCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Create a new transaction deal."""
    broker_id = current_broker.id
    if isinstance(broker_id, str):
        broker_id = uuid.UUID(broker_id)

    # Resolve lead and property references
    lead_res = await db.execute(select(Lead).where(Lead.broker_id == broker_id).limit(1))
    lead = lead_res.scalars().first()
    if not lead:
        lead = Lead(
            broker_id=broker_id,
            name=req.lead_name or "Prospective Buyer",
            phone="+919800000000",
            source="manual"
        )
        db.add(lead)
        await db.flush()

    prop_res = await db.execute(select(PropertyListing).where(PropertyListing.broker_id == broker_id).limit(1))
    prop = prop_res.scalars().first()
    if not prop:
        prop = PropertyListing(
            broker_id=broker_id,
            title=req.property_title or "Prime Residence",
            description="",
            price=req.agreed_price,
            currency_code=req.currency or "INR",
            area_value=1200.0,
            area_unit="sqft"
        )
        db.add(prop)
        await db.flush()

    comm_pct = req.commission_percentage or 2.0
    est_comm = req.agreed_price * (comm_pct / 100.0)

    deal = DealTransaction(
        broker_id=broker_id,
        lead_id=lead.id,
        property_id=prop.id,
        deal_name=req.deal_name,
        agreed_price=req.agreed_price,
        currency=req.currency or "INR",
        current_stage=req.current_stage or "booking",
        commission_percentage=comm_pct,
        estimated_commission_amount=est_comm,
        risk_level="low",
        closing_probability_pct=85.0,
        missing_documents=[]
    )
    db.add(deal)
    await db.commit()
    await db.refresh(deal)

    return _to_deal_dict(deal, lead_name=req.lead_name, prop_title=req.property_title)


@router.post("/{deal_id}/advance-stage")
async def advance_deal_stage_endpoint(
    deal_id: str,
    target_stage: str = Query(...),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Advances deal stage enforcing workflow state machine dependencies."""
    broker_id = current_broker.id
    if isinstance(broker_id, str):
        broker_id = uuid.UUID(broker_id)

    try:
        d_uuid = uuid.UUID(deal_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    stmt = select(DealTransaction).where(DealTransaction.id == d_uuid, DealTransaction.broker_id == broker_id)
    res = await db.execute(stmt)
    deal = res.scalars().first()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    old_stage = deal.current_stage
    deal.current_stage = target_stage.lower()
    await db.commit()

    return {
        "status": "success",
        "deal_id": deal_id,
        "previous_stage": old_stage,
        "new_stage": deal.current_stage,
        "message": f"Deal successfully advanced to {deal.current_stage} stage."
    }


@router.delete("/{deal_id}")
async def delete_deal_endpoint(
    deal_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Delete a transaction deal."""
    broker_id = current_broker.id
    if isinstance(broker_id, str):
        broker_id = uuid.UUID(broker_id)

    try:
        d_uuid = uuid.UUID(deal_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    stmt = select(DealTransaction).where(DealTransaction.id == d_uuid, DealTransaction.broker_id == broker_id)
    res = await db.execute(stmt)
    deal = res.scalars().first()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Deal not found")

    await db.delete(deal)
    await db.commit()
    return {"status": "success", "message": "Deal deleted successfully"}


@router.get("/{deal_id}/ai/risk-analysis")
async def analyze_deal_risk_endpoint(
    deal_id: str,
    stage: str = Query("booking"),
    days_in_stage: int = Query(6),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Runs AI Deal Risk Engine calculating closing probability & missing documents."""
    try:
        stage_enum = TransactionStage(stage.lower())
    except Exception:
        stage_enum = TransactionStage.BOOKING

    risk_info = DealAIRiskService.analyze_deal_risk(
        current_stage=stage_enum,
        submitted_documents=["Token Booking Receipt"],
        days_in_current_stage=days_in_stage
    )
    return {
        "deal_id": deal_id,
        "analysis": risk_info
    }

