import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import String, BigInteger, Float, DateTime, ForeignKey, CheckConstraint, Index, JSON, text, func
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.broker import Broker
    from app.models.conversation import Conversation
    from app.models.score import Score
    from app.models.follow_up import FollowUp

# Preferred locations ARRAY for Postgres with JSON fallback for SQLite
PreferredLocationsType = ARRAY(String).with_variant(JSON(), "sqlite")
# JSONB for PostgreSQL with JSON fallback for SQLite
JSONBType = JSONB().with_variant(JSON(), "sqlite")

class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(
        String(50),
        default="manual",
        nullable=False
    )
    score: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False
    )
    score_confidence: Mapped[float] = mapped_column(
        Float,
        default=0.0,
        nullable=False
    )
    budget_min: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    budget_max: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    property_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    transaction_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    preferred_locations: Mapped[List[str]] = mapped_column(
        PreferredLocationsType,
        default=list,
        nullable=False
    )
    timeline: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    loan_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default="pending",
        nullable=False
    )
    pipeline_stage: Mapped[str] = mapped_column(
        String(30),
        default="new",
        nullable=False
    )
    notes: Mapped[List[Dict[str, Any]]] = mapped_column(
        JSONBType,
        default=list,
        nullable=False
    )
    last_message_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    qualified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "source IN ('whatsapp_forward', 'facebook', 'google', 'manual')",
            name="ck_leads_source"
        ),
        CheckConstraint(
            "score IN ('hot', 'warm', 'cold', 'unqualified', 'pending')",
            name="ck_leads_score"
        ),
        CheckConstraint(
            "property_type IS NULL OR property_type IN ('1bhk', '2bhk', '3bhk', 'villa', 'plot')",
            name="ck_leads_property_type"
        ),
        CheckConstraint(
            "transaction_type IS NULL OR transaction_type IN ('buy', 'rent', 'lease')",
            name="ck_leads_transaction_type"
        ),
        CheckConstraint(
            "timeline IS NULL OR timeline IN ('immediate', '1_month', '3_months', '6_months')",
            name="ck_leads_timeline"
        ),
        CheckConstraint(
            "loan_status IS NULL OR loan_status IN ('pre_approved', 'in_process', 'not_started')",
            name="ck_leads_loan_status"
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'qualified', 'converted', 'lost')",
            name="ck_leads_status"
        ),
        CheckConstraint(
            "pipeline_stage IN ('new', 'contacted', 'viewing', 'negotiating', 'closed_won', 'closed_lost')",
            name="ck_leads_pipeline_stage"
        ),
        Index("ix_leads_broker_id_score", "broker_id", "score"),
        Index("ix_leads_broker_id_pipeline_stage", "broker_id", "pipeline_stage"),
        Index("ix_leads_broker_deleted_created", "broker_id", "deleted_at", "created_at"),
    )

    broker: Mapped["Broker"] = relationship("Broker", back_populates="leads")
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="lead", cascade="all, delete-orphan", order_by="Conversation.created_at.asc()")
    scores: Mapped[List["Score"]] = relationship("Score", back_populates="lead", cascade="all, delete-orphan", order_by="Score.created_at.desc()")
    follow_ups: Mapped[List["FollowUp"]] = relationship("FollowUp", back_populates="lead", cascade="all, delete-orphan", order_by="FollowUp.scheduled_at.asc()")
