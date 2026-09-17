"""
PART 31 — Customer Onboarding, Tenant Activation & Demo Mode Models
===================================================================
SQLAlchemy 2.0 models for:
- OnboardingState: Per-organization progressive onboarding state machine.
- TenantActivation: Milestone achievement and deterministic activation score tracking.
- DemoSession: Isolated synthetic playground session lifecycle and TTL management.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Integer, Boolean, DateTime, ForeignKey, Index, UniqueConstraint, JSON
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")


class OnboardingState(Base, TimestampMixin):
    """
    Tracks the sequential progress of a tenant's workspace configuration.
    Idempotent, resumable, skippable, and synchronized with live CRM entities.
    """
    __tablename__ = "onboarding_states"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    current_step: Mapped[str] = mapped_column(
        String(50),
        default="ORGANIZATION_SETUP",
        nullable=False
    )
    completed_steps: Mapped[List[str]] = mapped_column(
        JSONBType,
        default=list,
        nullable=False
    )
    skipped_steps: Mapped[List[str]] = mapped_column(
        JSONBType,
        default=list,
        nullable=False
    )
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    step_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONBType,
        default=dict,
        nullable=True
    )

    organization = relationship("Organization", backref="onboarding_state")
    broker = relationship("Broker", backref="onboarding_states")


class TenantActivation(Base, TimestampMixin):
    """
    Authoritative record of a tenant's core value activation.
    Evaluates business milestones (leads, properties, matches, follow-ups).
    """
    __tablename__ = "tenant_activations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    is_activated: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    activation_score: Mapped[int] = mapped_column(
        Integer,
        default=0,
        nullable=False
    )
    completed_milestones: Mapped[List[str]] = mapped_column(
        JSONBType,
        default=list,
        nullable=False
    )
    activated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    time_to_activate_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    first_property_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    first_lead_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    first_match_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    first_followup_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )

    organization = relationship("Organization", backref="activation_record")


class DemoSession(Base, TimestampMixin):
    """
    Manages the lifecycle of an ephemeral synthetic demo playground.
    Bound to a dedicated demo organization; automatically expires and purges safely.
    """
    __tablename__ = "demo_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    demo_organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True
    )
    demo_broker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    session_token: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
        nullable=False,
        index=True
    )  # active | expired | converted | purged
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True
    )
    created_by_ip: Mapped[Optional[str]] = mapped_column(
        String(45),
        nullable=True
    )
    metadata_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSONBType,
        default=dict,
        nullable=True
    )

    demo_organization = relationship("Organization", backref="demo_session")
    demo_broker = relationship("Broker", backref="demo_sessions")
