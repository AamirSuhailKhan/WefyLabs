"""
Canonical Property Intelligence DTOs, Enums, and Contracts
==========================================================
Establishes the authoritative data models for:
- Property Fact Pack (structured AI context)
- Truth & Grounded Retrieval Contracts
- Missing Data Semantics
- Source Precedence & Trust Levels
- Question Classification
- Tenant-Scoped Search & Knowledge DTOs
"""
from __future__ import annotations

from enum import Enum, IntEnum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ─── 1. Core Enums ────────────────────────────────────────────────────────────

class SourceTrustLevel(IntEnum):
    """
    Hierarchical authority rank for property information sources.
    Higher integer = strictly higher authority.
    AI must never supersede structured database records with document claims.
    """
    LIVE_STRUCTURED_INVENTORY = 100   # PropertyListing in DB (authoritative)
    APPROVED_PROPERTY_DOCUMENT = 85   # Verified brochure / rate card signed off by broker
    CURRENT_APPROVED_DOCUMENT = 75    # Current uploaded document in published status
    OLDER_DOCUMENT = 60               # Historical version / outdated brochure
    INTERNAL_NOTE = 50                # Agent / broker internal CRM note
    UNVERIFIED_EXTERNAL_CONTENT = 20  # Scraped web content or unverified external source


class MissingDataReason(str, Enum):
    """
    Explicit missing data semantics preventing AI guessing or hallucinating facts.
    """
    UNKNOWN = "UNKNOWN"               # Not known to the system
    NOT_PROVIDED = "NOT_PROVIDED"     # Field was omitted during listing creation
    NOT_APPLICABLE = "NOT_APPLICABLE" # Not relevant for this property type (e.g. floor for a plot)
    NOT_AVAILABLE = "NOT_AVAILABLE"   # Currently unavailable / restricted
    PRIVATE = "PRIVATE"               # Internal broker data hidden from customer actor
    STALE = "STALE"                   # Fact is past freshness expiration threshold


class QuestionClassification(str, Enum):
    """
    Deterministic classification for incoming property-related inquiries.
    """
    STRUCTURED_FACT = "STRUCTURED_FACT"   # Price, BHK, area, location, possession, floor
    KNOWLEDGE_FACT = "KNOWLEDGE_FACT"     # Project background, brochure details, developer bio
    AVAILABILITY = "AVAILABILITY"         # Is it available, sold, reserved?
    COMPARISON = "COMPARISON"             # How does property A compare with property B?
    MATCHING = "MATCHING"                 # Show me similar properties in my budget
    APPOINTMENT = "APPOINTMENT"           # Can I visit the site tomorrow?
    UNKNOWN = "UNKNOWN"                   # Unclassified / generic question


class PropertyLifecycleStatus(str, Enum):
    """
    Standard property inventory status lifecycle.
    """
    AVAILABLE = "available"
    UNDER_OFFER = "under_offer"
    RESERVED = "reserved"
    SOLD = "sold"
    RENTED = "rented"
    OFF_MARKET = "off_market"
    DRAFT = "draft"
    ARCHIVED = "archived"


# ─── 2. Internal / Segregated Data ────────────────────────────────────────────

class InternalBrokerPropertyData(BaseModel):
    """
    Strictly internal broker information.
    NEVER exposed to customer actors or customer-facing AI context.
    """
    model_config = ConfigDict(from_attributes=True)

    owner_name: Optional[str] = None
    owner_phone: Optional[str] = None
    owner_email: Optional[str] = None
    commission_amount: Optional[float] = None
    commission_percentage: Optional[float] = None
    internal_notes: Optional[str] = None
    assigned_agent_id: Optional[str] = None


# ─── 3. Property Fact Pack (Canonical AI Context) ─────────────────────────────

class PropertyFactPack(BaseModel):
    """
    Authoritative, machine-usable Property Fact Pack.
    The single standardized context object consumed by the future AI Sales Agent.
    """
    model_config = ConfigDict(from_attributes=True)

    property_id: str
    property_code: Optional[str] = None
    title: str
    description: str

    property_category: str = "residential"
    property_type: str = "apartment"
    transaction_category: str = "resale"
    status: str = "available"
    is_available: bool = True

    # Pricing
    price: float
    currency: str = "INR"
    price_per_sqft: Optional[float] = None

    # Specifications
    area_value: float
    area_unit: str = "sqft"
    bedrooms: int = 1
    bathrooms: int = 1
    balconies: int = 0
    parking_spaces: int = 1
    floor_number: Optional[int] = None
    total_floors: Optional[int] = None
    facing: Optional[str] = None
    furnishing: str = "unfurnished"
    construction_status: str = "ready_to_move"
    possession_date: Optional[str] = None

    # Project & Location
    developer_name: Optional[str] = None
    project_name: Optional[str] = None
    locality: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None

    # Amenities & Highlights
    amenities: List[str] = Field(default_factory=list)
    marketing_highlights: List[str] = Field(default_factory=list)
    public_media_urls: List[str] = Field(default_factory=list)

    # Authority & Provenance
    verified_source: str = "LIVE_STRUCTURED_INVENTORY"
    source_trust_level: int = SourceTrustLevel.LIVE_STRUCTURED_INVENTORY
    last_updated_at: Optional[str] = None

    # Explicit Missing Data Map
    missing_fields: Dict[str, str] = Field(default_factory=dict)


