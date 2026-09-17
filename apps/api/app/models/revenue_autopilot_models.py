"""
Part 35 — AI Real Estate Revenue Autopilot Models
==================================================
SQLAlchemy 2.0 models for Revenue Opportunities, Prioritized Actions,
Deterministic Provenance, and Agent Feedback Logs.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, TYPE_CHECKING
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index,
    UniqueConstraint, ForeignKey, func
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


class RevenueOpportunity(Base, TimestampMixin, SoftDeleteMixin):
    """
    Canonical Revenue Opportunity Entity.
    Represents an actionable, high-value commercial situation connecting
    a Lead, a Property Recommendation, timing urgency, and a concrete next action.
    """
    __tablename__ = "revenue_opportunities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    property_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("property_listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    assigned_agent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brokers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Category: NEW_HIGH_VALUE_MATCH | HOT_LEAD_NEEDS_CONTACT | STALE_HOT_LEAD | NEW_PROPERTY_MATCH |
    #           SITE_VISIT_FOLLOW_UP | POST_SITE_VISIT_FOLLOW_UP | PRICE_CHANGE_MATCH |
    #           REACTIVATION_OPPORTUNITY | DEAL_STALLED | NEW_INVENTORY_DEMAND | LEAD_REQUIREMENT_CHANGED
    opportunity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Priority & Urgency: CRITICAL | HIGH | MEDIUM | LOW
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False, index=True)
    urgency: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False, index=True)

    # Scores (0.0 - 100.0)
    # Revenue Opportunity Score (Commercial actionability right now)
    opportunity_score: Mapped[float] = mapped_column(Float, default=50.0, nullable=False, index=True)
    # Property Match Score (How suitable is the property for the lead)
    match_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, index=True)
    # Confidence (Data completeness and evidence quality 0.0 - 1.0)
    confidence: Mapped[float] = mapped_column(Float, default=0.8, nullable=False)

    # State Machine: NEW -> RECOMMENDED -> ACTIONED -> IN_PROGRESS -> COMPLETED | DISMISSED | EXPIRED | INVALIDATED
    status: Mapped[str] = mapped_column(String(30), default="NEW", nullable=False, index=True)

    # Explainability & Provenance
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    why_now: Mapped[str] = mapped_column(Text, nullable=False)
    why_property: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_of_inactivity: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Action directives
    recommended_action: Mapped[str] = mapped_column(String(50), default="CALL_LEAD", nullable=False)
    recommended_channel: Mapped[str] = mapped_column(String(30), default="CALL", nullable=False)

    # Snapshots and Signals
    recommended_property_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    alternative_properties: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    positive_signals: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    negative_signals: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    data_freshness: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    # Grounded Outreach Drafts (AI generated or fallback)
    call_brief: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    email_draft: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    # Deduplication & Engine Metadata
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    provenance: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    scoring_version: Mapped[str] = mapped_column(String(20), default="v1", nullable=False)

    # Timestamps & Lifecycle tracking
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    actioned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissal_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Feedback Loop
    feedback_rating: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # YES | NO | NOT_SURE
    feedback_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    __table_args__ = (
        Index("ix_rev_opp_org_status", "organization_id", "status"),
        Index("ix_rev_opp_org_score", "organization_id", "opportunity_score"),
        Index("ix_rev_opp_org_urgency", "organization_id", "urgency"),
        Index("ix_rev_opp_dedup", "dedup_key"),
        Index("ix_rev_opp_lead_status", "lead_id", "status"),
    )

    lead: Mapped["Lead"] = relationship("Lead", foreign_keys=[lead_id])
    property_listing: Mapped[Optional["PropertyListing"]] = relationship("PropertyListing", foreign_keys=[property_id])
    broker: Mapped["Broker"] = relationship("Broker", foreign_keys=[broker_id])


class RevenueFeedbackLog(Base, TimestampMixin):
    """
    Durable Audit Log of Agent Actions and Feedback on Revenue Opportunities.
    Provides auditable training dataset for future predictive models.
    """
    __tablename__ = "revenue_feedback_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("revenue_opportunities.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    property_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("property_listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ACTIONED | DISMISSED | COMPLETED | FEEDBACK
    rating: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # YES | NO | NOT_SURE
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    actual_outcome: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    features_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    __table_args__ = (
        Index("ix_rev_fb_org_created", "organization_id", "created_at"),
        Index("ix_rev_fb_opp", "opportunity_id"),
    )
