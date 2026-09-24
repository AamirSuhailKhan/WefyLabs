"""
Part 21 — Customer Portal, Digital Deal Room & Transaction Collaboration Models
================================================================================
SQLAlchemy 2.0 models for:
1. CustomerPortalInvite               — Time-bound, SHA-256 hashed customer access tokens
2. CustomerSupportRequest             — Customer queries/tickets linked to CRM tasks
3. CustomerPaymentProof               — Payment receipts uploaded by customer for staff verification
4. CustomerTransactionAcknowledgement — Formal customer acknowledgement of terms & milestones
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Numeric, JSON,
    Index, UniqueConstraint, ForeignKey, func
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")
MoneyType = Numeric(precision=20, scale=4)


def _gen_uuid() -> uuid.UUID:
    return uuid.uuid4()


class CustomerPortalInvite(Base, TimestampMixin):
    """
    Secure customer portal invitation and magic-link store.
    Stores only the SHA-256 hash of the raw token (raw token is never stored in DB).
    Enforces expiry (default 7 days) and single/active use tracking.
    """
    __tablename__ = "customer_portal_invites"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    invited_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True)
    
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False, index=True) # active | used | revoked | expired
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    last_accessed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    access_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        Index("ix_portal_invites_org_lead", "organization_id", "lead_id"),
        Index("ix_portal_invites_hash_status", "token_hash", "status"),
    )


class CustomerSupportRequest(Base, TimestampMixin, SoftDeleteMixin):
    """
    Customer service request / query submitted through the customer portal.
    Bridges into CRM Tasks and Activities for the assigned broker.
    """
    __tablename__ = "customer_support_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    deal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="SET NULL"), nullable=True, index=True)
    
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # DOCUMENT_HELP | PAYMENT_QUERY | APPOINTMENT_QUERY | TRANSACTION_QUERY | HANDOVER_QUERY | GENERAL
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="OPEN", nullable=False, index=True) # OPEN | IN_PROGRESS | RESOLVED | CLOSED
    priority: Mapped[str] = mapped_column(String(20), default="NORMAL", nullable=False) # LOW | NORMAL | HIGH | URGENT
    
    assigned_broker_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True, index=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attachment_urls: Mapped[Optional[List[str]]] = mapped_column(JSONBType, default=list, nullable=True)

    __table_args__ = (
        Index("ix_support_req_org_status", "organization_id", "status"),
        Index("ix_support_req_lead", "lead_id"),
    )


class CustomerPaymentProof(Base, TimestampMixin):
    """
    Payment receipt or wire confirmation submitted by the customer.
    Must be reviewed and verified by staff before the milestone is confirmed.
    System NEVER treats upload as money received.
    """
    __tablename__ = "customer_payment_proofs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    
    milestone_index: Mapped[int] = mapped_column(Integer, nullable=False) # index into booking.payment_schedule
    milestone_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_reported: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="AED", nullable=False)
    
    payment_mode: Mapped[str] = mapped_column(String(50), nullable=False) # bank_transfer | cheque | wire | online_gateway
    transaction_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    receipt_url: Mapped[str] = mapped_column(String(512), nullable=False)
    customer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    status: Mapped[str] = mapped_column(String(20), default="REPORTED", nullable=False, index=True) # REPORTED | VERIFIED | REJECTED
    reviewed_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    __table_args__ = (
        Index("ix_payment_proof_deal_status", "deal_id", "status"),
        Index("ix_payment_proof_org", "organization_id"),
    )


class CustomerTransactionAcknowledgement(Base, TimestampMixin):
    """
    Formal timestamped customer acknowledgement of transaction terms, disclosures, or milestones.
    Not a fabricated legal signature — an authoritative audit trail of user acceptance.
    """
    __tablename__ = "customer_transaction_acknowledgements"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    
    acknowledgement_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # BOOKING_SUMMARY | PAYMENT_SCHEDULE | AGREEMENT_TERMS | CLOSING_DISCLOSURE
    item_version: Mapped[str] = mapped_column(String(50), default="v1.0", nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[Optional[Dict]] = mapped_column(JSONBType, default=dict, nullable=True)
    acknowledged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_ack_deal_type", "deal_id", "acknowledgement_type"),
        Index("ix_ack_org_lead", "organization_id", "lead_id"),
    )
