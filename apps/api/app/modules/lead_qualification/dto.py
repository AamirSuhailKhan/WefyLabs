"""
Part 21.4.1 — AI Lead Qualification Strongly Typed DTOs
======================================================
Pydantic v2 schemas for all qualification domain interactions:
- Facts (create, response, history)
- Conflicts (detection, resolution)
- Requirement Policies (rules, thresholds)
- Snapshots (state, completeness, confidence, provenance)
- Audit Trail (events, actors, reasons)
- Human Overrides (RBAC, justifications)
"""
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.models.qualification_models import (
    QualificationState,
    QualificationIntent,
    QualificationBuyerType,
    QualificationTimeline,
    QualificationFinancing,
    FactValueCategory,
    EvidenceSourceType,
    FactStatus,
    ConflictStatus,
    QualificationAuditActorType,
    QualificationAuditEventType,
)


# ─── Fact DTOs ───────────────────────────────────────────────────────────────

class QualificationFactCreateDTO(BaseModel):
    """Payload to record a new atomic qualification fact."""
    field_name: str = Field(..., min_length=2, max_length=50, description="Qualification field identifier")
    raw_value: Optional[str] = Field(None, description="Original observed text/string")
    normalized_value: Optional[Any] = Field(None, description="Typed/structured value")
    value_category: FactValueCategory = Field(default=FactValueCategory.FACT)
    value_type: str = Field(default="string", description="Type: string, number, boolean, json, currency_amount, enum")
    source_type: EvidenceSourceType = Field(default=EvidenceSourceType.CUSTOMER_MESSAGE)
    source_id: Optional[str] = Field(None, description="Message ID, Conversation ID, or Source Document ID")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Evidence confidence score")
    extracted_by: Optional[str] = Field(None, description="Extracting agent, model ID, or broker ID")
    model_version: Optional[str] = Field(None, description="LLM/ML model version if applicable")
    evidence_text_reference: Optional[str] = Field(None, description="Direct quote or snippet reference")


class QualificationFactDTO(BaseModel):
    """Response DTO for an atomic qualification fact."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    lead_id: str
    field_name: str
    raw_value: Optional[str] = None
    normalized_value: Optional[Any] = None
    value_category: str
    value_type: str
    source_type: str
    source_id: Optional[str] = None
    confidence: float
    observed_at: datetime
    extracted_by: Optional[str] = None
    model_version: Optional[str] = None
    evidence_text_reference: Optional[str] = None
    status: str
    supersedes_fact_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ─── Conflict DTOs ───────────────────────────────────────────────────────────

class QualificationConflictResolveDTO(BaseModel):
    """Payload to resolve an open qualification conflict."""
    selected_fact_id: Optional[str] = Field(None, description="Fact ID chosen as authoritative")
    resolution_reason: str = Field(..., min_length=3, max_length=500, description="Justification for resolution")


class QualificationConflictDTO(BaseModel):
    """Response DTO for an evidence conflict."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    lead_id: str
    field_name: str
    existing_fact_id: Optional[str] = None
    conflicting_fact_id: Optional[str] = None
    status: str
    resolved_by: Optional[str] = None
    resolution_reason: Optional[str] = None
    resolved_fact_id: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


# ─── Requirement Policy DTOs ─────────────────────────────────────────────────

class QualificationPolicyCreateDTO(BaseModel):
    """Payload to create/configure a qualification requirement policy."""
    policy_name: str = Field(..., min_length=3, max_length=100)
    policy_version: str = Field(default="v1.0", min_length=1, max_length=20)
    country_code: Optional[str] = Field(None, max_length=10)
    market_id: Optional[str] = Field(None, max_length=36)
    transaction_type: Optional[str] = Field(None, max_length=20)
    property_type: Optional[str] = Field(None, max_length=50)
    required_fields: List[str] = Field(default_factory=lambda: ["intent", "location", "property_type"])
    recommended_fields: List[str] = Field(default_factory=lambda: ["budget_max", "timeline"])
    optional_fields: List[str] = Field(default_factory=lambda: ["financing", "bedrooms", "preferred_amenities"])
    min_completeness_for_qualified: float = Field(default=0.8, ge=0.0, le=1.0)
    min_confidence_for_qualified: float = Field(default=0.7, ge=0.0, le=1.0)
    is_active: bool = Field(default=True)


