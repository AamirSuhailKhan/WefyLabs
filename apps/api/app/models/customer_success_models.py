import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

class CustomerHealthRecord(Base, TimestampMixin):
    """
    Customer Success & Health Score Model tracking tenant adoption,
    churn risk, NPS/CSAT scores, and onboarding completion percentage.
    """
    __tablename__ = "customer_health_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    health_score: Mapped[int] = mapped_column(Integer, default=100, nullable=False) # 0-100
    health_status: Mapped[str] = mapped_column(String(20), default="healthy", nullable=False) # healthy | warning | at_risk
    churn_risk_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False) # 0.0 - 100.0%
    onboarding_completed_pct: Mapped[int] = mapped_column(Integer, default=20, nullable=False) # 0 - 100%
    nps_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # 0-10
    csat_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True) # 1-5

class SupportTicket(Base, TimestampMixin):
    """Customer Support Console Ticket Entity."""
    __tablename__ = "support_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="medium", nullable=False) # low | medium | high | urgent
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False) # open | in_progress | resolved
