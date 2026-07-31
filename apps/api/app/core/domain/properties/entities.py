import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, List, Dict, Any

class PropertyCategory(str, Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"

class PropertyType(str, Enum):
    APARTMENT = "apartment"
    VILLA = "villa"
    TOWNHOUSE = "townhouse"
    PENTHOUSE = "penthouse"
    OFFICE = "office"
    RETAIL = "retail"

class TransactionCategory(str, Enum):
    OFFPLAN_DEVELOPER = "offplan_developer"
    RESALE = "resale"
    RENTAL = "rental"

class PropertyStatus(str, Enum):
    AVAILABLE = "available"
    UNDER_OFFER = "under_offer"
    SOLD = "sold"
    RENTED = "rented"
    RESERVED = "reserved"

@dataclass
class PropertyMediaEntity:
    id: uuid.UUID
    media_type: str # photo | floorplan | video | tour_360
    url: str
    title: Optional[str] = None
    is_primary: bool = False

@dataclass
class PropertyValuationEntity:
    estimated_market_value: float
    estimated_price_per_sqft: float
    is_overpriced: bool
    overpriced_percentage: float
    estimated_annual_roi_yield_pct: float
    confidence_score: float

@dataclass
class PropertyListingEntity:
    """Pure Domain Entity for a Real Estate Property Listing."""
    id: uuid.UUID
    broker_id: uuid.UUID
    title: str
    description: str
    property_category: PropertyCategory
    property_type: PropertyType
    transaction_category: TransactionCategory
    status: PropertyStatus
    price: float
    currency: str
    built_up_area_sqft: float
    bedrooms: int
    bathrooms: int
    parking_spaces: int
    project_name: Optional[str] = None
    building_name: Optional[str] = None
    unit_number: Optional[str] = None
    floor_number: Optional[int] = None
    city: str = "Dubai"
    locality: str = "Dubai Marina"
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    amenities: List[str] = field(default_factory=list)
    media: List[PropertyMediaEntity] = field(default_factory=list)
    valuation: Optional[PropertyValuationEntity] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