# ─── 4. Property Truth Response ───────────────────────────────────────────────

class PropertyTruthResponse(BaseModel):
    """
    Response returned by `get_property_truth`.
    Enforces customer vs broker visibility boundary.
    """
    model_config = ConfigDict(from_attributes=True)

    property_id: str
    tenant_id: str
    fact_pack: PropertyFactPack
    source_trust_level: int = SourceTrustLevel.LIVE_STRUCTURED_INVENTORY
    source_authority: str = "PropertyListing (DB Primary)"
    is_customer_safe: bool = True
    internal_data: Optional[InternalBrokerPropertyData] = None
    missing_fields: Dict[str, str] = Field(default_factory=dict)
    conflicts_detected: List[str] = Field(default_factory=list)


# ─── 5. Search Criteria & Results ─────────────────────────────────────────────

class PropertySearchCriteria(BaseModel):
    """
    Structured search criteria executed deterministically WITHOUT Gemini.
    """
    city: Optional[str] = None
    locality: Optional[str] = None
    property_type: Optional[str] = None
    property_category: Optional[str] = None
    transaction_category: Optional[str] = None
    status: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    min_area: Optional[float] = None
    max_area: Optional[float] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    furnishing: Optional[str] = None
    construction_status: Optional[str] = None
    amenities: Optional[List[str]] = None
    query: Optional[str] = None
    sort_by: str = "newest"  # newest | price_asc | price_desc | area_asc | area_desc
    page: int = Field(1, ge=1)
    limit: int = Field(20, ge=1, le=100)


class PropertySearchResultItem(BaseModel):
    """
    Compact search result item for efficient payload and bounded AI token budgeting.
    """
    model_config = ConfigDict(from_attributes=True)

    property_id: str
    property_code: Optional[str] = None
    title: str
    property_type: str
    bedrooms: int
    bathrooms: int
    price: float
    currency: str
    area_value: float
    area_unit: str
    locality: Optional[str] = None
    city: Optional[str] = None
    status: str
    is_available: bool
    construction_status: str
    amenities: List[str] = Field(default_factory=list)
    primary_image_url: Optional[str] = None
    last_updated_at: Optional[str] = None


class PropertySearchResponse(BaseModel):
    """
    Paginated search response.
    """
    total: int
    page: int
    limit: int
    items: List[PropertySearchResultItem]


# ─── 6. Knowledge & Citations ─────────────────────────────────────────────────

class PropertyKnowledgeQuery(BaseModel):
    """
    Query for approved property knowledge and document chunks.
    """
    query: str = Field(..., min_length=1, description="Question or keyword to search in property knowledge")
    max_chunks: int = Field(5, ge=1, le=20)


class PropertyCitation(BaseModel):
    """
    Source citation preserving full provenance for every retrieved knowledge chunk.
    """
    citation_index: int
    document_id: str
    chunk_id: Optional[str] = None
    source_title: str
    page_number: Optional[int] = None
    heading: Optional[str] = None
    section: Optional[str] = None
    cited_text: Optional[str] = None
    trust_level: int = SourceTrustLevel.APPROVED_PROPERTY_DOCUMENT
    source_type: str = "document"


class PropertyKnowledgeResponse(BaseModel):
    """
    Grounded property knowledge response with provenance and prompt injection defense.
    """
    property_id: str
    tenant_id: str
    query: str
    context_block: str
    citations: List[PropertyCitation]
    confidence: float
    is_customer_safe: bool = True
    untrusted_data_boundary_enforced: bool = True


# ─── 7. Conflict Detection ────────────────────────────────────────────────────

class ConflictDetectionResult(BaseModel):
    """
    Report on conflicting claims between documents/external data and authoritative DB truth.
    """
    property_id: str
    field_name: str
    canonical_db_value: Any
    incoming_value: Any
    canonical_source: str = "LIVE_STRUCTURED_INVENTORY"
    incoming_source: str
    resolved_value: Any
    resolution_rule: str
    is_conflict: bool = False
    warning_message: Optional[str] = None


# ─── 8. Question Classification Request / Response ────────────────────────────

class QuestionClassificationRequest(BaseModel):
    query: str = Field(..., min_length=1)


class QuestionClassificationResponse(BaseModel):
    query: str
    classification: QuestionClassification
    confidence: float
    suggested_retrieval_mode: str  # structured | knowledge | availability | hybrid | none