class QualificationPolicyDTO(BaseModel):
    """Response DTO for a qualification policy."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: Optional[str] = None
    policy_name: str
    policy_version: str
    country_code: Optional[str] = None
    market_id: Optional[str] = None
    transaction_type: Optional[str] = None
    property_type: Optional[str] = None
    required_fields: List[str]
    recommended_fields: List[str]
    optional_fields: List[str]
    min_completeness_for_qualified: float
    min_confidence_for_qualified: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ─── Audit Event DTOs ────────────────────────────────────────────────────────

class QualificationAuditEventDTO(BaseModel):
    """Response DTO for a qualification audit trail event."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    lead_id: str
    actor_type: str
    actor_id: Optional[str] = None
    event_type: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None
    reason: Optional[str] = None
    correlation_id: Optional[str] = None
    details_json: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


# ─── Human Override DTO ──────────────────────────────────────────────────────

class QualificationHumanOverrideDTO(BaseModel):
    """Payload for an authorized human review override."""
    target_state: QualificationState = Field(..., description="Target qualification state")
    reason: str = Field(..., min_length=5, max_length=1000, description="Mandatory audit justification")
    notes: Optional[str] = Field(None, description="Optional agent notes")


# ─── Snapshot DTOs ───────────────────────────────────────────────────────────

class QualificationSnapshotDTO(BaseModel):
    """
    Evaluated point-in-time qualification snapshot.
    Decoupled from raw evidence. Completeness and confidence are strictly separated.
    """
    model_config = ConfigDict(from_attributes=True)

    id: Optional[str] = None
    organization_id: str
    lead_id: str
    state: str
    intent: str
    buyer_type: str

    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    budget_currency: Optional[str] = None

    location: str
    property_type: str
    bedrooms: Optional[int] = None

    timeline: str
    financing: str

    completeness_score: float = Field(..., ge=0.0, le=1.0, description="0.0 - 1.0 field completeness")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="0.0 - 1.0 evidence confidence")

    missing_fields: List[str] = Field(default_factory=list)
    conflicting_fields: List[str] = Field(default_factory=list)

    policy_version: str
    summary_notes: Optional[str] = None
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Part 21.4.2 Extraction DTOs ─────────────────────────────────────────────

class ProposedQualificationFactDTO(BaseModel):
    """An individual structured fact proposed by the extraction engine."""
    field_name: str = Field(..., description="Target qualification field")
    raw_value: Optional[str] = Field(None, description="Original verbatim snippet from source")
    normalized_value: Optional[Any] = Field(None, description="Canonical normalized representation")
    value_category: FactValueCategory = Field(default=FactValueCategory.FACT)
    value_type: str = Field(default="string", description="string, number, boolean, json, currency_amount")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Calibrated confidence")
    confidence_band: str = Field(default="HIGH", description="HIGH, MEDIUM, LOW, UNKNOWN")
    source_type: EvidenceSourceType = Field(default=EvidenceSourceType.CUSTOMER_MESSAGE)
    source_id: Optional[str] = Field(None, description="Message UUID or timeline event ID")
    evidence_text_reference: Optional[str] = Field(None, description="Verbatim quote supporting this fact")


class QualificationExtractionResultDTO(BaseModel):
    """Strongly-typed container for the output of fact extraction."""
    lead_id: str
    organization_id: str
    facts: List[ProposedQualificationFactDTO] = Field(default_factory=list)
    extraction_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    model_provider: str = Field(default="google_gemini")
    model_name: str = Field(default="gemini-3.5-flash")
    extraction_version: str = Field(default="v1.0-extraction")
    source_message_id: Optional[str] = None
    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    is_safe: bool = Field(default=True, description="Prompt injection safety check status")
    rejection_reason: Optional[str] = None


class QualificationExtractRequestDTO(BaseModel):
    """Request payload for triggering qualification fact extraction."""
    message_id: Optional[str] = Field(None, description="Specific message ID to extract from")
    include_full_history: bool = Field(default=True, description="Whether to analyze full conversation history")
    force_refresh: bool = Field(default=False, description="Whether to re-extract without cache")


class QualificationExtractionSummaryDTO(BaseModel):
    """Response returned when triggering extraction."""
    lead_id: str
    organization_id: str
    facts_extracted_count: int
    facts_persisted_count: int
    conflicts_detected_count: int
    snapshot: QualificationSnapshotDTO
    extracted_facts: List[QualificationFactDTO] = Field(default_factory=list)
    open_conflicts: List[QualificationConflictDTO] = Field(default_factory=list)
    processing_time_ms: float


