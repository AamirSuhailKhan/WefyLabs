import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.services.property_ai_valuation_service import PropertyAIValuationService

router = APIRouter(prefix="/v1/properties", tags=["Property Inventory & Valuation Engine"])

@router.get("")
async def list_properties_endpoint(
    city: Optional[str] = Query(None),
    property_type: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_broker: Broker = Depends(get_current_broker)
):
    """Lists property inventory with valuation benchmarks and filters."""
    return {
        "total": 3,
        "page": page,
        "limit": limit,
        "items": [
            {
                "id": "10101010-1010-1010-1010-101010101010",
                "title": "Luxury 3BHK Penthouse in Marina Gate",
                "property_category": "residential",
                "property_type": "penthouse",
                "transaction_category": "resale",
                "status": "available",
                "price": 2850000.0,
                "currency": "AED",
                "built_up_area_sqft": 1850.0,
                "bedrooms": 3,
                "bathrooms": 4,
                "project_name": "Marina Gate 1",
                "building_name": "Tower A",
                "unit_number": "3402",
                "city": "Dubai",
                "locality": "Dubai Marina",
                "amenities": ["Infinity Pool", "Private Gym", "Valet Parking", "Full Sea View"],
                "valuation": {
                    "estimated_market_value": 3237500.0,
                    "estimated_price_per_sqft": 1750.0,
                    "is_overpriced": False,
                    "overpriced_percentage": -11.9,
                    "estimated_annual_roi_yield_pct": 7.8,
                    "confidence_score": 0.94
                }
            },
            {
                "id": "20202020-2020-2020-2020-202020202020",
                "title": "Modern 2BHK Apartment in Downtown Heights",
                "property_category": "residential",
                "property_type": "apartment",
                "transaction_category": "offplan_developer",
                "status": "available",
                "price": 3100000.0,
                "currency": "AED",
                "built_up_area_sqft": 1200.0,
                "bedrooms": 2,
                "bathrooms": 2,
                "project_name": "Downtown Heights",
                "city": "Dubai",
                "locality": "Downtown Dubai",
                "amenities": ["Burj Khalifa View", "Concierge", "Underground Parking"],
                "valuation": {
                    "estimated_market_value": 2880000.0,
                    "estimated_price_per_sqft": 2400.0,
                    "is_overpriced": True,
                    "overpriced_percentage": 7.6,
                    "estimated_annual_roi_yield_pct": 6.8,
                    "confidence_score": 0.89
                }
            }
        ]
    }

@router.get("/{property_id}/valuation")
async def get_property_valuation_endpoint(
    property_id: uuid.UUID,
    price: float = Query(2850000.0),
    area_sqft: float = Query(1850.0),
    locality: str = Query("Dubai Marina"),
    current_broker: Broker = Depends(get_current_broker)
):
    """Runs AI Automated Valuation Model (AVM) for a specific listing."""
    val = PropertyAIValuationService.calculate_valuation(price, area_sqft, locality)
    return {
        "property_id": str(property_id),
        "valuation": {
            "estimated_market_value": val.estimated_market_value,
            "estimated_price_per_sqft": val.estimated_price_per_sqft,
            "is_overpriced": val.is_overpriced,
            "overpriced_percentage": val.overpriced_percentage,
            "estimated_annual_roi_yield_pct": val.estimated_annual_roi_yield_pct,
            "confidence_score": val.confidence_score
        }
    }
