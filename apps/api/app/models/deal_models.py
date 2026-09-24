"""
Part 18 — Real Estate Deal, Booking & Transaction OS
=====================================================
SQLAlchemy 2.0 models for the full commercial pipeline from
Opportunity through Negotiation, Offer, Reservation, Booking,
Transaction, Commission, Closing, Post-Sale, and Revenue Learning.

Design principles:
- Extends DealTransaction (existing) -- does NOT replace it.
- Every commercial state change is audited via the Outbox (Part 17).
- No autonomous financial mutations. AI recommends; humans confirm.
- Tenant-isolated via broker_id + organization_id.
- Numeric precision for all monetary fields (Decimal, not Float).
- Idempotency keys on every write operation.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Numeric, JSON,
    Index, UniqueConstraint, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.property_models import PropertyListing
    from app.models.broker import Broker

JSONBType = JSONB().with_variant(JSON(), "sqlite")
MoneyType = Numeric(precision=20, scale=4)


class DealStage:
    OPPORTUNITY  = "opportunity"
    NEGOTIATION  = "negotiation"
    OFFER        = "offer"
    RESERVATION  = "reservation"
    BOOKING      = "booking"
    TRANSACTION  = "transaction"
    COMMISSION   = "commission"
    CLOSING      = "closing"
    POST_SALE    = "post_sale"

    ORDERED: List[str] = [
        OPPORTUNITY, NEGOTIATION, OFFER, RESERVATION,
        BOOKING, TRANSACTION, COMMISSION, CLOSING, POST_SALE
    ]
    TERMINAL: List[str] = [CLOSING, POST_SALE]
    IRREVERSIBLE: List[str] = [BOOKING, TRANSACTION, COMMISSION, CLOSING]


class Deal(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "deals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("property_listings.id", ondelete="SET NULL"), nullable=True, index=True)
    assigned_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True, index=True)
    legacy_deal_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("deal_transactions.id", ondelete="SET NULL"), nullable=True, index=True)
    deal_reference: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    deal_title: Mapped[str] = mapped_column(String(255), nullable=False)
    current_stage: Mapped[str] = mapped_column(String(30), default=DealStage.OPPORTUNITY, nullable=False, index=True)
    previous_stage: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    stage_entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    stage_duration_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    agreed_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    offer_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    final_transaction_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="AED", nullable=False)
    commission_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=5, scale=2), nullable=True)
    commission_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    commission_split_details: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    closing_probability_pct: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2), default=Decimal("80.00"), nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    risk_factors: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False, index=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    close_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    lost_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    tags: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)

    stage_history: Mapped[List["DealStageHistory"]] = relationship("DealStageHistory", back_populates="deal", cascade="all, delete-orphan", lazy="selectin")
    offer: Mapped[Optional["DealOffer"]] = relationship("DealOffer", back_populates="deal", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    reservation: Mapped[Optional["DealReservation"]] = relationship("DealReservation", back_populates="deal", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    booking: Mapped[Optional["DealBooking"]] = relationship("DealBooking", back_populates="deal", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    commission_record: Mapped[Optional["DealCommission"]] = relationship("DealCommission", back_populates="deal", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    closing_record: Mapped[Optional["DealClosing"]] = relationship("DealClosing", back_populates="deal", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    post_sale_record: Mapped[Optional["DealPostSale"]] = relationship("DealPostSale", back_populates="deal", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    documents: Mapped[List["DealDocument"]] = relationship("DealDocument", back_populates="deal", cascade="all, delete-orphan", lazy="selectin")
    approval_requests: Mapped[List["DealApprovalRequest"]] = relationship("DealApprovalRequest", back_populates="deal", cascade="all, delete-orphan", lazy="selectin")
    commercial_audit: Mapped[List["DealCommercialAuditLog"]] = relationship("DealCommercialAuditLog", back_populates="deal", cascade="all, delete-orphan", lazy="selectin")
    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])
    property_listing: Mapped[Optional["PropertyListing"]] = relationship("PropertyListing", foreign_keys=[property_id])
    broker: Mapped["Broker"] = relationship("Broker", foreign_keys=[broker_id])

    __table_args__ = (
        UniqueConstraint("organization_id", "deal_reference", name="uq_deal_ref_per_org"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_deal_idempotency_per_org"),
        Index("ix_deals_org_stage", "organization_id", "current_stage"),
        Index("ix_deals_org_status", "organization_id", "status"),
        Index("ix_deals_broker_stage", "broker_id", "current_stage"),
        Index("ix_deals_lead", "lead_id"),
        Index("ix_deals_property", "property_id"),
    )

    @property
    def is_closed(self) -> bool:
        return self.status in ("CLOSED_WON", "CLOSED_LOST", "CANCELLED")

    @property
    def is_irreversible_stage(self) -> bool:
        return self.current_stage in DealStage.IRREVERSIBLE


class DealStageHistory(Base, TimestampMixin):
    __tablename__ = "deal_stage_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    from_stage: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    transitioned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    transitioned_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    transitioned_by_type: Mapped[str] = mapped_column(String(20), default="HUMAN", nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_hours_in_previous_stage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_json: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    deal: Mapped["Deal"] = relationship("Deal", back_populates="stage_history")

    __table_args__ = (
        Index("ix_deal_stage_hist_deal", "deal_id", "transitioned_at"),
        Index("ix_deal_stage_hist_org", "organization_id", "to_stage"),
    )


class DealOffer(Base, TimestampMixin):
    __tablename__ = "deal_offers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    offer_price: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="AED", nullable=False)
    listing_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    discount_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    discount_percentage: Mapped[Optional[Decimal]] = mapped_column(Numeric(precision=5, scale=2), nullable=True)
    payment_plan: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    token_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    possession_date_requested: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    special_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT", nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    offer_history: Mapped[List[Dict]] = mapped_column(JSONBType, default=list, nullable=False)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    counter_offer_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    submitted_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    accepted_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    deal: Mapped["Deal"] = relationship("Deal", back_populates="offer")

    __table_args__ = (Index("ix_deal_offers_org_status", "organization_id", "status"),)


class DealReservation(Base, TimestampMixin):
    __tablename__ = "deal_reservations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    property_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("property_listings.id", ondelete="SET NULL"), nullable=True, index=True)
    reservation_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="AED", nullable=False)
    reserved_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    reserved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", nullable=False, index=True)
    reservation_form_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    reservation_form_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reservation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reserved_by_agent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    deal: Mapped["Deal"] = relationship("Deal", back_populates="reservation")

    __table_args__ = (
        Index("ix_deal_reservations_org_status", "organization_id", "status"),
        Index("ix_deal_reservations_expires", "expires_at"),
    )


class DealBooking(Base, TimestampMixin):
    __tablename__ = "deal_bookings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    booking_reference: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    token_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    token_paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    token_payment_mode: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    token_receipt_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    booked_price: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="AED", nullable=False)
    payment_plan_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    down_payment_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    down_payment_due_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING_PAYMENT", nullable=False, index=True)
    booked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    booking_form_signed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    booking_form_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    payment_schedule: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    forfeiture_amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    deal: Mapped["Deal"] = relationship("Deal", back_populates="booking")

    __table_args__ = (
        UniqueConstraint("organization_id", "booking_reference", name="uq_booking_ref_per_org"),
        Index("ix_deal_bookings_org_status", "organization_id", "status"),
    )


class DealCommission(Base, TimestampMixin):
    __tablename__ = "deal_commissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_price: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="AED", nullable=False)
    commission_percentage: Mapped[Decimal] = mapped_column(Numeric(precision=5, scale=2), nullable=False)
    gross_commission: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    tax_deducted: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    net_commission: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    commission_splits: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    invoice_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    invoiced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_mode: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    disputed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dispute_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dispute_resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deal: Mapped["Deal"] = relationship("Deal", back_populates="commission_record")

    __table_args__ = (
        Index("ix_deal_commissions_org_status", "organization_id", "status"),
        Index("ix_deal_commissions_broker_status", "broker_id", "status"),
    )


class DealClosing(Base, TimestampMixin):
    __tablename__ = "deal_closings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    closing_checklist: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    registration_authority: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    registration_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    registration_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    title_deed_number: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    title_deed_issued_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    handover_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    keys_handed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    handover_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="IN_PROGRESS", nullable=False, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deal: Mapped["Deal"] = relationship("Deal", back_populates="closing_record")

    __table_args__ = (Index("ix_deal_closings_org_status", "organization_id", "status"),)


class DealPostSale(Base, TimestampMixin):
    __tablename__ = "deal_post_sales"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    customer_satisfaction_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    nps_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    feedback_collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    referral_given: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    referral_lead_ids: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    after_sales_interactions: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    success_factors: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    obstacle_factors: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    days_to_close: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_recommendation_followed: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    ai_recommendations_accepted: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    ai_recommendations_rejected: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deal: Mapped["Deal"] = relationship("Deal", back_populates="post_sale_record")

    __table_args__ = (Index("ix_deal_post_sales_org", "organization_id"),)


class DealDocument(Base, TimestampMixin):
    __tablename__ = "deal_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    document_name: Mapped[str] = mapped_column(String(255), nullable=False)
    required_at_stage: Mapped[str] = mapped_column(String(30), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="REQUIRED", nullable=False, index=True)
    file_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    uploaded_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    verified_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deal: Mapped["Deal"] = relationship("Deal", back_populates="documents")

    __table_args__ = (
        Index("ix_deal_docs_deal_stage", "deal_id", "required_at_stage"),
        Index("ix_deal_docs_status", "deal_id", "status"),
    )


class DealApprovalRequest(Base, TimestampMixin):
    __tablename__ = "deal_approval_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    requested_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    requested_by_type: Mapped[str] = mapped_column(String(20), default="HUMAN", nullable=False)
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    action_payload: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)
    reviewed_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    deal: Mapped["Deal"] = relationship("Deal", back_populates="approval_requests")

    __table_args__ = (
        Index("ix_deal_approvals_org_status", "organization_id", "status"),
        Index("ix_deal_approvals_deal_action", "deal_id", "action_type"),
    )


class DealCommercialAuditLog(Base):
    __tablename__ = "deal_commercial_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="HUMAN", nullable=False)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(64), nullable=False)
    previous_state: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    new_state: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False, index=True)
    deal: Mapped["Deal"] = relationship("Deal", back_populates="commercial_audit")

    __table_args__ = (
        Index("ix_deal_audit_org_event", "organization_id", "event_type", "created_at"),
        Index("ix_deal_audit_deal_created", "deal_id", "created_at"),
        Index("ix_deal_audit_idempotency", "organization_id", "idempotency_key"),
    )
