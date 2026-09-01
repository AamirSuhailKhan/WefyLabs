"""
Part 21.5 — AI Sales Action & Follow-Up DTOs
=============================================
Pydantic v2 schemas for strongly-typed action decisions, human sales briefs,
execution results, and follow-up states.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict

from app.modules.sales_action.taxonomies import (
    SalesActionType,
    SalesActionStatus,
    CommunicationChannel,
    ConsentStatus,
    HandoffReason,
)


class SalesBriefDTO(BaseModel):
    """Structured brief for human broker handoffs derived from verified CRM facts."""
    model_config = ConfigDict(from_attributes=True)

    lead_id: str
    lead_name: str
    lead_intent: str = "UNKNOWN"
    budget_range: str = "Not Specified"
    preferred_location: str = "Not Specified"
    property_type: str = "Not Specified"
    timeline: str = "Not Specified"
    financing: str = "Not Specified"
    matched_properties_count: int = 0
    handoff_reason: str
    recent_conversation_summary: str
    recommended_human_action: str


class SalesActionDecisionDTO(BaseModel):
    """Immutable, strongly-typed sales action decision."""
    model_config = ConfigDict(from_attributes=True)

    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    lead_id: str
    organization_id: str
    action_type: SalesActionType
    status: SalesActionStatus
    reason: str
    priority: float = Field(default=50.0, ge=0.0, le=100.0)
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    recommended_channel: CommunicationChannel = CommunicationChannel.WHATSAPP
    automation_allowed: bool = False
    human_approval_required: bool = False
    blocked_reason: Optional[str] = None
    scheduled_for_utc: Optional[datetime] = None
    customer_timezone: str = "UTC"
    required_facts: List[str] = Field(default_factory=list)
    matched_properties_count: int = 0
    matched_properties_summary: Optional[List[Dict[str, Any]]] = None
    draft_message_body: Optional[str] = None
    draft_message_subject: Optional[str] = None
    sales_brief: Optional[SalesBriefDTO] = None
    source_evidence: Dict[str, Any] = Field(default_factory=dict)
    policy_version: str = "v1.0-sales-action"
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    next_evaluation_at: Optional[datetime] = None


class SalesActionExecutionResultDTO(BaseModel):
    """Result of an executed sales action."""
    model_config = ConfigDict(from_attributes=True)

    action_id: str
    lead_id: str
    organization_id: str
    action_type: SalesActionType
    status: SalesActionStatus
    channel: str
    provider: str
    provider_message_id: Optional[str] = None
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict[str, Any] = Field(default_factory=dict)


class FollowUpStateDTO(BaseModel):
    """Real-time follow-up state, fatigue, and suppression tracking."""
    model_config = ConfigDict(from_attributes=True)

    lead_id: str
    organization_id: str
    is_paused: bool = False
    is_dormant: bool = False
    is_suppressed: bool = False
    suppression_reason: Optional[str] = None
    fatigue_score: float = 0.0
    consecutive_no_replies: int = 0
    total_messages_sent: int = 0
    last_contacted_at: Optional[datetime] = None
    last_responded_at: Optional[datetime] = None
    active_scheduled_actions: List[Dict[str, Any]] = Field(default_factory=list)


class EvaluateSalesActionRequestDTO(BaseModel):
    """Request payload for manual or webhook-triggered sales action evaluation."""
    trigger_event: Optional[str] = None
    target_property_id: Optional[str] = None
    force_refresh: bool = False


class ApproveSalesActionRequestDTO(BaseModel):
    """Request payload to approve a pending sales action."""
    custom_message_body: Optional[str] = None
    scheduled_for_utc: Optional[datetime] = None
