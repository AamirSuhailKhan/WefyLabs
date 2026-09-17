import uuid
from datetime import datetime
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, Depends, Query, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.property_models import PropertyListing
from app.modules.properties.service import PropertyService
from app.services.property_ai_valuation_service import PropertyAIValuationService

router = APIRouter(prefix="/properties", tags=["Property Inventory & Property CRM"])


class PropertyCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = ""
    property_category: Optional[str] = "residential"
    property_type: Optional[str] = "apartment"
    transaction_category: Optional[str] = "resale"
    listing_type: Optional[str] = "exclusive"
    status: Optional[str] = "available"
    price: float = Field(..., gt=0)
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    monthly_rent: Optional[float] = None
    security_deposit: Optional[float] = None
    price_per_sqft: Optional[float] = None
    currency_code: Optional[str] = "INR"
    built_up_area_sqft: float = Field(..., gt=0)
    carpet_area: Optional[float] = None
    super_built_up_area: Optional[float] = None
    plot_area: Optional[float] = None
    bedrooms: Optional[int] = 1
    bathrooms: Optional[int] = 1
    balconies: Optional[int] = 0
    parking_spaces: Optional[int] = 1
    floor_number: Optional[int] = None
    total_floors: Optional[int] = None
    facing: Optional[str] = None
    furnishing: Optional[str] = "unfurnished"
    age_years: Optional[int] = None
    possession_date: Optional[datetime] = None
    construction_status: Optional[str] = "ready_to_move"
    project_name: Optional[str] = None
    developer_name: Optional[str] = None
    building_name: Optional[str] = None
    unit_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = "Bengaluru"
    locality: Optional[str] = "Indiranagar"
    state: Optional[str] = "Karnataka"
    country_code: Optional[str] = "IN"
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    amenities: Optional[List[str]] = Field(default_factory=list)
    marketing_highlights: Optional[List[str]] = Field(default_factory=list)
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    commission_amount: Optional[float] = None
    commission_percentage: Optional[float] = None
    internal_notes: Optional[str] = None


class PropertyUpdateRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    property_category: Optional[str] = None
    property_type: Optional[str] = None
    transaction_category: Optional[str] = None
    listing_type: Optional[str] = None
    status: Optional[str] = None
    price: Optional[float] = None
    price_change_reason: Optional[str] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    monthly_rent: Optional[float] = None
    security_deposit: Optional[float] = None
    price_per_sqft: Optional[float] = None
    currency_code: Optional[str] = None
    area_value: Optional[float] = None
    built_up_area_sqft: Optional[float] = None
    carpet_area: Optional[float] = None
    super_built_up_area: Optional[float] = None
    plot_area: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    balconies: Optional[int] = None
    parking_spaces: Optional[int] = None
    floor_number: Optional[int] = None
    total_floors: Optional[int] = None
    facing: Optional[str] = None
    furnishing: Optional[str] = None
    age_years: Optional[int] = None
    possession_date: Optional[datetime] = None
    construction_status: Optional[str] = None
    project_name: Optional[str] = None
    developer_name: Optional[str] = None
    building_name: Optional[str] = None
    unit_number: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    locality: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    amenities: Optional[List[str]] = None
    marketing_highlights: Optional[List[str]] = None
    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    commission_amount: Optional[float] = None
    commission_percentage: Optional[float] = None
    internal_notes: Optional[str] = None


class PropertyPriceUpdateRequest(BaseModel):
    new_price: float = Field(..., gt=0)
    reason: Optional[str] = None


class ReservePropertyRequest(BaseModel):
    lead_id: Optional[str] = None
    notes: Optional[str] = None


class LeadPropertyLinkRequest(BaseModel):
    lead_id: str
    status: Optional[str] = "INTERESTED"
    interest_level: Optional[str] = "medium"
    notes: Optional[str] = None
    source: Optional[str] = "manual"


class ScheduleVisitRequest(BaseModel):
    lead_id: str
    scheduled_at: datetime
    duration_minutes: Optional[int] = 60
    notes: Optional[str] = None


