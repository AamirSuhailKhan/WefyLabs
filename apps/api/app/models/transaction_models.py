import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer, Text, Boolean, Float
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")

class DealTransaction(Base, TimestampMixin):
    """
    Enterprise Transaction Lifecycle Model managing the 13 stages from Lead to Commission.
    """
    __tablename__ = "deal_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("property_listings.id", ondelete="CASCADE"), nullable=False, index=True)

    deal_name: Mapped[str] = mapped_column(String(255), nullable=False)
    agreed_price: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="AED", nullable=False)
    current_stage: Mapped[str] = mapped_column(String(50), default="lead", nullable=False, index=True)

    commission_percentage: Mapped[float] = mapped_column(Float, default=2.0, nullable=False)
    estimated_commission_amount: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # AI Risk Intelligence
    risk_level: Mapped[str] = mapped_column(String(30), default="low", nullable=False)
    closing_probability_pct: Mapped[float] = mapped_column(Float, default=85.0, nullable=False)
    missing_documents: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)

    milestones: Mapped[List["DealMilestone"]] = relationship("DealMilestone", back_populates="deal", cascade="all, delete-orphan")
    installments: Mapped[List["DealPaymentSchedule"]] = relationship("DealPaymentSchedule", back_populates="deal", cascade="all, delete-orphan")

class DealMilestone(Base, TimestampMixin):
    """Stage Milestone Tracking."""
    __tablename__ = "deal_milestones"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deal_transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    deal: Mapped["DealTransaction"] = relationship("DealTransaction", back_populates="milestones")

class DealPaymentSchedule(Base, TimestampMixin):
    """Payment Installment Schedule Ledger."""
    __tablename__ = "deal_payment_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deal_transactions.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    due_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    paid_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    deal: Mapped["DealTransaction"] = relationship("DealTransaction", back_populates="installments")
