"""
Part 21 — Customer Portal, Digital Deal Room & Transaction Collaboration DTOs
=============================================================================
Strictly customer-safe schemas with zero internal CRM/financial data leakage.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# ─── Auth & Session DTOs ──────────────────────────────────────────────────────

class PortalTokenExchangeRequest(BaseModel):
    token: str = Field(..., min_length=16, description="Raw invite or magic-link token")

class PortalMagicLinkRequest(BaseModel):
    email_or_phone: str = Field(..., min_length=3, description="Customer registered email or phone")

class PortalAuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 86400  # 24 hours
    customer_id: str
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    organization_id: str

class PortalCustomerContext(BaseModel):
    """Internal security context extracted from verified customer JWT."""
    lead_id: str
    organization_id: str
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None


# ─── Portal Overview DTOs ─────────────────────────────────────────────────────

class CustomerAssignedAdvisor(BaseModel):
    name: str
    agency_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

class CustomerActiveDealSummary(BaseModel):
    deal_id: str
    deal_reference: str
    deal_title: str
    current_stage: str
    stage_display_name: str
    agreed_price: Optional[Decimal] = None
    currency: str = "AED"
    status: str
    booked_at: Optional[datetime] = None

class CustomerNextAction(BaseModel):
    action_type: str  # UPLOAD_DOCUMENT | REVIEW_AGREEMENT | CONFIRM_APPOINTMENT | PAY_MILESTONE | COMPLETE_NPS | NONE
    title: str
    description: str
    target_id: Optional[str] = None
    action_url: Optional[str] = None
    is_urgent: bool = False

class CustomerPortalOverview(BaseModel):
    customer_name: str
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None
    assigned_advisor: Optional[CustomerAssignedAdvisor] = None
    active_deal: Optional[CustomerActiveDealSummary] = None
    next_action: CustomerNextAction
    upcoming_appointment_count: int = 0
    pending_documents_count: int = 0
    due_payments_count: int = 0
    unread_messages_count: int = 0


# ─── Digital Deal Room DTOs ───────────────────────────────────────────────────

class DealPropertySummary(BaseModel):
    property_id: Optional[str] = None
    project_name: Optional[str] = None
    unit_number: Optional[str] = None
    bhk: Optional[str] = None
    area_sqft: Optional[float] = None
    price: Optional[Decimal] = None
    currency: str = "AED"
    address: Optional[str] = None
    city: Optional[str] = None
    features: List[str] = Field(default_factory=list)
    image_urls: List[str] = Field(default_factory=list)

class DealStageStep(BaseModel):
    stage_key: str
    stage_name: str
    order_index: int
    is_current: bool = False
    is_completed: bool = False
    completed_at: Optional[datetime] = None

class CustomerDealOfferSummary(BaseModel):
    offer_price: Decimal
    currency: str = "AED"
    listing_price: Optional[Decimal] = None
    status: str
    valid_until: Optional[datetime] = None
    accepted_at: Optional[datetime] = None

class CustomerDealReservationSummary(BaseModel):
    reservation_amount: Optional[Decimal] = None
    currency: str = "AED"
    reserved_price: Optional[Decimal] = None
    reserved_at: datetime
    expires_at: Optional[datetime] = None
    status: str

class CustomerDealBookingSummary(BaseModel):
    booking_reference: str
    token_amount: Optional[Decimal] = None
    token_paid_at: Optional[datetime] = None
    booked_price: Decimal
    currency: str = "AED"
    payment_plan_type: Optional[str] = None
    status: str
    booked_at: Optional[datetime] = None

class CustomerDealClosingSummary(BaseModel):
    registration_authority: Optional[str] = None
    registration_number: Optional[str] = None
    title_deed_number: Optional[str] = None
    title_deed_issued_at: Optional[datetime] = None
    handover_date: Optional[datetime] = None
    keys_handed_at: Optional[datetime] = None
    status: str

class CustomerPortalDeal(BaseModel):
    deal_id: str
    deal_reference: str
    deal_title: str
    current_stage: str
    stage_display_name: str
    currency: str
    agreed_price: Optional[Decimal] = None
    status: str
    
    property: Optional[DealPropertySummary] = None
    stages_timeline: List[DealStageStep] = Field(default_factory=list)
    offer: Optional[CustomerDealOfferSummary] = None
    reservation: Optional[CustomerDealReservationSummary] = None
    booking: Optional[CustomerDealBookingSummary] = None
    closing: Optional[CustomerDealClosingSummary] = None
    is_acknowledged: bool = False


# ─── Documents DTOs ───────────────────────────────────────────────────────────

class CustomerPortalDocument(BaseModel):
    document_id: str
    document_type: str
    document_name: str
    required_at_stage: str
    is_required: bool
    customer_status: str  # ACTION_REQUIRED | IN_REVIEW | APPROVED
    file_url: Optional[str] = None
    uploaded_at: Optional[datetime] = None
    verified_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None

class CustomerDocumentUploadRequest(BaseModel):
    file_url: str = Field(..., min_length=5, description="Uploaded file URL")
    document_name: Optional[str] = None
    idempotency_key: Optional[str] = None


# ─── Payment Schedule & Proof DTOs ───────────────────────────────────────────

class CustomerPortalPaymentMilestone(BaseModel):
    index: int
    name: str
    amount: Decimal
    due_date: Optional[datetime] = None
    status: str  # UPCOMING | DUE | REPORTED | VERIFIED | OVERDUE
    payment_mode: Optional[str] = None
    receipt_reference: Optional[str] = None
    verified_at: Optional[datetime] = None

class CustomerPortalPaymentSchedule(BaseModel):
    deal_id: str
    currency: str
    total_payable: Decimal
    total_verified: Decimal
    remaining_balance: Decimal
    milestones: List[CustomerPortalPaymentMilestone] = Field(default_factory=list)
    payment_instructions: str
    is_live_gateway_enabled: bool = False  # Always False per Razorpay boundary

class CustomerPaymentProofSubmitRequest(BaseModel):
    milestone_index: int = Field(..., ge=0)
    amount_reported: Decimal = Field(..., gt=0)
    currency: str = Field(default="AED", min_length=3, max_length=3)
    payment_mode: str = Field(..., description="bank_transfer | cheque | wire | online_gateway")
    transaction_reference: str = Field(..., min_length=2)
    receipt_url: str = Field(..., min_length=5)
    customer_notes: Optional[str] = None
    idempotency_key: Optional[str] = None


# ─── Appointments & Viewing DTOs ──────────────────────────────────────────────

class CustomerPortalAppointment(BaseModel):
    appointment_id: str
    title: str
    meeting_type: str  # PROPERTY_VIEWING | SITE_VISIT | CALL | VIDEO_CALL
    start_utc: datetime
    end_utc: datetime
    duration_minutes: int
    location: Optional[str] = None
    meeting_url: Optional[str] = None
    status: str  # REQUESTED | CONFIRMED | RESCHEDULED | CANCELLED | COMPLETED

class CustomerAppointmentConfirmRequest(BaseModel):
    idempotency_key: Optional[str] = None


# ─── Messages & Communication DTOs ────────────────────────────────────────────

class CustomerPortalMessage(BaseModel):
    message_id: str
    direction: str  # inbound (customer) | outbound (staff/AI)
    sender_name: str
    content: str
    created_at: datetime
    attachments: List[str] = Field(default_factory=list)

class CustomerSendMessageRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    attachments: Optional[List[str]] = Field(default_factory=list)


# ─── Customer Support Requests DTOs ───────────────────────────────────────────

class CustomerSupportRequestCreate(BaseModel):
    category: str = Field(..., description="DOCUMENT_HELP | PAYMENT_QUERY | APPOINTMENT_QUERY | TRANSACTION_QUERY | HANDOVER_QUERY | GENERAL")
    subject: str = Field(..., min_length=3, max_length=255)
    description: str = Field(..., min_length=5)
    priority: str = Field(default="NORMAL", description="LOW | NORMAL | HIGH | URGENT")
    attachment_urls: Optional[List[str]] = Field(default_factory=list)

class CustomerSupportRequestResponse(BaseModel):
    id: str
    category: str
    subject: str
    description: str
    status: str  # OPEN | IN_PROGRESS | RESOLVED | CLOSED
    priority: str
    created_at: datetime
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None


# ─── Post-Sale & CSAT/NPS DTOs ────────────────────────────────────────────────

class CustomerPostSaleFeedbackRequest(BaseModel):
    csat_score: int = Field(..., ge=1, le=5, description="1 to 5 customer satisfaction rating")
    nps_score: int = Field(..., ge=1, le=10, description="1 to 10 net promoter score")
    feedback_text: Optional[str] = Field(None, max_length=2000)
    referral_interested: bool = False

class CustomerPostSaleFeedbackResponse(BaseModel):
    status: str = "RECORDED"
    recorded_at: datetime
    message: str = "Thank you for your valuable feedback."


# ─── Acknowledgement DTOs ─────────────────────────────────────────────────────

class CustomerAcknowledgementRequest(BaseModel):
    acknowledgement_type: str = Field(..., description="BOOKING_SUMMARY | PAYMENT_SCHEDULE | AGREEMENT_TERMS | CLOSING_DISCLOSURE")
    item_version: str = Field(default="v1.0")
    user_agent: Optional[str] = None


# ─── Governed Customer AI DTOs ────────────────────────────────────────────────

class CustomerAIQueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=500)

class CustomerAIQueryResponse(BaseModel):
    answer: str
    suggested_actions: List[str] = Field(default_factory=list)
    source_references: List[str] = Field(default_factory=list)


# ─── Broker-Facing Admin DTOs ─────────────────────────────────────────────────

class PortalInviteGenerateRequest(BaseModel):
    lead_id: str
    deal_id: Optional[str] = None
    expires_in_days: int = Field(default=7, ge=1, le=30)

class PortalInviteResponse(BaseModel):
    invite_id: str
    lead_id: str
    customer_email: Optional[str] = None
    raw_token: str
    portal_access_url: str
    expires_at: datetime

class DocumentReviewDecision(BaseModel):
    action: str = Field(..., description="APPROVE | REJECT")
    rejection_reason: Optional[str] = None

class PaymentProofReviewDecision(BaseModel):
    action: str = Field(..., description="VERIFY | REJECT")
    review_notes: Optional[str] = None
    rejection_reason: Optional[str] = None