class VisitOutcomeRequest(BaseModel):
    outcome: str = Field(..., description="attended | cancelled | rescheduled | no_show | interested | rejected")
    feedback: Optional[str] = None
    next_action: Optional[str] = None


class BulkActionRequest(BaseModel):
    property_ids: List[str]
    action: str = Field(..., description="archive | change_status | assign_agent")
    status: Optional[str] = None
    assigned_agent_id: Optional[str] = None


class AIDescriptionRequest(BaseModel):
    title: str
    property_type: Optional[str] = "apartment"
    bedrooms: Optional[int] = 2
    locality: Optional[str] = "Bengaluru"
    price: Optional[float] = 0
    amenities: Optional[List[str]] = None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_properties_endpoint(
    search: Optional[str] = Query(None),
    property_type: Optional[str] = Query(None),
    property_category: Optional[str] = Query(None),
    transaction_category: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    locality: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    min_area: Optional[float] = Query(None),
    max_area: Optional[float] = Query(None),
    bedrooms: Optional[int] = Query(None),
    bathrooms: Optional[int] = Query(None),
    furnishing: Optional[str] = Query(None),
    construction_status: Optional[str] = Query(None),
    assigned_agent_id: Optional[str] = Query(None),
    sort_by: str = Query("newest"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Lists property inventory with multi-attribute filtering, sorting, and pagination."""
    service = PropertyService(db)
    result = await service.search_and_filter(
        broker=current_broker,
        query=search,
        property_type=property_type,
        property_category=property_category,
        transaction_category=transaction_category,
        status_filter=status,
        city=city,
        locality=locality,
        min_price=min_price,
        max_price=max_price,
        min_area=min_area,
        max_area=max_area,
        bedrooms=bedrooms,
        bathrooms=bathrooms,
        furnishing=furnishing,
        construction_status=construction_status,
        assigned_agent_id=assigned_agent_id,
        sort_by=sort_by,
        page=page,
        limit=limit
    )

    # If new broker has no properties yet and no search active, seed 2 initial demo properties
    if result["total"] == 0 and not search and (not property_type or property_type == "all"):
        broker_id = current_broker.id if isinstance(current_broker.id, uuid.UUID) else uuid.UUID(str(current_broker.id))
        seed1 = PropertyListing(
            broker_id=broker_id,
            property_code="PROP-DEMO1",
            title="Luxury 3BHK Penthouse in Marina Gate",
            description="Ultra luxury penthouse with full skyline view",
            property_category="residential",
            property_type="penthouse",
            transaction_category="resale",
            status="available",
            price=28500000.0,
            currency_code="INR",
            area_value=2450.0,
            area_unit="sqft",
            bedrooms=3,
            bathrooms=4,
            parking_spaces=2,
            project_name="Marina Gate",
            city="Bengaluru",
            locality="Indiranagar",
            amenities=["Infinity Pool", "Private Gym", "Valet Parking", "Clubhouse"],
            extended_fields={"amenities": ["Infinity Pool", "Private Gym", "Valet Parking", "Clubhouse"]}
        )
        seed2 = PropertyListing(
            broker_id=broker_id,
            property_code="PROP-DEMO2",
            title="Modern 2BHK Apartment in Downtown Heights",
            description="Contemporary apartment close to tech hubs",
            property_category="residential",
            property_type="apartment",
            transaction_category="resale",
            status="available",
            price=12500000.0,
            currency_code="INR",
            area_value=1350.0,
            area_unit="sqft",
            bedrooms=2,
            bathrooms=2,
            parking_spaces=1,
            project_name="Downtown Heights",
            city="Bengaluru",
            locality="Koramangala",
            amenities=["Concierge", "Underground Parking", "Garden Area"],
            extended_fields={"amenities": ["Concierge", "Underground Parking", "Garden Area"]}
        )
        db.add(seed1)
        db.add(seed2)
        await db.commit()
        result = {
            "total": 2,
            "page": 1,
            "limit": limit,
            "items": [service.serialize_property(seed1), service.serialize_property(seed2)]
        }

    return result


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_property_endpoint(
    req: PropertyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Create a new property listing with valuation benchmarks and audit log."""
    service = PropertyService(db)
    prop = await service.create_property(current_broker, req.model_dump())
    return service.serialize_property(prop)


@router.get("/dashboard")
async def get_inventory_dashboard_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Returns inventory KPIs, status breakdown, price bands, and category distribution."""
    service = PropertyService(db)
    return await service.get_inventory_analytics(current_broker)


@router.get("/demand-analytics")
async def get_demand_analytics_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Compares lead demand preferences against available property inventory."""
    service = PropertyService(db)
    return await service.get_demand_vs_inventory(current_broker)


@router.get("/public/{share_token}")
async def get_public_property_endpoint(
    share_token: str,
    db: AsyncSession = Depends(get_db)
):
    """Publicly accessible, sanitized property view. Owner contact & internal notes REDACTED."""
    service = PropertyService(db)
    return await service.get_public_share(share_token)


@router.get("/visits")
async def list_property_visits_endpoint(
    status: Optional[str] = Query(None),
    limit: int = Query(15, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Lists site visits for the current broker across all properties."""
    service = PropertyService(db)
    return await service.list_site_visits(
        broker=current_broker,
        status_filter=status,
        limit=limit
    )


@router.post("/visits/{meeting_id}/outcome")
async def record_visit_outcome_endpoint(
    meeting_id: str,
    req: VisitOutcomeRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Records the outcome and feedback of an on-site property visit."""
    service = PropertyService(db)
    res = await service.record_visit_outcome(
        meeting_id=meeting_id,
        broker=current_broker,
        outcome=req.outcome,
        feedback=req.feedback,
        next_action=req.next_action
    )
    # Background trigger revenue autopilot evaluation for post site visit follow-up matches
    try:
        from app.modules.revenue_autopilot.engine import RevenueAutopilotEngine
        engine = RevenueAutopilotEngine(db)
        await engine.evaluate_tenant_opportunities(current_broker)
    except Exception:
        pass
    return res


@router.get("/{property_id}")
async def get_property_endpoint(
    property_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Get single property details by ID (tenant-scoped)."""
    service = PropertyService(db)
    prop = await service.get_property(property_id, current_broker)
    return service.serialize_property(prop)


@router.put("/{property_id}")
async def update_property_endpoint(
    property_id: str,
    req: PropertyUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Update property details with price audit logging."""
    service = PropertyService(db)
    prop = await service.update_property(property_id, current_broker, req.model_dump(exclude_unset=True))
    return service.serialize_property(prop)


@router.post("/{property_id}/price")
async def update_property_price_endpoint(
    property_id: str,
    req: PropertyPriceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Updates property price, creates price history audit record, and triggers revenue opportunity evaluation."""
    service = PropertyService(db)
    prop = await service.update_price(
        property_id=property_id,
        broker=current_broker,
        new_price=req.new_price,
        reason=req.reason
    )
    # Background trigger revenue autopilot evaluation for price change matches
    try:
        from app.modules.revenue_autopilot.engine import RevenueAutopilotEngine
        engine = RevenueAutopilotEngine(db)
        await engine.evaluate_tenant_opportunities(current_broker)
    except Exception:
        pass
    return service.serialize_property(prop)


@router.delete("/{property_id}")
async def delete_property_endpoint(
    property_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Soft-deletes and archives a property listing."""
    service = PropertyService(db)
    prop = await service.archive_property(property_id, current_broker)
    return {"status": "success", "message": f"Property {property_id} archived successfully."}


@router.post("/{property_id}/reserve")
async def reserve_property_endpoint(
    property_id: str,
    req: ReservePropertyRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Concurrency-safe atomic property reservation."""
    service = PropertyService(db)
    prop = await service.reserve_property(property_id, current_broker, lead_id=req.lead_id)
    return service.serialize_property(prop)


@router.get("/{property_id}/leads")
async def get_property_leads_endpoint(
    property_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Lists leads interested in this property."""
    service = PropertyService(db)
    return await service.list_interested_leads(property_id, current_broker)


@router.post("/{property_id}/leads")
async def link_lead_property_endpoint(
    property_id: str,
    req: LeadPropertyLinkRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Links a lead's interest to a property with relationship status and metadata."""
    service = PropertyService(db)
    interest = await service.link_lead_property(
        lead_id=req.lead_id,
        property_id=property_id,
        broker=current_broker,
        status=req.status or "INTERESTED",
        interest_level=req.interest_level or "medium",
        notes=req.notes,
        source=req.source or "manual"
    )
    return {
        "status": "success",
        "interest_id": str(interest.id),
        "lead_id": str(interest.lead_id),
        "property_id": str(interest.property_id),
        "relationship_status": interest.status
    }


@router.post("/{property_id}/visits")
async def schedule_property_visit_endpoint(
    property_id: str,
    req: ScheduleVisitRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Schedules a site visit, creates meeting and agent task, and records activity."""
    service = PropertyService(db)
    return await service.schedule_site_visit(
        lead_id=req.lead_id,
        property_id=property_id,
        broker=current_broker,
        scheduled_at=req.scheduled_at,
        duration_minutes=req.duration_minutes or 60,
        notes=req.notes
    )



@router.post("/import")
async def import_properties_csv_endpoint(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Batch imports property inventory from CSV with security scanning and duplicate checking."""
    content = await file.read()
    service = PropertyService(db)
    return await service.import_properties_csv(
        broker=current_broker,
        file_content=content,
        filename=file.filename or "inventory.csv"
    )


@router.post("/bulk")
async def bulk_properties_endpoint(
    req: BulkActionRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Performs bulk operations (archive, status update, agent assignment) on selected properties."""
    service = PropertyService(db)
    processed = 0
    for pid in req.property_ids:
        try:
            if req.action == "archive":
                await service.archive_property(pid, current_broker)
            elif req.action == "change_status" and req.status:
                await service.update_property(pid, current_broker, {"status": req.status})
            elif req.action == "assign_agent" and req.assigned_agent_id:
                await service.update_property(pid, current_broker, {"assigned_agent_id": req.assigned_agent_id})
            processed += 1
        except Exception:
            pass
    return {"status": "success", "action": req.action, "processed_count": processed}


@router.post("/ai-description")
async def generate_ai_description_endpoint(
    req: AIDescriptionRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Generates a professional marketing description strictly grounded in property facts."""
    service = PropertyService(db)
    return await service.generate_ai_description(req.model_dump())


@router.get("/{property_id}/valuation")
async def get_property_valuation_endpoint(
    property_id: str,
    price: Optional[float] = Query(None),
    area_sqft: Optional[float] = Query(None),
    locality: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Backwards-compatible AI Automated Property Valuation Benchmark endpoint."""
    service = PropertyService(db)
    prop = await service.get_property(property_id, current_broker)

    eval_price = price or float(prop.price)
    eval_area = area_sqft or float(prop.area_value)
    eval_loc = locality or prop.locality or "Bengaluru"

    val = PropertyAIValuationService.calculate_valuation(
        price=eval_price,
        built_up_area_sqft=eval_area,
        locality=eval_loc
    )
    return {
        "property_id": str(prop.id),
        "title": prop.title,
        "input": {
            "price": eval_price,
            "area_sqft": eval_area,
            "locality": eval_loc
        },
        "valuation": {
            "estimated_market_value": val.estimated_market_value,
            "estimated_price_per_sqft": val.estimated_price_per_sqft,
            "is_overpriced": val.is_overpriced,
            "overpriced_percentage": val.overpriced_percentage,
            "estimated_annual_roi_yield_pct": val.estimated_annual_roi_yield_pct,
            "confidence_score": val.confidence_score
        }
    }
