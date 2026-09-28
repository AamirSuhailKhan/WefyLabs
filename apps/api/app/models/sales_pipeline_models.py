"""
Build 08 — WefyLabs Sales Pipeline OS
======================================
Canonical models for the complete lead-to-revenue transaction graph.

Domain concepts introduced:
1. SalesPipeline           — org-configurable pipeline definition
2. PipelineStageConfig     — configurable stage with semantic type, SLA, guardrails
3. OpportunityStageHistory — immutable record of every stage transition
4. SiteVisit               — canonical site visit entity (physical/virtual)
5. SiteVisitOutcome        — post-visit structured feedback
6. NegotiationRound        — immutable per-round offer/counter record
7. PropertyShortlist       — per-opportunity property interest history
8. BookingIntent           — explicit booking intent (before DealBooking)
9. UnitHold                — inventory hold with TTL (linked to ProjectUnit)
10. PropertyPaymentTransaction — real-estate payment (not platform billing)
11. RevenueEvent           — immutable append-only revenue event log

Design principles:
- NEVER use Float for monetary values — all money is Numeric(20, 4)
- Every state change emits an OutboxEvent atomically
- Every model is tenant-isolated via organization_id
- No autonomous financial mutations — AI recommends, humans confirm
- Idempotency keys on all write operations
- Stage transitions are validated server-side, never trusted from client
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
    from app.models.deal_models import Deal, DealBooking
    from app.models.calendar_models import SchedulingMeeting
    from app.models.inventory_models import ProjectUnit

JSONBType = JSONB().with_variant(JSON(), "sqlite")
MoneyType = Numeric(precision=20, scale=4)
PctType   = Numeric(precision=7, scale=4)


# ---------------------------------------------------------------------------
# CONTROLLED VOCABULARIES
# ---------------------------------------------------------------------------

class OpportunityStage:
    """
    Build 08 canonical opportunity stage vocabulary.
    These stages are semantic types. Organizations may configure display labels
    but the underlying semantics must remain deterministic.
    """
    NEW                  = "NEW"
    QUALIFIED            = "QUALIFIED"
    PROPERTY_SHORTLISTED = "PROPERTY_SHORTLISTED"
    APPOINTMENT_SET      = "APPOINTMENT_SET"
    SITE_VISIT_SCHEDULED = "SITE_VISIT_SCHEDULED"
    SITE_VISIT_COMPLETED = "SITE_VISIT_COMPLETED"
    NEGOTIATION          = "NEGOTIATION"
    BOOKING_PENDING      = "BOOKING_PENDING"
    BOOKED               = "BOOKED"
    WON                  = "WON"
    LOST                 = "LOST"

    ORDERED: List[str] = [
        NEW, QUALIFIED, PROPERTY_SHORTLISTED, APPOINTMENT_SET,
        SITE_VISIT_SCHEDULED, SITE_VISIT_COMPLETED,
        NEGOTIATION, BOOKING_PENDING, BOOKED, WON,
    ]

    # Terminal stages — no further progression
    TERMINAL: List[str] = [WON, LOST]

    # Stages that require explicit business evidence before transition
    EVIDENCE_REQUIRED: List[str] = [BOOKED, WON]

    # Controlled forward transition map
    ALLOWED_FORWARD: Dict[str, List[str]] = {
        NEW:                  [QUALIFIED, LOST],
        QUALIFIED:            [PROPERTY_SHORTLISTED, LOST],
        PROPERTY_SHORTLISTED: [APPOINTMENT_SET, LOST],
        APPOINTMENT_SET:      [SITE_VISIT_SCHEDULED, NEGOTIATION, LOST],
        SITE_VISIT_SCHEDULED: [SITE_VISIT_COMPLETED, APPOINTMENT_SET, LOST],  # reschedule -> APPOINTMENT_SET
        SITE_VISIT_COMPLETED: [NEGOTIATION, PROPERTY_SHORTLISTED, LOST],       # property switch -> re-shortlist
        NEGOTIATION:          [BOOKING_PENDING, LOST],
        BOOKING_PENDING:      [BOOKED, NEGOTIATION, LOST],
        BOOKED:               [WON],
        WON:                  [],
        LOST:                 [],
    }

    @classmethod
    def is_allowed_transition(cls, from_stage: str, to_stage: str) -> bool:
        """Returns True only if the transition is in the controlled forward map."""
        allowed = cls.ALLOWED_FORWARD.get(from_stage, [])
        return to_stage in allowed

    @classmethod
    def is_terminal(cls, stage: str) -> bool:
        return stage in cls.TERMINAL


class SiteVisitStatus:
    REQUESTED  = "REQUESTED"
    PROPOSED   = "PROPOSED"
    CONFIRMED  = "CONFIRMED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED  = "CANCELLED"
    NO_SHOW    = "NO_SHOW"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED  = "COMPLETED"

    VALID_TRANSITIONS: Dict[str, List[str]] = {
        REQUESTED:  [PROPOSED, CONFIRMED, CANCELLED],
        PROPOSED:   [CONFIRMED, RESCHEDULED, CANCELLED],
        CONFIRMED:  [RESCHEDULED, CANCELLED, IN_PROGRESS, NO_SHOW],
        RESCHEDULED: [CONFIRMED, CANCELLED],
        CANCELLED:  [],
        NO_SHOW:    [],
        IN_PROGRESS: [COMPLETED, NO_SHOW],
        COMPLETED:  [],
    }

    @classmethod
    def can_transition(cls, from_status: str, to_status: str) -> bool:
        return to_status in cls.VALID_TRANSITIONS.get(from_status, [])


class BookingIntentStatus:
    CREATED   = "CREATED"
    CONFIRMED = "CONFIRMED"
    EXPIRED   = "EXPIRED"
    CANCELLED = "CANCELLED"
    CONVERTED = "CONVERTED"   # Converted to a DealBooking


class UnitHoldStatus:
    ACTIVE   = "ACTIVE"
    EXPIRED  = "EXPIRED"
    RELEASED = "RELEASED"
    CONVERTED = "CONVERTED"   # Converted to DealReservation


class NegotiationRoundActor:
    CUSTOMER   = "CUSTOMER"
    AGENT      = "AGENT"
    MANAGER    = "MANAGER"
    DEVELOPER  = "DEVELOPER"
    AI_DRAFT   = "AI_DRAFT"   # AI proposed — not yet sent


class PropertyShortlistStatus:
    SHORTLISTED = "SHORTLISTED"
    VIEWED      = "VIEWED"
    DISMISSED   = "DISMISSED"
    PREFERRED   = "PREFERRED"
    SELECTED    = "SELECTED"


class LostReasonType:
    PRICE      = "PRICE"
    TIMING     = "TIMING"
    FINANCING  = "FINANCING"
    COMPETITOR = "COMPETITOR"
    PROPERTY   = "PROPERTY"
    CUSTOMER_DECISION = "CUSTOMER_DECISION"
    NO_RESPONSE = "NO_RESPONSE"
    OTHER      = "OTHER"


class RevenueEventType:
    OPPORTUNITY_CREATED      = "opportunity.created"
    OPPORTUNITY_STAGE_CHANGED = "opportunity.stage_changed"
    OPPORTUNITY_WON          = "opportunity.won"
    OPPORTUNITY_LOST         = "opportunity.lost"
    SITE_VISIT_COMPLETED     = "site_visit.completed"
    SITE_VISIT_NO_SHOW       = "site_visit.no_show"
    OFFER_CREATED            = "offer.created"
    OFFER_ACCEPTED           = "offer.accepted"
    BOOKING_INTENT_CREATED   = "booking_intent.created"
    UNIT_HELD                = "unit.held"
    UNIT_HOLD_RELEASED       = "unit.hold_released"
    BOOKING_CREATED          = "booking.created"
    BOOKING_CONFIRMED        = "booking.confirmed"
    BOOKING_CANCELLED        = "booking.cancelled"
    PAYMENT_RECEIVED         = "payment.received"
    PAYMENT_FAILED           = "payment.failed"
    REFUND_ISSUED            = "refund.issued"
    DEAL_WON                 = "deal.won"
    DEAL_LOST                = "deal.lost"


# ---------------------------------------------------------------------------
# 1. SALES PIPELINE CONFIGURATION
# ---------------------------------------------------------------------------

class SalesPipeline(Base, TimestampMixin, SoftDeleteMixin):
    """
    Organization-configurable sales pipeline definition.
    One organization may have multiple pipelines (Residential, Commercial, Rental, etc.).
    """
    __tablename__ = "sales_pipelines"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pipeline_type: Mapped[str] = mapped_column(String(50), default="RESIDENTIAL_SALES", nullable=False)
    # RESIDENTIAL_SALES | COMMERCIAL | RENTAL | INVESTOR | DEVELOPER_CHANNEL
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    stage_configs: Mapped[List["PipelineStageConfig"]] = relationship(
        "PipelineStageConfig", back_populates="pipeline",
        cascade="all, delete-orphan", order_by="PipelineStageConfig.position"
    )

    __table_args__ = (
        Index("ix_sales_pipelines_org_active", "organization_id", "is_active"),
        Index("ix_sales_pipelines_org_type", "organization_id", "pipeline_type"),
    )


class PipelineStageConfig(Base, TimestampMixin):
    """
    Organization-configurable stage definition within a pipeline.
    Maps a display label to a canonical semantic_type from OpportunityStage.
    Historical opportunity records retain the pipeline_version under which they operated.
    """
    __tablename__ = "pipeline_stage_configs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pipeline_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_pipelines.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)     # Display label (org-customizable)
    semantic_type: Mapped[str] = mapped_column(String(50), nullable=False)  # OpportunityStage constant — immutable
    color: Mapped[str] = mapped_column(String(7), default="#3B82F6", nullable=False)
    # SLA in hours for this stage
    sla_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # JSON: list of required field names before leaving this stage
    required_fields: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    # JSON: list of allowed action types in this stage
    allowed_actions: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    pipeline: Mapped["SalesPipeline"] = relationship("SalesPipeline", back_populates="stage_configs")

    __table_args__ = (
        UniqueConstraint("pipeline_id", "semantic_type", name="uq_stage_config_pipeline_semantic"),
        Index("ix_stage_config_pipeline_pos", "pipeline_id", "position"),
    )


# ---------------------------------------------------------------------------
# 2. OPPORTUNITY STAGE HISTORY
# ---------------------------------------------------------------------------

class OpportunityStageHistory(Base):
    """
    Immutable record of every stage transition on a Deal/Opportunity.
    Append-only — never update or delete.
    Answers: who moved this opportunity from stage A to B, when, why, from what source?
    """
    __tablename__ = "opportunity_stage_history"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    pipeline_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("sales_pipelines.id", ondelete="SET NULL"), nullable=True)
    pipeline_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    from_stage: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    to_stage: Mapped[str] = mapped_column(String(50), nullable=False)
    changed_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    changed_by_type: Mapped[str] = mapped_column(String(20), default="HUMAN", nullable=False)
    # HUMAN | AI_AGENT | WORKFLOW | SYSTEM
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # MANUAL | APPOINTMENT | SITE_VISIT | OFFER | BOOKING | WORKFLOW | AI_RECOMMENDATION
    duration_hours_in_previous_stage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Analytics contract: entered_at / exited_at for stage duration analysis
    entered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    exited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    # Snapshot of key deal fields at transition time — never mutate historical records
    snapshot: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)

    __table_args__ = (
        Index("ix_opp_stage_hist_deal_at", "deal_id", "changed_at"),
        Index("ix_opp_stage_hist_org_stage", "organization_id", "to_stage"),
    )


# ---------------------------------------------------------------------------
# 3. PROPERTY SHORTLIST
# ---------------------------------------------------------------------------

class PropertyShortlist(Base, TimestampMixin):
    """
    Per-opportunity record of every property/unit shown to or shortlisted by a customer.
    Preserves complete property interest history — never overwrite past interactions.
    One customer may compare multiple properties before selecting.
    """
    __tablename__ = "property_shortlists"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Either project_id or unit_id or both
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # Legacy fallback: old PropertyListing model
    property_listing_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(30), default=PropertyShortlistStatus.SHORTLISTED, nullable=False, index=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    added_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    added_by_type: Mapped[str] = mapped_column(String(20), default="HUMAN", nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # AI_RECOMMENDATION | AGENT_MANUAL | CUSTOMER_REQUEST | SITE_VISIT | MARKETING

    # Dismissal / rejection details
    dismissed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissal_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Property snapshot at time of shortlisting (price may change later)
    property_snapshot: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_shortlist_deal_status", "deal_id", "status"),
        Index("ix_shortlist_org_unit", "organization_id", "unit_id"),
    )


# ---------------------------------------------------------------------------
# 4. SITE VISIT
# ---------------------------------------------------------------------------

class SiteVisit(Base, TimestampMixin, SoftDeleteMixin):
    """
    Canonical Site Visit entity — one first-class record per physical/virtual visit.
    Links the commercial opportunity to the calendar appointment, the property, and the outcome.

    A SiteVisit is NOT the same as a SchedulingMeeting. The meeting is the calendar event.
    The SiteVisit is the commercial record of the visit outcome linked to the opportunity.

    One opportunity may have multiple site visits (Section 27 of Build 08 spec).
    """
    __tablename__ = "site_visits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Commercial linkage
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # Property linkage
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # Legacy fallback
    property_listing_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # Calendar linkage (optional — visit may happen without calendar sync)
    scheduling_meeting_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    # Scheduling
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    timezone: Mapped[str] = mapped_column(String(100), default="UTC", nullable=False)

    # Location
    meeting_point: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    location_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    location_type: Mapped[str] = mapped_column(String(30), default="PHYSICAL", nullable=False)
    # PHYSICAL | VIRTUAL | PHONE

    # Assignment
    assigned_agent_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)

    # Status lifecycle
    status: Mapped[str] = mapped_column(
        String(30),
        default=SiteVisitStatus.REQUESTED,
        nullable=False,
        index=True
    )

    # Attendance tracking
    check_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    attendance_status: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # ATTENDED | NO_SHOW | PARTIAL | RESCHEDULED_ON_ARRIVAL

    # Visit number for this opportunity (1st visit, 2nd visit, etc.)
    visit_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Idempotency
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    outcome: Mapped[Optional["SiteVisitOutcome"]] = relationship(
        "SiteVisitOutcome", back_populates="site_visit",
        uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_site_visits_deal_status", "deal_id", "status"),
        Index("ix_site_visits_org_scheduled", "organization_id", "scheduled_at"),
        Index("ix_site_visits_org_status", "organization_id", "status"),
    )


class SiteVisitOutcome(Base, TimestampMixin):
    """
    Structured outcome captured after a site visit is completed.
    Only from actual customer/agent input — never inferred.
    """
    __tablename__ = "site_visit_outcomes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    site_visit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("site_visits.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Structured customer response
    customer_interest_level: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 1-5
    customer_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    preferred_property_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    preferred_unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Objections and signals
    objections: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)
    positive_signals: Mapped[Optional[List]] = mapped_column(JSONBType, default=list, nullable=True)

    # Next action
    next_action: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    next_action_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Agent notes (separate from customer feedback)
    agent_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Who recorded this outcome
    recorded_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    site_visit: Mapped["SiteVisit"] = relationship("SiteVisit", back_populates="outcome")

    __table_args__ = (
        Index("ix_site_visit_outcomes_org", "organization_id"),
    )


# ---------------------------------------------------------------------------
# 5. NEGOTIATION ROUNDS (IMMUTABLE APPEND-ONLY)
# ---------------------------------------------------------------------------

class NegotiationRound(Base):
    """
    Immutable record of every offer, counter-offer, and response in a negotiation.
    Never update or delete — create a new round for each commercial communication.
    This replaces the JSONB offer_history blob on DealOffer.

    Full negotiation timeline example:
      Round 1: asking_price = 1.50 Cr (DEVELOPER, source=PRICE_BOOK)
      Round 2: offer = 1.35 Cr (CUSTOMER, source=WHATSAPP)
      Round 3: counter = 1.43 Cr (AGENT, source=HUMAN)
    """
    __tablename__ = "negotiation_rounds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    round_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # ASKING_PRICE | CUSTOMER_OFFER | AGENT_COUNTER | ACCEPTANCE | REJECTION | WITHDRAWAL

    actor: Mapped[str] = mapped_column(String(30), nullable=False)
    # NegotiationRoundActor: CUSTOMER | AGENT | MANAGER | DEVELOPER | AI_DRAFT
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Price in original currency — NEVER float
    price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="AED", nullable=False)
    original_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    # original_price = list price at time of this round — separate from negotiated price

    # Payment terms offered in this round
    payment_plan: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    payment_terms: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)

    # Human-readable notes or message extract
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # WHATSAPP | EMAIL | PHONE | IN_PERSON | AI_DRAFT | SYSTEM

    # Whether this round requires human review before sending
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    __table_args__ = (
        UniqueConstraint("deal_id", "round_number", name="uq_negotiation_round_number"),
        Index("ix_neg_rounds_deal_at", "deal_id", "occurred_at"),
        Index("ix_neg_rounds_org", "organization_id"),
    )


# ---------------------------------------------------------------------------
# 6. BOOKING INTENT
# ---------------------------------------------------------------------------

class BookingIntent(Base, TimestampMixin):
    """
    Explicit booking intent — the state between 'customer says yes' and 'booking confirmed'.
    This prevents prematurely recording BOOKED status before inventory, payment,
    and authorization requirements are satisfied.

    AI may PROPOSE a BookingIntent. Only the booking workflow produces DealBooking.
    """
    __tablename__ = "booking_intents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # Property / unit
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    property_listing_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Commercial terms at time of intent
    intended_price: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="AED", nullable=False)
    intended_payment_terms: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Lifecycle
    status: Mapped[str] = mapped_column(String(30), default=BookingIntentStatus.CREATED, nullable=False, index=True)
    created_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_by_type: Mapped[str] = mapped_column(String(20), default="HUMAN", nullable=False)

    # Expiry — intent must not be used after this time without re-verification
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    # Reference to the DealBooking once converted (nullable until conversion)
    converted_booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Source of intent
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # AGENT_MANUAL | AI_PROPOSAL | CUSTOMER_INITIATED | SITE_VISIT_OUTCOME

    # Idempotency
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_booking_intents_deal_status", "deal_id", "status"),
        Index("ix_booking_intents_org_status", "organization_id", "status"),
        Index("ix_booking_intents_expires", "expires_at"),
    )


# ---------------------------------------------------------------------------
# 7. UNIT HOLD
# ---------------------------------------------------------------------------

class UnitHold(Base, TimestampMixin):
    """
    Temporary inventory hold linking the commercial deal to a specific ProjectUnit.
    Enforces: one hold per unit at a time (exclusive lock via DB constraint).
    Backend-managed TTL — never rely on browser timers.

    Flow:
      BOOKING INTENT -> UNIT AVAILABILITY CHECK -> UNIT HOLD -> EXPIRY TIMER -> BOOKING
    """
    __tablename__ = "unit_holds"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    unit_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    # unit_id references project_units.id — FK not enforced at DB level for cross-module safety
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_intent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    status: Mapped[str] = mapped_column(String(20), default=UnitHoldStatus.ACTIVE, nullable=False, index=True)
    created_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # TTL
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Audit
    released_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    released_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    release_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    converted_to_reservation_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Idempotency
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)

    __table_args__ = (
        # Only one ACTIVE hold per unit per organization at a time
        UniqueConstraint(
            "organization_id", "unit_id", "status",
            name="uq_unit_hold_active_per_unit"
        ),
        Index("ix_unit_holds_unit_status", "unit_id", "status"),
        Index("ix_unit_holds_org_expires", "organization_id", "expires_at"),
    )


# ---------------------------------------------------------------------------
# 8. PROPERTY PAYMENT TRANSACTION
# ---------------------------------------------------------------------------

class PropertyPaymentTransaction(Base, TimestampMixin):
    """
    Real-estate property payment — SEPARATE from platform billing (PaymentOrder/PaymentTransaction).
    Records actual money movement for property bookings, token amounts, and installments.

    IMPORTANT:
    - Never mark payment as successful based only on frontend response.
    - Payment status must be reconciled from authoritative provider webhook events.
    - All monetary amounts use Decimal (Numeric(20,4)) — never Float.
    """
    __tablename__ = "property_payment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Commercial linkage
    deal_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("deals.id", ondelete="CASCADE"), nullable=False, index=True)
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # booking_id references deal_bookings.id

    # Payment details
    payment_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # TOKEN | DOWN_PAYMENT | INSTALLMENT | FULL_PAYMENT | PARTIAL | REFUND

    amount: Mapped[Decimal] = mapped_column(MoneyType, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)

    # Provider details (reconciled from webhook — not from frontend)
    payment_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    # RAZORPAY | STRIPE | BANK_TRANSFER | CHEQUE | CASH | OFFLINE
    provider_payment_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    provider_order_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    provider_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    # provider_event_id is the webhook event ID — idempotency key for duplicate webhooks

    # Status — set only from provider webhook verification
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    # INITIATED | PENDING | AUTHORIZED | CAPTURED | FAILED | CANCELLED | REFUNDED

    # Timestamps from provider (authoritative)
    provider_created_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Failure details
    failure_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failure_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Refund linkage
    original_transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    refund_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    refund_approved_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Idempotency
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)

    # Audit
    recorded_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    recorded_by_type: Mapped[str] = mapped_column(String(20), default="SYSTEM", nullable=False)

    __table_args__ = (
        Index("ix_prop_payments_deal_status", "deal_id", "status"),
        Index("ix_prop_payments_org_status", "organization_id", "status"),
        Index("ix_prop_payments_provider_id", "provider_payment_id"),
    )


# ---------------------------------------------------------------------------
# 9. REVENUE EVENT (IMMUTABLE APPEND-ONLY)
# ---------------------------------------------------------------------------

class RevenueEvent(Base):
    """
    Immutable append-only revenue event log.
    Every material commercial event must produce a RevenueEvent.
    These events are the primary input for Build 09 revenue intelligence.

    CRITICAL:
    - Never rewrite historical monetary events to fix dashboards.
    - Create correction/reversal events instead.
    - Every event includes data lineage: lead -> opportunity -> property -> unit -> payment.
    """
    __tablename__ = "revenue_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Unique event identifier (idempotency key for replay)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True, default=lambda: str(uuid.uuid4()))
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # RevenueEventType constants

    # Data lineage — full provenance chain
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    opportunity_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    # opportunity_id = deal_id from deals table
    site_visit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    booking_intent_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Financial data (nullable — not all events have monetary value)
    amount: Mapped[Optional[Decimal]] = mapped_column(MoneyType, nullable=True)
    currency: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)

    # Source and actor
    source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    actor_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    actor_type: Mapped[str] = mapped_column(String(20), default="SYSTEM", nullable=False)

    # Structured payload (must not contain secrets)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    # Version for event schema evolution
    schema_version: Mapped[str] = mapped_column(String(20), default="v1", nullable=False)

    # Immutable timestamp — set once, never updated
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    __table_args__ = (
        Index("ix_revenue_events_org_type", "organization_id", "event_type"),
        Index("ix_revenue_events_org_time", "organization_id", "occurred_at"),
        Index("ix_revenue_events_lead", "lead_id"),
        Index("ix_revenue_events_opportunity", "opportunity_id"),
    )


# ---------------------------------------------------------------------------
# 10. BOOKING RECONCILIATION
# ---------------------------------------------------------------------------

class BookingReconciliationTask(Base, TimestampMixin):
    """
    Operational reconciliation record for inconsistencies between:
    - Booking exists but inventory not updated
    - Payment received but booking not confirmed
    - Booking recorded but payment evidence missing
    - Opportunity marked WON but no booking evidence

    These are created automatically when inconsistencies are detected.
    They must be resolved before the state is considered authoritative.
    """
    __tablename__ = "booking_reconciliation_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    inconsistency_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # BOOKING_WITHOUT_INVENTORY | PAYMENT_WITHOUT_BOOKING | BOOKING_WITHOUT_PAYMENT
    # OPPORTUNITY_WON_WITHOUT_BOOKING | UNIT_BOOKED_WITHOUT_DEAL | HOLD_EXPIRED_WITH_ACTIVE_BOOKING

    deal_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    booking_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    unit_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    payment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[Optional[Dict]] = mapped_column(JSONBType, nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="OPEN", nullable=False, index=True)
    # OPEN | IN_PROGRESS | RESOLVED | ESCALATED | ACKNOWLEDGED

    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_by_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Severity
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)
    # LOW | MEDIUM | HIGH | CRITICAL

    __table_args__ = (
        Index("ix_recon_tasks_org_status", "organization_id", "status"),
        Index("ix_recon_tasks_deal", "deal_id"),
    )
