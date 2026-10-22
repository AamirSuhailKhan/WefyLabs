"""
Part 18 — Deal OS DTOs / Schemas
=================================
Pydantic v2 request/response schemas for the full deal lifecycle:
  Deal, Offer, Reservation, Booking, Commission, Closing, Post-Sale
"""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, model_validator


# ─────────────────────────────────────────────────────────────────────────────
# Deal creation / summary
# ─────────────────────────────────────────────────────────────────────────────

class DealCreateRequest(BaseModel):
    lead_id: str
    property_id: Optional[str] = None
    deal_title: str = Field(..., min_length=2, max_length=255)
    current_stage: str = Field("opportunity", max_length=30)
    agreed_price: Optional[Decimal] = None
    currency: str = Field("AED", max_length=3)
    commission_percentage: Optional[Decimal] = Field(None, ge=0, le=100)
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None


class DealStageAdvanceRequest(BaseModel):
    target_stage: str = Field(..., min_length=1, max_length=30)
    reason: Optional[str] = None


class DealSummaryResponse(BaseModel):
    id: str
    organization_id: str
    broker_id: str
    lead_id: str
    lead_name: Optional[str] = None
    lead_phone: Optional[str] = None
    property_id: Optional[str] = None
    property_title: Optional[str] = None
    deal_reference: str
    deal_title: str
    current_stage: str
    previous_stage: Optional[str] = None
    status: str
    agreed_price: Optional[float] = None
    offer_price: Optional[float] = None
    final_transaction_price: Optional[float] = None
    currency: str = "AED"
    commission_percentage: Optional[float] = None
    commission_amount: Optional[float] = None
    closing_probability_pct: float
    risk_level: str
    has_offer: bool = False
    has_reservation: bool = False
    has_booking: bool = False
    has_commission: bool = False
    has_closing: bool = False
    tags: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DealDetailResponse(DealSummaryResponse):
    notes: Optional[str] = None
    risk_factors: List[str] = Field(default_factory=list)
    stage_history: List[Dict[str, Any]] = Field(default_factory=list)
    offer: Optional[Dict[str, Any]] = None
    reservation: Optional[Dict[str, Any]] = None
    booking: Optional[Dict[str, Any]] = None
    commission: Optional[Dict[str, Any]] = None
    closing: Optional[Dict[str, Any]] = None
    post_sale: Optional[Dict[str, Any]] = None
    documents: List[Dict[str, Any]] = Field(default_factory=list)
    pending_approvals: List[Dict[str, Any]] = Field(default_factory=list)
    commercial_audit: List[Dict[str, Any]] = Field(default_factory=list)
    ai_recommendations: List[str] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Offer
# ─────────────────────────────────────────────────────────────────────────────

class OfferSubmitRequest(BaseModel):
    offer_price: Decimal = Field(..., gt=0)
    currency: str = Field("AED", max_length=3)
    listing_price: Optional[Decimal] = None
    payment_plan: Optional[str] = None
    token_amount: Optional[Decimal] = None
    valid_until: Optional[datetime] = None
    possession_date_requested: Optional[datetime] = None
    special_conditions: Optional[str] = None


class OfferResponseRequest(BaseModel):
    """Accept, reject, or counter an offer."""
    action: str = Field(..., pattern="^(ACCEPT|REJECT|COUNTER)$")
    counter_offer_price: Optional[Decimal] = None
    rejection_reason: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Reservation
# ─────────────────────────────────────────────────────────────────────────────

class ReservationCreateRequest(BaseModel):
    reservation_amount: Optional[Decimal] = None
    currency: str = Field("AED", max_length=3)
    reserved_price: Optional[Decimal] = None
    expires_at: Optional[datetime] = None
    reservation_form_url: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None
    reservation_notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Booking
# ─────────────────────────────────────────────────────────────────────────────

class BookingConfirmRequest(BaseModel):
    """
    Confirms a booking. Creates a DealApprovalRequest for human gating
    before the booking becomes irreversible.
    """
    booked_price: Decimal = Field(..., gt=0)
    currency: str = Field("AED", max_length=3)
    token_amount: Optional[Decimal] = None
    token_payment_mode: Optional[str] = None
    payment_plan_type: Optional[str] = None
    down_payment_amount: Optional[Decimal] = None
    down_payment_due_at: Optional[datetime] = None
    booking_form_url: Optional[str] = None
    idempotency_key: str  # Required for irreversible actions


