"""
Canonical Customer Intelligence Domain Schemas
==============================================
Pydantic v2 schemas for Customer Identity, Requirements, Conversation,
and Bounded Multi-Tier Memory Foundation (Part 1 of 8).
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ─── 1. Identity Resolution Schemas ──────────────────────────────────────────

class IdentityResolutionRequest(BaseModel):
    phone: Optional[str] = Field(None, description="Phone number (E.164 or national format)")
    email: Optional[str] = Field(None, description="Email address")
    lead_id: Optional[str] = Field(None, description="Existing Lead / Customer UUID")
    name: Optional[str] = Field(None, description="Full or partial customer name")


class IdentityResolutionResponse(BaseModel):
    match_status: str = Field(..., description="EXACT_MATCH | POSSIBLE_MATCH | NO_MATCH")
    confidence: float = Field(..., ge=0.0, le=1.0)
    customer_id: Optional[str] = Field(None, description="UUID of the matched customer Lead")
    identity_id: Optional[str] = Field(None, description="Underlying permanent identity node UUID")
    matched_by: Optional[str] = Field(None, description="phone | email | lead_id | candidate_similarity")
    candidate_details: Optional[Dict[str, Any]] = None
    explanation: str


# ─── 2. Customer Identity Schemas ────────────────────────────────────────────

class CustomerCreateDTO(BaseModel):
    phone: str = Field(..., min_length=5, max_length=25)
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    source: str = Field("manual", max_length=50)
    transaction_type: Optional[str] = Field(None, description="buy | rent | lease")
    budget_min: Optional[int] = Field(None, ge=0)
    budget_max: Optional[int] = Field(None, ge=0)
    budget_currency: Optional[str] = Field("INR", max_length=10)
    property_type: Optional[str] = Field(None, max_length=50)
    preferred_locations: List[str] = Field(default_factory=list)
    timeline: Optional[str] = Field(None, max_length=50)
    loan_status: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class CustomerUpdateDTO(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    pipeline_stage: Optional[str] = None


class CustomerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    customer_id: str
    organization_id: str
    name: Optional[str] = None
    phone: str
    email: Optional[str] = None
    source: str
    status: str
    pipeline_stage: str
    score: str
    score_confidence: float
    transaction_type: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    budget_currency: str = "INR"
    property_type: Optional[str] = None
    preferred_locations: List[str] = Field(default_factory=list)
    timeline: Optional[str] = None
    loan_status: Optional[str] = None
    country_code: Optional[str] = None
    locale: Optional[str] = None
    last_message_at: Optional[str] = None
    qualified_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


# ─── 3. Customer Requirement Profile & Preferences ────────────────────────────

class RequirementAttributeDTO(BaseModel):
    field_name: str
    value: Any
    provenance: str = Field("EXPLICIT", description="EXPLICIT | CRM | IMPORTED | SYSTEM | INFERRED")
    confidence: float = Field(1.0, ge=0.0, le=1.0)
    updated_at: Optional[str] = None


class NegativePreferenceDTO(BaseModel):
    key: str
    description: str
    provenance: str = "EXPLICIT"
    confidence: float = 1.0


class RequirementProfileDTO(BaseModel):
    customer_id: str
    transaction_type: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    currency: str = "INR"
    locations: List[str] = Field(default_factory=list)
    property_types: List[str] = Field(default_factory=list)
    bhk: List[Any] = Field(default_factory=list)
    area_min: Optional[float] = None
    area_max: Optional[float] = None
    amenities: List[str] = Field(default_factory=list)
    furnishing: Optional[str] = None
    possession_preference: Optional[str] = None
    timeline: Optional[str] = None
    purpose: Optional[str] = None
    financing_required: Optional[str] = None
    urgency: Optional[str] = None
    positive_preferences: List[Dict[str, Any]] = Field(default_factory=list)
    negative_preferences: List[Dict[str, Any]] = Field(default_factory=list)
    provenance_map: Dict[str, str] = Field(default_factory=dict)
    last_updated_at: Optional[str] = None


class RequirementUpdateDTO(BaseModel):
    transaction_type: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    currency: Optional[str] = None
    locations: Optional[List[str]] = None
    property_types: Optional[List[str]] = None
    bhk: Optional[List[Any]] = None
    area_min: Optional[float] = None
    area_max: Optional[float] = None
    amenities: Optional[List[str]] = None
    furnishing: Optional[str] = None
    possession_preference: Optional[str] = None
    timeline: Optional[str] = None
    purpose: Optional[str] = None
    financing_required: Optional[str] = None
    urgency: Optional[str] = None
    positive_preferences: Optional[List[Dict[str, Any]]] = None
    negative_preferences: Optional[List[str]] = None
    source: str = Field("EXPLICIT", description="EXPLICIT | CRM | IMPORTED | SYSTEM | INFERRED")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


# ─── 4. Conversation Domain Schemas ──────────────────────────────────────────

class ConversationCreateDTO(BaseModel):
    channel: str = Field("whatsapp", description="whatsapp | telegram | email | webchat | sms")
    control_mode: str = Field("ai", description="ai | human | bot | paused")
    status: str = Field("ACTIVE", description="ACTIVE | WAITING | HANDED_OFF | CLOSED | ARCHIVED")
    metadata: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    customer_id: str
    status: str
    channel: str
    control_mode: str
    total_messages: int = 0
    unread_count: int = 0
    last_message_at: Optional[str] = None
    last_message_preview: Optional[str] = None
    created_at: str
    updated_at: str


# ─── 5. Message Domain Schemas ───────────────────────────────────────────────

class MessageCreateDTO(BaseModel):
    sender_type: str = Field(..., description="CUSTOMER | AI_AGENT | HUMAN_AGENT | SYSTEM")
    content: str = Field(..., min_length=1)
    channel: Optional[str] = None
    message_type: str = Field("text", description="text | image | document | location")
    metadata: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    conversation_id: str
    customer_id: str
    organization_id: str
    sender_type: str
    direction: str
    content: str
    message_type: str = "text"
    delivery_status: str = "delivered"
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


# ─── 6. Bounded Memory Schemas ───────────────────────────────────────────────

class BoundedMemoryContextResponse(BaseModel):
    customer_id: str
    conversation_id: Optional[str] = None
    current_turn: Optional[Dict[str, Any]] = None
    current_session: Dict[str, Any] = Field(default_factory=dict)
    customer_memory: Dict[str, Any] = Field(default_factory=dict)
    crm_memory: Dict[str, Any] = Field(default_factory=dict)
    formatted_prompt_context: str
