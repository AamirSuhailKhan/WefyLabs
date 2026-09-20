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
    from app.models.property_models import LeadPropertyInterest

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
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
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
        String(100),  # No DB CheckConstraint — validated by RegionalPipelineService
        default="new",
        nullable=False
    )
    # ── Global / Multi-Country Fields ──────────────────────────────────────────
    # Resolved from phone, form, declared location, property location — NOT just IP
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)  # "AE", "IN"
    market_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True, index=True
    )  # FK to markets.id (nullable — no FK enforced here to avoid circular dep in test isolation)
    locale: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)          # "en-AE", "ar-AE"
    # Confidence of country inference (0.0 - 1.0)
    country_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # phone | form | declared | property_location | crm_data | ip (lowest confidence)
    country_inference_source: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # Budget with explicit currency — never store budget without currency
    budget_currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)  # "AED", "INR"
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
        # REMOVED: property_type CheckConstraint — hardcoded India BHK enum.
        # Property types are now validated by PropertySchemaRegistry per market.
        # Historical values are preserved as-is.
        CheckConstraint(
            "score IN ('hot', 'warm', 'cold', 'unqualified', 'pending')",
            name="ck_leads_score"
        ),
        # REMOVED: pipeline_stage CheckConstraint — fixed stages replaced by RegionalPipeline.
        # Stage transitions are now validated by RegionalPipelineService per org+market.
        CheckConstraint(
            "status IN ('pending', 'active', 'qualified', 'converted', 'lost')",
            name="ck_leads_status"
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
        Index("ix_leads_broker_id_score", "broker_id", "score"),
        Index("ix_leads_broker_id_pipeline_stage", "broker_id", "pipeline_stage"),
        Index("ix_leads_broker_deleted_created", "broker_id", "deleted_at", "created_at"),
        Index("ix_leads_country_market", "country_code", "market_id"),
    )

    broker: Mapped["Broker"] = relationship("Broker", back_populates="leads")
    conversations: Mapped[List["Conversation"]] = relationship("Conversation", back_populates="lead", cascade="all, delete-orphan", order_by="Conversation.created_at.asc()")
    scores: Mapped[List["Score"]] = relationship("Score", back_populates="lead", cascade="all, delete-orphan", order_by="Score.created_at.desc()")
    follow_ups: Mapped[List["FollowUp"]] = relationship("FollowUp", back_populates="lead", cascade="all, delete-orphan", order_by="FollowUp.scheduled_at.asc()")
    interested_properties: Mapped[List["LeadPropertyInterest"]] = relationship("LeadPropertyInterest", back_populates="lead", cascade="all, delete-orphan")

    @property
    def organization_id(self) -> str:
        return str(self.broker_id)

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Canonical representation of customer identity and CRM state."""
        return {
            "customer_id": str(self.id),
            "organization_id": str(self.broker_id),
            "name": self.name,
            "phone": self.phone,
            "email": self.email,
            "source": self.source,
            "status": self.status,
            "pipeline_stage": self.pipeline_stage,
            "score": self.score,
            "score_confidence": self.score_confidence,
            "transaction_type": self.transaction_type,
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "budget_currency": self.budget_currency or "INR",
            "property_type": self.property_type,
            "preferred_locations": self.preferred_locations or [],
            "timeline": self.timeline,
            "loan_status": self.loan_status,
            "country_code": self.country_code,
            "locale": self.locale,
            "last_message_at": self.last_message_at.isoformat() if self.last_message_at else None,
            "qualified_at": self.qualified_at.isoformat() if self.qualified_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
