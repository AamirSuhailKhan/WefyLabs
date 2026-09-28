import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean, JSON, Index
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.ext.mutable import MutableDict
from app.database import Base

class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Handles UUID objects AND string representations seamlessly in SQLite and PostgreSQL.
    """
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            if isinstance(value, uuid.UUID):
                return value
            try:
                return uuid.UUID(str(value))
            except (ValueError, TypeError):
                return value
        else:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, uuid.UUID):
            return value
        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError):
            return value

JSONBType = JSONB().with_variant(JSON(), "sqlite")
UUIDType = GUID()

def _gen_uuid():
    return str(uuid.uuid4())


class PipelineStage(Base):
    """Kanban pipeline stage belonging to an organization's workspace."""
    __tablename__ = "pipeline_stages"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    broker_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), nullable=True, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    name = Column(String(50), nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    color = Column(String(7), default="#3B82F6", nullable=False)
    is_default = Column(String(20), default="false")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class LeadNote(Base):
    """Rich text note attached to a lead, tenant-scoped."""
    __tablename__ = "lead_notes"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    lead_id = Column(UUIDType, ForeignKey("leads.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), nullable=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead")


class LeadTag(Base):
    """Taxonomy tag for lead segmentation, tenant-scoped."""
    __tablename__ = "lead_tags"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    broker_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), nullable=True, index=True)
    name = Column(String(50), nullable=False)
    color = Column(String(7), default="#6B7280", nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    leads = relationship("Lead", secondary="lead_tag_assignments")


class LeadTagAssignment(Base):
    """Junction mapping Leads to Tags."""
    __tablename__ = "lead_tag_assignments"

    lead_id = Column(UUIDType, ForeignKey("leads.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(String(36), ForeignKey("lead_tags.id", ondelete="CASCADE"), primary_key=True)


class Task(Base):
    """
    Canonical WorkItem — the single unified task/follow-up/action model.
    Build 07: Extended with type, source, idempotency_key, conversation_id,
    reason, and full provenance. Backward-compatible (new fields are nullable).
    """
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    broker_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(UUIDType, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    organization_id = Column(String(36), nullable=True, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    assigned_broker_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    due_at = Column(DateTime(timezone=True), nullable=True, index=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    status = Column(String(30), default="pending", nullable=False)
    # status values: pending | scheduled | ready | in_progress | completed | skipped | cancelled | failed | expired
    priority = Column(String(10), default="normal", nullable=False)  # low | normal | high | urgent
    reminder_sent = Column(Boolean, default=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # ── Build 07: WorkItem canonical extensions ──────────────────────────────
    # Type: controlled work item type (FOLLOW_UP, CALL_BACK, SEND_MESSAGE, etc.)
    task_type = Column(String(50), nullable=True, index=True)
    # Source: origin of this work item
    source = Column(String(50), nullable=True)  # CUSTOMER_REQUEST | AI_RECOMMENDATION | WORKFLOW | SYSTEM_SLA | ...
    # Idempotency: prevents duplicate work items from concurrent creation
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    # Correlation: links related work items across the trace
    correlation_id = Column(String(100), nullable=True, index=True)
    # Linked entities
    conversation_id = Column(String(36), nullable=True, index=True)
    identity_id = Column(String(36), nullable=True, index=True)
    opportunity_id = Column(String(36), nullable=True, index=True)
    # Reason: why this task exists (human-readable)
    reason = Column(Text, nullable=True)
    # Provenance: traceable back to originating event/message/action/workflow
    source_event_id = Column(String(100), nullable=True)
    source_message_id = Column(String(100), nullable=True)
    source_action_id = Column(String(100), nullable=True)
    source_workflow_id = Column(String(36), nullable=True)
    source_agent_run_id = Column(String(36), nullable=True)
    # Assignment
    assigned_team = Column(String(100), nullable=True)
    # Expiry
    expires_at = Column(DateTime(timezone=True), nullable=True)

    lead = relationship("Lead")

    __table_args__ = (
        Index("ix_tasks_org_status", "organization_id", "status"),
        Index("ix_tasks_broker_due", "broker_id", "due_at"),
        Index("ix_tasks_org_type", "organization_id", "task_type"),
        Index("ix_tasks_lead_type", "lead_id", "task_type"),
    )


# ── WorkItem type and source controlled vocabularies ────────────────────────
WORK_ITEM_TYPES = {
    "FOLLOW_UP", "CALL_BACK", "SEND_MESSAGE", "SEND_PROPERTY",
    "ASK_QUESTION", "APPOINTMENT_CONFIRMATION", "SITE_VISIT_CONFIRMATION",
    "POST_VISIT_FOLLOW_UP", "DOCUMENT_REQUEST", "DOCUMENT_REMINDER",
    "NEGOTIATION_FOLLOW_UP", "REENGAGEMENT", "HUMAN_HANDOFF", "INTERNAL_REVIEW",
}

WORK_ITEM_SOURCES = {
    "CUSTOMER_REQUEST", "AI_RECOMMENDATION", "WORKFLOW", "SYSTEM_SLA",
    "HUMAN_AGENT", "APPOINTMENT", "SITE_VISIT", "PROPERTY_INTERACTION",
    "REENGAGEMENT_RULE",
}

WORK_ITEM_STATUSES = {
    "pending", "scheduled", "ready", "in_progress",
    "completed", "skipped", "cancelled", "failed", "expired",
}


class Commitment(Base):
    """
    Build 07 — Promise / Commitment Engine.
    Tracks both company commitments ("I'll send the brochure in 10 minutes")
    and customer commitments ("I'll send documents tomorrow").
    Both are traceable. Neither is confused with the other.
    """
    __tablename__ = "commitments"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = Column(String(36), nullable=False, index=True)
    lead_id = Column(String(36), nullable=False, index=True)
    conversation_id = Column(String(36), nullable=True, index=True)
    source_message_id = Column(String(100), nullable=True)

    # Who made the commitment: COMPANY or CUSTOMER
    owner = Column(String(20), nullable=False)  # COMPANY | CUSTOMER

    # What was promised (structured + raw)
    commitment = Column(Text, nullable=False)
    commitment_type = Column(String(50), nullable=True)  # CALL_BACK | SEND_DOCUMENT | SEND_BROCHURE | VISIT | OTHER

    # Timing
    due_at = Column(DateTime(timezone=True), nullable=True, index=True)

    # Lifecycle
    status = Column(String(20), default="PENDING", nullable=False, index=True)
    # PENDING | FULFILLED | MISSED | CANCELLED | EXPIRED

    # If company commitment → linked work item
    work_item_id = Column(String(36), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)

    # Audit
    fulfilled_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_commitments_lead_status", "lead_id", "status"),
        Index("ix_commitments_org_due", "organization_id", "due_at"),
    )


class Meeting(Base):
    """
    Meeting / Appointment entity for client site visits and calls.
    Tenant-isolated. Emits MeetingBooked domain event on creation.
    """
    __tablename__ = "meetings"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    broker_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    lead_id = Column(UUIDType, ForeignKey("leads.id", ondelete="SET NULL"), nullable=True, index=True)
    organization_id = Column(String(36), nullable=True, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    title = Column(String(255), nullable=False)
    meeting_type = Column(String(30), default="site_visit", nullable=False)  # site_visit | call | video_call | office_meeting
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)
    duration_minutes = Column(Integer, default=60, nullable=False)
    location = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(String(20), default="scheduled", nullable=False)  # scheduled | completed | cancelled | no_show
    meeting_url = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    lead = relationship("Lead")

    __table_args__ = (
        Index("ix_meetings_org_scheduled", "organization_id", "scheduled_at"),
    )


class Contact(Base):
    """
    Contact entity distinct from Leads — vendors, consultants, legal contacts.
    Tenant-isolated for enterprise multi-tenancy.
    """
    __tablename__ = "contacts"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    broker_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), nullable=True, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True, index=True)
    phone = Column(String(20), nullable=True, index=True)
    contact_type = Column(String(30), default="vendor", nullable=False)  # vendor | consultant | developer | legal | other
    company = Column(String(255), nullable=True)
    position = Column(String(100), nullable=True)
    tags = Column(JSONBType, default=list, nullable=False)
    notes = Column(Text, nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_contacts_org_type", "organization_id", "contact_type"),
    )


class Activity(Base):
    """
    Immutable Activity Feed entry tracking every significant user action
    for CRM timeline display and AI context building.
    """
    __tablename__ = "activities"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = Column(String(36), nullable=True, index=True)
    workspace_id = Column(String(36), nullable=True, index=True)
    actor_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True, index=True)
    lead_id = Column(UUIDType, ForeignKey("leads.id", ondelete="CASCADE"), nullable=True, index=True)
    activity_type = Column(String(50), nullable=False, index=True)  # lead_created | stage_changed | task_completed | meeting_booked | note_added | call_made
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    activity_data = Column(JSONBType, default=dict, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_activities_org_type_created", "organization_id", "activity_type", "created_at"),
        Index("ix_activities_lead_created", "lead_id", "created_at"),
    )


class Notification(Base):
    """
    In-app and push notification entity for real-time alerts.
    Tenant-isolated, read-tracking, and category-tagged.
    """
    __tablename__ = "notifications"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    broker_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(String(36), nullable=True, index=True)
    category = Column(String(30), default="system", nullable=False)  # lead | deal | task | meeting | billing | system
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    action_url = Column(String(500), nullable=True)
    is_read = Column(Boolean, default=False, nullable=False, index=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        Index("ix_notifications_broker_read", "broker_id", "is_read"),
    )


# WebhookSubscription is already defined in app.models.developer_models (table: webhook_subscriptions).
# Import it from there: from app.models.developer_models import WebhookSubscription


class ApiKey(Base):
    """
    API Key entity for machine-to-machine authentication.
    Keys are hashed (SHA-256) before storage — never stored in plaintext.
    """
    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = Column(String(36), nullable=False, index=True)
    broker_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    key_hash = Column(String(64), unique=True, nullable=False)  # SHA-256 hash of the API key
    key_prefix = Column(String(10), nullable=False)  # First 8 chars for display (e.g. "bl_a1b2c3")
    scopes = Column(JSONBType, default=list, nullable=False)  # ["leads:read", "tasks:write"]
    is_active = Column(Boolean, default=True, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        Index("ix_api_keys_org_active", "organization_id", "is_active"),
    )


class CustomField(Base):
    """
    Schema for organization-defined custom fields on Leads and Contacts.
    Enables per-tenant data extensibility without schema migrations.
    """
    __tablename__ = "custom_fields"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = Column(String(36), nullable=False, index=True)
    entity_type = Column(String(30), nullable=False)  # lead | contact | property | deal
    field_name = Column(String(100), nullable=False)
    field_label = Column(String(100), nullable=False)
    field_type = Column(String(20), nullable=False)  # text | number | date | boolean | select | multi_select
    field_options = Column(JSONBType, default=list, nullable=True)  # For select/multi_select
    is_required = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

