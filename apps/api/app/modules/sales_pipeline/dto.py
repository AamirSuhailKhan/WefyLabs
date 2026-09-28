"""
Build 08 — Sales Pipeline DTOs / Schemas
========================================
Pydantic v2 schemas for the canonical sales pipeline OS:
  - Pipeline & Stage configurations
  - Opportunity lifecycle & stage transitions
  - Property shortlists & interest tracking
  - Site visit state machine & outcomes
  - Negotiation rounds & human approval
  - Booking intents & unit holds
  - Reconciliation tasks & revenue events
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ─────────────────────────────────────────────────────────────────────────────
# 1. Pipeline & Stages
# ─────────────────────────────────────────────────────────────────────────────

class PipelineCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    pipeline_type: str = Field("standard", max_length=64)
    description: Optional[str] = None
    is_default: bool = False
    stages: Optional[List[Dict[str, Any]]] = None


class StageConfigResponse(BaseModel):
    id: str
    pipeline_id: str
    stage_key: str
    display_name: str
    order_index: int
    probability_weight: float
    requires_approval: bool
    requires_evidence: bool
    is_terminal: bool
    terminal_type: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class PipelineResponse(BaseModel):
    id: str
    organization_id: str
    name: str
    pipeline_type: str
    is_default: bool
    is_active: bool
    description: Optional[str] = None
    created_at: datetime
    stages: Optional[List[StageConfigResponse]] = None
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Opportunities & Stage Advances
# ─────────────────────────────────────────────────────────────────────────────

class OpportunityCreateRequest(BaseModel):
    lead_id: str
    deal_title: str = Field(..., min_length=2, max_length=255)
    property_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    currency: str = Field("AED", max_length=3)
    target_budget: Optional[Decimal] = None
    idempotency_key: Optional[str] = None


class OpportunityStageAdvanceRequest(BaseModel):
    target_stage: str = Field(..., min_length=1, max_length=64)
    evidence: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None
    idempotency_key: Optional[str] = None


class OpportunityLostRequest(BaseModel):
    lost_reason: str = Field(..., min_length=1, max_length=64)
    competitor_name: Optional[str] = None
    details: Optional[str] = None
    idempotency_key: Optional[str] = None


class OpportunityStageHistoryResponse(BaseModel):
    id: str
    opportunity_id: str
    from_stage: Optional[str] = None
    to_stage: str
    transitioned_by: Optional[str] = None
    transition_reason: Optional[str] = None
    lost_reason: Optional[str] = None
    evidence_payload: Optional[Dict[str, Any]] = None
    snapshot_state: Optional[Dict[str, Any]] = None
    transitioned_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Property Shortlist
# ─────────────────────────────────────────────────────────────────────────────

class ShortlistAddRequest(BaseModel):
    property_id: str
    interest_level: str = Field("interested", max_length=32)
    client_reaction: Optional[str] = None
    is_primary: bool = False
    notes: Optional[str] = None


class ShortlistUpdateRequest(BaseModel):
    status: str = Field(..., max_length=32)
    reason: Optional[str] = None


class ShortlistResponse(BaseModel):
    id: str
    opportunity_id: str
    property_id: str
    status: str
    interest_level: str
    client_reaction: Optional[str] = None
    is_primary: bool
    dismissal_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Site Visits
# ─────────────────────────────────────────────────────────────────────────────

class SiteVisitCreateRequest(BaseModel):
    property_id: str
    scheduled_start: datetime
    scheduled_end: datetime
    assigned_broker_id: Optional[str] = None
    location_address: Optional[str] = None
    access_instructions: Optional[str] = None
    special_requests: Optional[str] = None
    idempotency_key: Optional[str] = None


class SiteVisitStatusUpdateRequest(BaseModel):
    status: str = Field(..., max_length=32)
    cancellation_reason: Optional[str] = None
    notes: Optional[str] = None


class SiteVisitOutcomeRequest(BaseModel):
    outcome: str = Field(..., max_length=32)
    sentiment: Optional[str] = Field(None, max_length=32)
    client_feedback: Optional[str] = None
    next_action: Optional[str] = None
    agent_notes: Optional[str] = None
    follow_up_scheduled: Optional[datetime] = None


class SiteVisitResponse(BaseModel):
    id: str
    organization_id: str
    opportunity_id: str
    property_id: str
    visit_number: int
    status: str
    outcome: Optional[str] = None
    scheduled_start: datetime
    scheduled_end: datetime
    assigned_broker_id: Optional[str] = None
    location_address: Optional[str] = None
    client_feedback: Optional[str] = None
    sentiment: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# 5. Negotiation & Offers
# ─────────────────────────────────────────────────────────────────────────────

class NegotiationRoundRequest(BaseModel):
    offered_price: Decimal
    currency: str = Field("AED", max_length=3)
    round_number: Optional[int] = None
    actor: str = Field("buyer", max_length=32)
    payment_terms: Optional[str] = None
    inclusions: Optional[List[str]] = None
    valid_until: Optional[datetime] = None
    counter_proposal: Optional[str] = None
    ai_generated: bool = False
    idempotency_key: Optional[str] = None


class NegotiationRoundResponse(BaseModel):
    id: str
    opportunity_id: str
    round_number: int
    actor: str
    offered_price: Decimal
    currency: str
    payment_terms: Optional[str] = None
    inclusions: Optional[List[str]] = None
    ai_generated: bool
    requires_approval: bool
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    status: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# 6. Booking Intent & Unit Holds
# ─────────────────────────────────────────────────────────────────────────────

class BookingIntentCreateRequest(BaseModel):
    property_id: str
    unit_id: Optional[str] = None
    agreed_price: Decimal
    deposit_amount: Decimal
    currency: str = Field("AED", max_length=3)
    ttl_hours: int = Field(48, ge=1, le=720)
    customer_national_id: Optional[str] = None
    idempotency_key: Optional[str] = None


class BookingIntentResponse(BaseModel):
    id: str
    organization_id: str
    opportunity_id: str
    property_id: str
    unit_id: Optional[str] = None
    agreed_price: Decimal
    deposit_amount: Decimal
    currency: str
    status: str
    expires_at: datetime
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class UnitHoldCreateRequest(BaseModel):
    property_id: str
    unit_id: Optional[str] = None
    ttl_minutes: int = Field(120, ge=5, le=43200)
    idempotency_key: Optional[str] = None


class UnitHoldResponse(BaseModel):
    id: str
    organization_id: str
    opportunity_id: str
    property_id: str
    unit_id: Optional[str] = None
    status: str
    expires_at: datetime
    released_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# 7. Reconciliation & Revenue Events
# ─────────────────────────────────────────────────────────────────────────────

class ReconciliationResolveRequest(BaseModel):
    resolution_notes: str = Field(..., min_length=2)


class ReconciliationTaskResponse(BaseModel):
    id: str
    organization_id: str
    opportunity_id: Optional[str] = None
    issue_type: str
    description: str
    status: str
    resolution_notes: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class RevenueEventResponse(BaseModel):
    id: str
    organization_id: str
    opportunity_id: Optional[str] = None
    site_visit_id: Optional[str] = None
    booking_intent_id: Optional[str] = None
    event_type: str
    amount: Optional[Decimal] = None
    currency: Optional[str] = None
    payload: Dict[str, Any]
    recorded_at: datetime
    model_config = ConfigDict(from_attributes=True)