# ─── Part 21.4.3 Policy Evaluation & Next Best Question DTOs ─────────────────

class QualificationEvaluationResultDTO(BaseModel):
    """
    Detailed output of deterministic qualification policy evaluation.
    Contains state, separated completeness/confidence, missing items, and next best question.
    """
    model_config = ConfigDict(from_attributes=True)

    lead_id: str
    organization_id: str
    qualification_state: str
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    policy_version: str
    missing_required_information: List[str] = Field(default_factory=list)
    missing_recommended_information: List[str] = Field(default_factory=list)
    blocking_conflicts: List[str] = Field(default_factory=list)
    next_best_question_field: Optional[str] = None
    next_best_question: Optional[str] = None
    snapshot: QualificationSnapshotDTO
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QualificationMissingInfoDTO(BaseModel):
    """Response DTO for lead missing qualification information and question prompts."""
    model_config = ConfigDict(from_attributes=True)

    lead_id: str
    organization_id: str
    missing_required_fields: List[str] = Field(default_factory=list)
    missing_recommended_fields: List[str] = Field(default_factory=list)
    next_best_question_field: Optional[str] = None
    next_best_question: Optional[str] = None
    field_questions: Dict[str, str] = Field(default_factory=dict)


# ─── Part 21.4.4 Qualification Conversation Engine DTOs ──────────────────────

class QualificationConversationState(str):
    """Lifecycle state of the active qualification conversation loop."""
    IDLE = "IDLE"
    ASKING = "ASKING"
    WAITING_FOR_RESPONSE = "WAITING_FOR_RESPONSE"
    PROCESSING = "PROCESSING"
    QUALIFICATION_UPDATED = "QUALIFICATION_UPDATED"
    COMPLETED = "COMPLETED"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    BLOCKED = "BLOCKED"


class QualificationConversationStartDTO(BaseModel):
    """Request payload to initiate or resume qualification conversation."""
    channel: str = Field(default="webchat", description="Communication channel (whatsapp, webchat, sms, email)")
    force_restart: bool = Field(default=False, description="Whether to reset conversation memory")
    context_notes: Optional[str] = Field(None, description="Optional agent or CRM context")


class QualificationConversationMessageDTO(BaseModel):
    """Incoming customer response message payload."""
    message: str = Field(..., min_length=1, max_length=4000, description="Customer message text")
    channel: str = Field(default="webchat", description="Channel message was received on")
    message_id: Optional[str] = Field(None, description="Client or external message identifier")
    idempotency_key: Optional[str] = Field(None, description="Idempotency key to prevent duplicate processing")


class QualificationConversationResponseDTO(BaseModel):
    """Standardized response from the Qualification Conversation Engine."""
    model_config = ConfigDict(from_attributes=True)

    lead_id: str
    organization_id: str
    conversation_state: str
    qualification_state: str
    question: Optional[str] = None
    question_field: Optional[str] = None
    is_fallback_question: bool = False
    missing_fields: List[str] = Field(default_factory=list)
    completeness_score: float = Field(..., ge=0.0, le=1.0)
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    human_handoff: bool = False
    handoff_reason: Optional[str] = None
    extracted_facts_count: int = 0
    extracted_facts_summary: Dict[str, Any] = Field(default_factory=dict)
    matched_properties_summary: Optional[Dict[str, Any]] = None
    processed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QualificationConversationStateDTO(BaseModel):
    """Current state and history summary of lead qualification conversation."""
    model_config = ConfigDict(from_attributes=True)

    lead_id: str
    organization_id: str
    conversation_state: str
    qualification_state: str
    current_question: Optional[str] = None
    current_question_field: Optional[str] = None
    missing_required_fields: List[str] = Field(default_factory=list)
    missing_recommended_fields: List[str] = Field(default_factory=list)
    completeness_score: float
    confidence_score: float
    human_handoff: bool
    handoff_reason: Optional[str] = None
    previously_asked_fields: List[str] = Field(default_factory=list)
    field_attempts: Dict[str, int] = Field(default_factory=dict)
    total_turns: int = 0
    last_interaction_at: Optional[datetime] = None