class BookingApproveRequest(BaseModel):
    approval_id: str
    review_notes: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Commission
# ─────────────────────────────────────────────────────────────────────────────

class CommissionRecordRequest(BaseModel):
    transaction_price: Decimal = Field(..., gt=0)
    currency: str = Field("AED", max_length=3)
    commission_percentage: Decimal = Field(..., ge=0, le=100)
    tax_deducted: Optional[Decimal] = None
    tax_rate_percentage: Optional[Decimal] = None
    split_basis: Optional[str] = Field("GROSS", description="GROSS or NET basis for split allocation")
    other_deductions: Optional[Decimal] = None
    broker_split_percentage: Optional[Decimal] = None
    agency_split_percentage: Optional[Decimal] = None
    commission_splits: Optional[List[Dict[str, Any]]] = None
    invoice_reference: Optional[str] = None
    idempotency_key: Optional[str] = None



class CommissionSettleRequest(BaseModel):
    amount_received: Optional[Decimal] = None
    settled_amount: Optional[Decimal] = None
    payment_reference: str = Field(..., min_length=2, max_length=100)
    payment_mode: str = Field("MANUAL_BANK_TRANSFER", max_length=50)
    provenance: Optional[str] = Field("MANUAL_UNVERIFIED", max_length=50)
    currency: Optional[str] = Field(None, max_length=3)
    settled_at: Optional[datetime] = None
    notes: Optional[str] = None
    settlement_evidence_url: Optional[str] = None
    idempotency_key: Optional[str] = None

    @model_validator(mode="after")
    def validate_amount(self):
        amt = self.settled_amount if self.settled_amount is not None else self.amount_received
        if amt is None:
            raise ValueError("settled_amount or amount_received is required")
        if amt <= Decimal("0"):
            raise ValueError("settled_amount must be greater than 0")
        self.settled_amount = amt
        self.amount_received = amt
        return self


class CommissionDisputeRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)
    idempotency_key: Optional[str] = ""


class CommissionReverseRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=500)
    idempotency_key: Optional[str] = ""


# ─────────────────────────────────────────────────────────────────────────────
# Closing
# ─────────────────────────────────────────────────────────────────────────────

class ClosingCreateRequest(BaseModel):
    registration_authority: Optional[str] = None
    registration_number: Optional[str] = None
    registration_date: Optional[datetime] = None
    title_deed_number: Optional[str] = None
    handover_date: Optional[datetime] = None


# ─────────────────────────────────────────────────────────────────────────────
# Post-Sale
# ─────────────────────────────────────────────────────────────────────────────

class PostSaleRecordRequest(BaseModel):
    customer_satisfaction_score: Optional[int] = Field(None, ge=1, le=10)
    nps_score: Optional[int] = Field(None, ge=-100, le=100)
    feedback_text: Optional[str] = None
    referral_given: bool = False
    success_factors: List[str] = Field(default_factory=list)
    obstacle_factors: List[str] = Field(default_factory=list)
    ai_recommendation_followed: Optional[bool] = None


# ─────────────────────────────────────────────────────────────────────────────
# Document
# ─────────────────────────────────────────────────────────────────────────────

class DocumentUploadRequest(BaseModel):
    document_type: str
    document_name: str
    required_at_stage: str
    file_url: Optional[str] = None
    is_required: bool = True


# ─────────────────────────────────────────────────────────────────────────────
# Commercial Audit
# ─────────────────────────────────────────────────────────────────────────────

class CommercialAuditLogEntry(BaseModel):
    id: str
    event_type: str
    actor_id: Optional[str] = None
    actor_type: str
    resource_type: str
    resource_id: str
    change_summary: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard / Analytics
# ─────────────────────────────────────────────────────────────────────────────

class DealPipelineSummary(BaseModel):
    total_active_deals: int
    total_pipeline_value: float
    currency: str = "AED"
    deals_by_stage: Dict[str, int]
    pending_approvals: int
    stalled_deals: int
    commission_pending: float
    commission_earned: float
    commission_unverified: Optional[float] = 0.0
    booked_value: Optional[float] = 0.0
    token_collected: Optional[float] = 0.0
    commission_disputed: Optional[float] = 0.0
