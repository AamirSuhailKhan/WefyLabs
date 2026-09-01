"""
Part 21.7 — AI Conversation Intelligence DTOs
=============================================
Typed Pydantic & dataclass schemas for inbound response understanding,
signal detection, objection tracking, qualification updates, and human handoff.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, ConfigDict

from app.modules.conversation_intelligence.taxonomies import (
    CustomerIntent,
    BuyingSignalLevel,
    BuyingSignalIndicator,
    ObjectionCategory,
    ObjectionSeverity,
    AppointmentIntentType,
    NegotiationDirection,
    HandoffTrigger,
)


class InboundCustomerMessage(BaseModel):
    """Canonical normalized inbound customer communication."""
    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    lead_id: str
    conversation_id: Optional[str] = None
    channel: str = Field(description="whatsapp | email | sms | webchat | telegram")
    provider_message_id: str
    message_id: Optional[str] = None
    message_type: str = "text"
    text: str
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider_timestamp: Optional[datetime] = None
    sender_identifier: str
    sender_name: Optional[str] = None
    reply_to_message_id: Optional[str] = None
    attachments_metadata: List[Dict[str, Any]] = Field(default_factory=list)
    language: Optional[str] = None
    idempotency_key: str


class ExtractedIntentDTO(BaseModel):
    """Specific intent classified with confidence and grounded evidence."""
    intent: CustomerIntent
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: Optional[str] = None


class BuyingSignalDTO(BaseModel):
    """Structured buying signal evaluation."""
    level: BuyingSignalLevel
    indicators: List[BuyingSignalIndicator] = Field(default_factory=list)
    evidence: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ObjectionDTO(BaseModel):
    """Structured customer objection."""
    category: ObjectionCategory
    severity: ObjectionSeverity
    evidence: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_message_id: Optional[str] = None
    is_resolved: bool = False
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class NegotiationSignalDTO(BaseModel):
    """Price negotiation and discount intent."""
    is_negotiating: bool = False
    direction: NegotiationDirection = NegotiationDirection.NONE
    requested_price: Optional[Decimal] = None
    offered_price: Optional[Decimal] = None
    currency: Optional[str] = "AED"
    discount_percentage: Optional[float] = None
    evidence: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    requires_human_approval: bool = False


class AppointmentIntentDTO(BaseModel):
    """Viewing and meeting schedule intent."""
    intent_type: AppointmentIntentType = AppointmentIntentType.NONE
    preferred_date: Optional[str] = None
    preferred_time: Optional[str] = None
    timezone: Optional[str] = None
    location_preference: Optional[str] = None
    evidence: Optional[str] = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    calendar_verified: bool = False


class ExtractedQualificationUpdateDTO(BaseModel):
    """Qualification facts extracted from customer response."""
    intent: Optional[str] = None
    buyer_type: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    location: Optional[str] = None
    budget_min: Optional[Decimal] = None
    budget_max: Optional[Decimal] = None
    budget_currency: Optional[str] = "AED"
    timeline: Optional[str] = None
    financing: Optional[str] = None
    evidence_quotes: Dict[str, str] = Field(default_factory=dict)
    confidences: Dict[str, float] = Field(default_factory=dict)


class PropertyRequirementUpdateDTO(BaseModel):
    """Explicit property search requirement changes."""
    has_changes: bool = False
    location: Optional[str] = None
    budget_max: Optional[Decimal] = None
    bedrooms: Optional[int] = None
    property_type: Optional[str] = None
    currency: Optional[str] = "AED"
    evidence: Optional[str] = None


class HumanHandoffBriefDTO(BaseModel):
    """Structured brief provided to the broker when human handoff is required."""
    lead_id: str
    organization_id: str
    trigger: HandoffTrigger
    urgency: str = "HIGH"
    summary: str
    customer_message: str
    detected_intents: List[CustomerIntent] = Field(default_factory=list)
    buying_signal: BuyingSignalDTO
    objections: List[ObjectionDTO] = Field(default_factory=list)
    qualification_changes: Optional[Dict[str, Any]] = None
    property_requirement_changes: Optional[Dict[str, Any]] = None
    recommended_action: str
    evidence: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ResponseAnalysisResultDTO(BaseModel):
    """Complete intelligence analysis output for an inbound message."""
    lead_id: str
    organization_id: str
    message_id: Optional[str] = None
    detected_language: str = "en"
    intents: List[ExtractedIntentDTO] = Field(default_factory=list)
    buying_signal: BuyingSignalDTO
    objections: List[ObjectionDTO] = Field(default_factory=list)
    negotiation: NegotiationSignalDTO
    appointment: AppointmentIntentDTO
    qualification_update: ExtractedQualificationUpdateDTO
    property_requirement_update: PropertyRequirementUpdateDTO
    opt_out_detected: bool = False
    requires_human_handoff: bool = False
    handoff_brief: Optional[HumanHandoffBriefDTO] = None
    next_best_action_suggested: Optional[str] = None
    draft_response: Optional[str] = None
    processing_latency_ms: int = 0
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DraftReplyRequestDTO(BaseModel):
    """Request to generate a grounded draft reply."""
    custom_instructions: Optional[str] = None
    language: Optional[str] = None


class DraftReplyResponseDTO(BaseModel):
    """Fact-grounded draft reply ready for broker review."""
    lead_id: str
    draft_body: str
    language: str
    channel: str
    grounding_facts_used: List[str] = Field(default_factory=list)
    properties_referenced: List[Dict[str, Any]] = Field(default_factory=list)
    human_approval_required: bool = False
    warning_notes: Optional[str] = None


class ApproveDraftReplyRequestDTO(BaseModel):
    """Request to approve and immediately dispatch or queue an AI draft reply."""
    approved_message_body: str
    channel: Optional[str] = None
