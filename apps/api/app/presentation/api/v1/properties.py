import uuid
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.property_models import PropertyListing
from app.services.property_ai_valuation_service import PropertyAIValuationService

router = APIRouter(prefix="/properties", tags=["Property Inventory & Valuation Engine"])


class PropertyCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = ""
    property_category: Optional[str] = "residential"
    property_type: Optional[str] = "apartment"
    transaction_category: Optional[str] = "resale"
    status: Optional[str] = "available"
    price: float = Field(..., gt=0)
    currency_code: Optional[str] = "INR"
    built_up_area_sqft: float = Field(..., gt=0)
    bedrooms: Optional[int] = 1
    bathrooms: Optional[int] = 1
    parking_spaces: Optional[int] = 1
    project_name: Optional[str] = None
    building_name: Optional[str] = None
    unit_number: Optional[str] = None
    city: Optional[str] = "Bengaluru"
    locality: Optional[str] = "Indiranagar"
    amenities: Optional[List[str]] = Field(default_factory=list)


def _to_prop_dict(p: PropertyListing) -> Dict[str, Any]:
    val = PropertyAIValuationService.calculate_valuation(
        price=float(p.price),
        area_sqft=float(p.area_value),
        locality=p.locality or "Bengaluru"
    )
    amenities = []
    if p.extended_fields and isinstance(p.extended_fields, dict):
        amenities = p.extended_fields.get("amenities", [])

    return {
        "id": str(p.id),
        "broker_id": str(p.broker_id),
        "title": p.title,
        "description": p.description,
        "property_category": p.property_category,
        "property_type": p.property_type,
        "transaction_category": p.transaction_category,
        "status": p.status,
        "price": float(p.price),
        "currency": p.currency_code or "INR",
        "currency_code": p.currency_code or "INR",
        "built_up_area_sqft": float(p.area_value),
        "area_value": float(p.area_value),
        "area_unit": p.area_unit,
        "bedrooms": p.bedrooms,
        "bathrooms": p.bathrooms,
        "parking_spaces": p.parking_spaces,
        "project_name": p.project_name,
        "building_name": p.building_name,
        "unit_number": p.unit_number,
        "city": p.city,
        "locality": p.locality,
        "amenities": amenities,
        "valuation": {
            "estimated_market_value": val.estimated_market_value,
            "estimated_price_per_sqft": val.estimated_price_per_sqft,
            "is_overpriced": val.is_overpriced,
            "overpriced_percentage": val.overpriced_percentage,
            "estimated_annual_roi_yield_pct": val.estimated_annual_roi_yield_pct,
            "confidence_score": val.confidence_score
        }
    }


