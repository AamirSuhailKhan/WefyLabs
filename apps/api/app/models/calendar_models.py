"""
Volume 2 PART 9 — Calendar, Meeting, Viewing & Scheduling Intelligence Engine Models
=====================================================================================
SQLAlchemy 2.0 models for calendar accounts, availability rules, temporary booking holds,
meetings, property viewings, AI preparation briefs, outcomes, no-show predictions, and conflicts.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index,
    UniqueConstraint, ForeignKey, Uuid
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")
UUIDType = Uuid(as_uuid=True)

def _gen_uuid() -> str:
    return str(uuid.uuid4())


class CalendarAccount(Base, TimestampMixin):
    """
    Connected external calendar account (Google, Microsoft Graph, Apple CalDAV).
    Tokens are stored securely in encrypted format.
    """
    __tablename__ = "calendar_accounts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(30), default="GOOGLE", nullable=False) # GOOGLE | MICROSOFT_GRAPH | APPLE_CALDAV | CUSTOM
    account_email: Mapped[str] = mapped_column(String(255), nullable=False)
    encrypted_access_token: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_refresh_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_connected: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    sync_cursor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    connections: Mapped[List["CalendarConnection"]] = relationship("CalendarConnection", back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("broker_id", "account_email", name="uq_broker_account_email"),
    )


class CalendarConnection(Base, TimestampMixin):
    """
    Specific calendar within an account (e.g. Primary, Work, Team, Personal).
    """
    __tablename__ = "calendar_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    calendar_account_id: Mapped[str] = mapped_column(String(36), ForeignKey("calendar_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    external_calendar_id: Mapped[str] = mapped_column(String(255), nullable=False)
    calendar_name: Mapped[str] = mapped_column(String(255), nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)  # Set from lead.market→country timezone via TimezoneService
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_write_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    account: Mapped["CalendarAccount"] = relationship("CalendarAccount", back_populates="connections")
    events: Mapped[List["CalendarEvent"]] = relationship("CalendarEvent", back_populates="connection", cascade="all, delete-orphan")


class AvailabilityRule(Base, TimestampMixin):
    """
    Recurring working hours and appointment availability windows per broker.
    """
    __tablename__ = "availability_rules"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False) # 0=Sunday, 1=Monday... 6=Saturday
    start_time: Mapped[str] = mapped_column(String(10), default="09:00", nullable=False)
    end_time: Mapped[str] = mapped_column(String(10), default="18:00", nullable=False)
    timezone: Mapped[str] = mapped_column(String(100), nullable=False)  # Set from broker.organization→market timezone via TimezoneService
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_avail_rule_broker_day", "broker_id", "day_of_week"),
    )


class MeetingHold(Base, TimestampMixin):
    """
    Temporary 5-minute booking hold to prevent race conditions and double bookings.
    """
    __tablename__ = "meeting_holds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    broker_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    slot_start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    slot_end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_released: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    __table_args__ = (
        Index("ix_hold_broker_slot", "broker_id", "slot_start_utc", "is_released"),
    )


class SchedulingMeeting(Base, TimestampMixin):
    """
    Canonical Meeting / Appointment entity for site visits, calls, and consultations.
    """
    __tablename__ = "scheduling_meetings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUIDType, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    meeting_type: Mapped[str] = mapped_column(String(40), default="PROPERTY_VIEWING", nullable=False) # PROPERTY_VIEWING | SITE_VISIT | CALL | VIDEO_CALL | OFFICE_MEETING
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="CONFIRMED", nullable=False) # REQUESTED | HELD | CONFIRMED | RESCHEDULED | CANCELLED | COMPLETED | NO_SHOW
    start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    customer_timezone: Mapped[str] = mapped_column(String(100), nullable=False)  # Resolved by TimezoneService.resolve() — never defaults to Asia/Dubai
    broker_timezone: Mapped[str] = mapped_column(String(100), nullable=False)      # Resolved by TimezoneService.resolve() — never defaults to Asia/Dubai
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    buffer_minutes_before: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    buffer_minutes_after: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    location_type: Mapped[str] = mapped_column(String(50), default="PROPERTY", nullable=False)
    location_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    virtual_provider: Mapped[str] = mapped_column(String(40), default="NONE", nullable=False) # GOOGLE_MEET | MICROSOFT_TEAMS | ZOOM | NONE
    meeting_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    external_event_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True)

    viewing: Mapped[Optional["Viewing"]] = relationship("Viewing", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    preparation_brief: Mapped[Optional["MeetingPreparationBrief"]] = relationship("MeetingPreparationBrief", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    outcome: Mapped[Optional["MeetingOutcome"]] = relationship("MeetingOutcome", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    no_show_prediction: Mapped[Optional["NoShowPrediction"]] = relationship("NoShowPrediction", back_populates="meeting", uselist=False, cascade="all, delete-orphan")
    reminders: Mapped[List["MeetingReminder"]] = relationship("MeetingReminder", back_populates="meeting", cascade="all, delete-orphan")
    conflicts: Mapped[List["CalendarConflict"]] = relationship("CalendarConflict", back_populates="meeting", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_mtg_org_start", "organization_id", "start_utc"),
        Index("ix_mtg_broker_start", "broker_id", "start_utc"),
    )


# Alias for backward-compatible module references
Meeting = SchedulingMeeting


class Viewing(Base, TimestampMixin):
    """
    On-site property viewing metadata linking meeting to property and building access rules.
    """
    __tablename__ = "viewings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("scheduling_meetings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    property_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    unit_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    access_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    key_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    security_preclearance: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_multi_property: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    itinerary_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    meeting: Mapped["SchedulingMeeting"] = relationship("SchedulingMeeting", back_populates="viewing")


class MeetingPreparationBrief(Base, TimestampMixin):
    """
    Internal AI briefing document prepared for the sales agent prior to the meeting.
    """
    __tablename__ = "meeting_preparation_briefs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("scheduling_meetings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    buyer_summary: Mapped[str] = mapped_column(Text, nullable=False)
    verified_budget: Mapped[str] = mapped_column(String(100), nullable=False)
    key_objections: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    recommended_properties: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    suggested_questions: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    next_best_action: Mapped[str] = mapped_column(String(255), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    meeting: Mapped["SchedulingMeeting"] = relationship("SchedulingMeeting", back_populates="preparation_brief")


class MeetingOutcome(Base, TimestampMixin):
    """
    Structured outcome recording post-meeting feedback, buyer interest level, and next steps.
    """
    __tablename__ = "meeting_outcomes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("scheduling_meetings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    outcome_category: Mapped[str] = mapped_column(String(50), default="INTERESTED", nullable=False) # INTERESTED | VERY_INTERESTED | NEEDS_FOLLOW_UP | NOT_INTERESTED | NEGOTIATION | CONVERTED | NO_SHOW
    buyer_interest_level: Mapped[int] = mapped_column(Integer, default=3, nullable=False) # 1 to 5
    detailed_feedback: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    agreed_next_step: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    next_follow_up_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    agent_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    meeting: Mapped["SchedulingMeeting"] = relationship("SchedulingMeeting", back_populates="outcome")


class NoShowPrediction(Base, TimestampMixin):
    """
    Probabilistic no-show risk assessment and preventative confirmation triggers.
    """
    __tablename__ = "no_show_predictions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("scheduling_meetings.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    no_show_probability: Mapped[float] = mapped_column(Float, default=0.1, nullable=False) # 0.0 to 1.0
    risk_level: Mapped[str] = mapped_column(String(20), default="LOW", nullable=False) # LOW | MEDIUM | HIGH
    confidence: Mapped[float] = mapped_column(Float, default=0.9, nullable=False)
    influencing_factors: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    preventative_action: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    meeting: Mapped["SchedulingMeeting"] = relationship("SchedulingMeeting", back_populates="no_show_prediction")


class MeetingReminder(Base, TimestampMixin):
    """
    Scheduled reminder messages before a meeting (e.g. 24h, 2h, 30m prior).
    """
    __tablename__ = "meeting_reminders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("scheduling_meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    offset_minutes: Mapped[int] = mapped_column(Integer, nullable=False) # 1440, 120, 30
    channel: Mapped[str] = mapped_column(String(30), default="WHATSAPP", nullable=False)
    scheduled_for_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    meeting: Mapped["SchedulingMeeting"] = relationship("SchedulingMeeting", back_populates="reminders")


class CalendarEvent(Base, TimestampMixin):
    """
    External calendar event cache used for busy/free slot calculation.
    """
    __tablename__ = "calendar_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    connection_id: Mapped[str] = mapped_column(String(36), ForeignKey("calendar_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    start_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_busy: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    connection: Mapped["CalendarConnection"] = relationship("CalendarConnection", back_populates="events")

    __table_args__ = (
        Index("ix_cal_evt_range", "connection_id", "start_utc", "end_utc"),
    )


class CalendarConflict(Base, TimestampMixin):
    """
    Detected conflicts between BeetleLabs appointments and external calendar events.
    """
    __tablename__ = "calendar_conflicts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    meeting_id: Mapped[str] = mapped_column(String(36), ForeignKey("scheduling_meetings.id", ondelete="CASCADE"), nullable=False, index=True)
    external_event_id: Mapped[str] = mapped_column(String(255), nullable=False)
    conflict_description: Mapped[str] = mapped_column(Text, nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(50), default="DETECTED", nullable=False) # DETECTED | RESOLVED | IGNORED
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    meeting: Mapped["SchedulingMeeting"] = relationship("SchedulingMeeting", back_populates="conflicts")
