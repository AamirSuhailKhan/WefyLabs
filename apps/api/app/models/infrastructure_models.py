"""
PART 6 — Enterprise Infrastructure Models
==========================================
New SQLAlchemy models for: TimelineEvent, NotificationPreference,
WebhookDelivery, Integration, IntegrationCredential, FeatureFlag,
Setting, EventHistory, BackgroundJob, SystemHealthSnapshot.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


# ─── Timeline Events ──────────────────────────────────────────────────────────

class TimelineEvent(Base):
    """
    Immutable unified activity timeline for any CRM object (lead, contact, property, deal).
    Merged from: Activities, Messages, Notes, Meetings, AI Actions, Workflow Executions.
    Ordered newest-first. Never deleted.
    """
    __tablename__ = "timeline_events"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    workspace_id = mapped_column(String(36), nullable=True, index=True)
    resource_type = mapped_column(String(50), nullable=False, index=True)   # lead | contact | property | deal
    resource_id = mapped_column(String(36), nullable=False, index=True)
    event_type = mapped_column(String(80), nullable=False, index=True)      # note_added | stage_changed | message_sent | ai_qualified
    channel = mapped_column(String(30), nullable=True)                       # whatsapp | email | phone | system | ai
    actor_id = mapped_column(String(36), nullable=True)
    actor_type = mapped_column(String(20), default="user", nullable=False)  # user | system | ai | webhook
    title = mapped_column(String(255), nullable=False)
    body = mapped_column(Text, nullable=True)
    event_metadata = mapped_column(JSONBType, default=dict, nullable=False)
    correlation_id = mapped_column(String(64), nullable=True, index=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_timeline_resource", "resource_type", "resource_id", "created_at"),
        Index("ix_timeline_org_type", "organization_id", "event_type"),
    )


# ─── Notification Preferences ─────────────────────────────────────────────────

class NotificationPreference(Base):
    """Per-user, per-channel notification preferences with mute, schedule, and priority."""
    __tablename__ = "notification_preferences"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    user_id = mapped_column(String(36), nullable=False, index=True)
    channel = mapped_column(String(30), nullable=False)                      # in_app | email | whatsapp | telegram | sms
    event_type = mapped_column(String(80), nullable=False)                   # lead.assigned | task.due | meeting.reminder
    is_enabled = mapped_column(Boolean, default=True, nullable=False)
    is_muted = mapped_column(Boolean, default=False, nullable=False)
    muted_until = mapped_column(DateTime(timezone=True), nullable=True)
    quiet_hours_start = mapped_column(String(5), nullable=True)              # "22:00"
    quiet_hours_end = mapped_column(String(5), nullable=True)                # "08:00"
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("user_id", "channel", "event_type", name="uq_notif_pref_user_channel_event"),
        Index("ix_notif_pref_org_user", "organization_id", "user_id"),
    )


# ─── Webhook Deliveries ───────────────────────────────────────────────────────

class WebhookDelivery(Base):
    """
    Outbound webhook delivery log. Tracks every attempt, response status, retry count.
    Supports admin replay for failed deliveries.
    """
    __tablename__ = "webhook_deliveries"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    webhook_subscription_id = mapped_column(String(36), nullable=True, index=True)
    event_type = mapped_column(String(80), nullable=False, index=True)
    target_url = mapped_column(String(500), nullable=False)
    payload = mapped_column(JSONBType, default=dict, nullable=False)
    request_headers = mapped_column(JSONBType, default=dict, nullable=True)
    response_status = mapped_column(Integer, nullable=True)
    response_body = mapped_column(Text, nullable=True)
    response_time_ms = mapped_column(Integer, nullable=True)
    status = mapped_column(String(20), default="pending", nullable=False, index=True)  # pending | delivered | failed | retrying
    retry_count = mapped_column(Integer, default=0, nullable=False)
    max_retries = mapped_column(Integer, default=5, nullable=False)
    next_retry_at = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason = mapped_column(Text, nullable=True)
    delivered_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_webhook_delivery_org_status", "organization_id", "status"),
        Index("ix_webhook_delivery_retry", "status", "next_retry_at"),
    )


# ─── Integrations ─────────────────────────────────────────────────────────────

class Integration(Base):
    """
    Integration registry. Each organization can connect external systems.
    Provider examples: google_calendar, hubspot, salesforce, stripe, twilio.
    """
    __tablename__ = "integrations"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=False, index=True)
    provider = mapped_column(String(50), nullable=False, index=True)         # google_calendar | hubspot | stripe | twilio
    display_name = mapped_column(String(100), nullable=False)
    status = mapped_column(String(20), default="pending", nullable=False)   # pending | connected | error | disconnected
    is_active = mapped_column(Boolean, default=True, nullable=False)
    config = mapped_column(JSONBType, default=dict, nullable=True)           # Non-sensitive provider config
    last_synced_at = mapped_column(DateTime(timezone=True), nullable=True)
    error_message = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("organization_id", "provider", name="uq_integration_org_provider"),
    )


class IntegrationCredential(Base):
    """
    Encrypted integration credentials (OAuth tokens, API secrets).
    Raw tokens NEVER stored. Encrypted at rest with AES-256.
    """
    __tablename__ = "integration_credentials"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    integration_id = mapped_column(String(36), nullable=False, index=True)
    credential_type = mapped_column(String(30), nullable=False)             # access_token | refresh_token | api_key | client_secret
    encrypted_value = mapped_column(Text, nullable=False)                   # AES-256 encrypted
    expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ─── Feature Flags ────────────────────────────────────────────────────────────

class FeatureFlag(Base):
    """
    Enterprise feature flag registry.
    Supports global, org, workspace, and user-level overrides.
    Used for: canary releases, beta programs, kill switches, A/B tests.
    """
    __tablename__ = "feature_flags"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    key = mapped_column(String(100), nullable=False, index=True)             # e.g. "ai_lead_scoring_v2"
    scope = mapped_column(String(20), default="global", nullable=False)     # global | organization | workspace | user
    scope_id = mapped_column(String(36), nullable=True, index=True)         # org_id | workspace_id | user_id
    is_enabled = mapped_column(Boolean, default=False, nullable=False)
    rollout_percentage = mapped_column(Float, default=100.0, nullable=False)
    environment = mapped_column(String(20), default="production", nullable=False)  # production | staging | development
    description = mapped_column(Text, nullable=True)
    flag_metadata = mapped_column(JSONBType, default=dict, nullable=True)
    expires_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("key", "scope", "scope_id", name="uq_feature_flag_key_scope"),
        Index("ix_feature_flag_key_scope", "key", "scope", "scope_id"),
    )


# ─── Settings ─────────────────────────────────────────────────────────────────

class Setting(Base):
    """
    Hierarchical settings store. Inheritance: global → organization → workspace → user.
    Typed values serialized as JSON. Supports hot-reload via cache invalidation.
    """
    __tablename__ = "settings"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    key = mapped_column(String(150), nullable=False, index=True)
    scope = mapped_column(String(20), default="organization", nullable=False)  # global | organization | workspace | user
    scope_id = mapped_column(String(36), nullable=True, index=True)
    value = mapped_column(JSONBType, nullable=True)                          # Typed: str, int, bool, list, dict
    value_type = mapped_column(String(20), default="string")                # string | integer | boolean | json | list
    description = mapped_column(Text, nullable=True)
    is_sensitive = mapped_column(Boolean, default=False)                    # Mask in API responses
    updated_by = mapped_column(String(36), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("key", "scope", "scope_id", name="uq_setting_key_scope"),
        Index("ix_setting_scope_id", "scope", "scope_id"),
    )


# ─── Event History ────────────────────────────────────────────────────────────

class EventHistory(Base):
    """
    Persistent domain event store. Every DomainEvent is written here.
    Supports replay for analytics rebuilds, RAG re-indexing, and debugging.
    """
    __tablename__ = "event_history"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    event_id = mapped_column(String(64), unique=True, nullable=False, index=True)
    event_type = mapped_column(String(100), nullable=False, index=True)
    event_version = mapped_column(String(10), default="1.0", nullable=False)
    organization_id = mapped_column(String(36), nullable=True, index=True)
    correlation_id = mapped_column(String(64), nullable=True, index=True)
    producer = mapped_column(String(100), nullable=True)                     # service that emitted the event
    actor_id = mapped_column(String(36), nullable=True)
    actor_type = mapped_column(String(20), default="system")
    payload = mapped_column(JSONBType, default=dict, nullable=False)
    processing_status = mapped_column(String(20), default="processed", nullable=False, index=True)  # processed | failed | replaying
    retry_count = mapped_column(Integer, default=0, nullable=False)
    failure_reason = mapped_column(Text, nullable=True)
    subscribers_notified = mapped_column(JSONBType, default=list, nullable=True)
    published_at = mapped_column(DateTime(timezone=True), nullable=False)
    processed_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_event_history_org_type", "organization_id", "event_type"),
        Index("ix_event_history_status", "processing_status", "created_at"),
    )


# ─── Background Jobs ──────────────────────────────────────────────────────────

class BackgroundJob(Base):
    """
    Job registry for tracking all background, scheduled, and delayed jobs.
    Provides visibility and manual retry capability for ops teams.
    """
    __tablename__ = "background_jobs"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = mapped_column(String(36), nullable=True, index=True)
    job_type = mapped_column(String(80), nullable=False, index=True)         # lead.score | ai.qualify | export.csv | email.dispatch
    queue_name = mapped_column(String(50), nullable=False, index=True)
    celery_task_id = mapped_column(String(255), nullable=True, unique=True, index=True)
    status = mapped_column(String(20), default="queued", nullable=False, index=True)  # queued | running | completed | failed | retrying | dead
    priority = mapped_column(Integer, default=5, nullable=False)            # 1=highest, 10=lowest
    payload = mapped_column(JSONBType, default=dict, nullable=False)
    result = mapped_column(JSONBType, nullable=True)
    error_message = mapped_column(Text, nullable=True)
    retry_count = mapped_column(Integer, default=0, nullable=False)
    max_retries = mapped_column(Integer, default=3, nullable=False)
    scheduled_at = mapped_column(DateTime(timezone=True), nullable=True)
    started_at = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at = mapped_column(DateTime(timezone=True), nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_bg_job_org_status", "organization_id", "status"),
        Index("ix_bg_job_queue_status", "queue_name", "status"),
    )


# ─── System Health Snapshots ──────────────────────────────────────────────────

class SystemHealthSnapshot(Base):
    """Periodic system health snapshots for ops dashboards and alerting."""
    __tablename__ = "system_health_snapshots"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    status = mapped_column(String(20), nullable=False)                      # healthy | degraded | unhealthy
    database_ok = mapped_column(Boolean, default=True)
    redis_ok = mapped_column(Boolean, default=True)
    queue_ok = mapped_column(Boolean, default=True)
    storage_ok = mapped_column(Boolean, default=True)
    worker_count = mapped_column(Integer, default=0)
    api_version = mapped_column(String(20), nullable=True)
    details = mapped_column(JSONBType, default=dict, nullable=True)
    recorded_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