@router.get("")
async def list_properties_endpoint(
    city: Optional[str] = Query(None),
    property_type: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Lists property inventory with valuation benchmarks and filters."""
    broker_id = current_broker.id
    if isinstance(broker_id, str):
        broker_id = uuid.UUID(broker_id)

    stmt = select(PropertyListing).where(
        PropertyListing.broker_id == broker_id,
        PropertyListing.deleted_at.is_(None)
    )

    if property_type and property_type.lower() != "all":
        stmt = stmt.where(PropertyListing.property_type.ilike(f"%{property_type}%"))
    if city:
        stmt = stmt.where(PropertyListing.city.ilike(f"%{city}%"))
    if min_price is not None:
        stmt = stmt.where(PropertyListing.price >= min_price)
    if max_price is not None:
        stmt = stmt.where(PropertyListing.price <= max_price)
    if search:
        search_term = f"%{search.strip()}%"
        stmt = stmt.where(
            (PropertyListing.title.ilike(search_term)) |
            (PropertyListing.locality.ilike(search_term)) |
            (PropertyListing.project_name.ilike(search_term))
        )

    res = await db.execute(stmt.order_by(PropertyListing.created_at.desc()))
    items = list(res.scalars().all())

    # If new broker has no properties yet, seed 2 initial demo properties in database
    if not items and not search and (not property_type or property_type == "all"):
        seed1 = PropertyListing(
            broker_id=broker_id,
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
            extended_fields={"amenities": ["Infinity Pool", "Private Gym", "Valet Parking", "Clubhouse"]}
        )
        seed2 = PropertyListing(
            broker_id=broker_id,
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
            extended_fields={"amenities": ["Concierge", "Underground Parking", "Garden Area"]}
        )
        db.add(seed1)
        db.add(seed2)
        await db.commit()
        items = [seed1, seed2]

    return {
        "total": len(items),
        "page": page,
        "limit": limit,
        "items": [_to_prop_dict(p) for p in items]
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_property_endpoint(
    req: PropertyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Create a new property listing with AI Automated Valuation."""
    broker_id = current_broker.id
    if isinstance(broker_id, str):
        broker_id = uuid.UUID(broker_id)

    listing = PropertyListing(
        broker_id=broker_id,
        title=req.title,
        description=req.description or "",
        property_category=req.property_category or "residential",
        property_type=req.property_type or "apartment",
        transaction_category=req.transaction_category or "resale",
        status=req.status or "available",
        price=req.price,
        currency_code=req.currency_code or "INR",
        area_value=req.built_up_area_sqft,
        area_unit="sqft",
        bedrooms=req.bedrooms or 1,
        bathrooms=req.bathrooms or 1,
        parking_spaces=req.parking_spaces or 1,
        project_name=req.project_name,
        building_name=req.building_name,
        unit_number=req.unit_number,
        city=req.city or "Bengaluru",
        locality=req.locality or "Indiranagar",
        extended_fields={"amenities": req.amenities or []}
    )
    db.add(listing)
    await db.commit()
    await db.refresh(listing)

    return _to_prop_dict(listing)


@router.get("/{property_id}")
async def get_property_endpoint(
    property_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Get single property details by ID."""
    broker_id = current_broker.id
    if isinstance(broker_id, str):
        broker_id = uuid.UUID(broker_id)

    try:
        p_uuid = uuid.UUID(property_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    stmt = select(PropertyListing).where(
        PropertyListing.id == p_uuid,
        PropertyListing.broker_id == broker_id,
        PropertyListing.deleted_at.is_(None)
    )
    res = await db.execute(stmt)
    prop = res.scalars().first()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    return _to_prop_dict(prop)


@router.delete("/{property_id}")
async def delete_property_endpoint(
    property_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Delete / archive property listing."""
    broker_id = current_broker.id
    if isinstance(broker_id, str):
        broker_id = uuid.UUID(broker_id)

    try:
        p_uuid = uuid.UUID(property_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    stmt = select(PropertyListing).where(
        PropertyListing.id == p_uuid,
        PropertyListing.broker_id == broker_id
    )
    res = await db.execute(stmt)
    prop = res.scalars().first()
    if not prop:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Property not found")

    await db.delete(prop)
    await db.commit()
    return {"status": "success", "message": "Property deleted successfully"}


@router.get("/{property_id}/valuation")
async def get_property_valuation_endpoint(
    property_id: str,
    price: float = Query(28500000.0),
    area_sqft: float = Query(2450.0),
    locality: str = Query("Indiranagar"),
    current_broker: Broker = Depends(get_current_broker)
):
    """Runs AI Automated Valuation Model (AVM) for a specific listing."""
    val = PropertyAIValuationService.calculate_valuation(price, area_sqft, locality)
    return {
        "property_id": property_id,
        "valuation": {
            "estimated_market_value": val.estimated_market_value,
            "estimated_price_per_sqft": val.estimated_price_per_sqft,
            "is_overpriced": val.is_overpriced,
            "overpriced_percentage": val.overpriced_percentage,
            "estimated_annual_roi_yield_pct": val.estimated_annual_roi_yield_pct,
            "confidence_score": val.confidence_score
        }
    }

