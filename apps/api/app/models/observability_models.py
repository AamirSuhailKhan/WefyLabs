"""
PART 8 — Enterprise Observability & Reliability Models
======================================================
SQLAlchemy models for: Incident, AlertRule, AlertHistory,
MetricSnapshot, PerformanceProfile, HealthCheckResult, CapacityForecast.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")


def _gen_uuid() -> str:
    return str(uuid.uuid4())


class Incident(Base):
    """
    Production Incident Tracking entity (P0, P1, P2, P3).
    Tracks detection, mitigation, resolution, root cause, and postmortem analysis.
    """
    __tablename__ = "incidents"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    incident_number = mapped_column(String(20), unique=True, nullable=False, index=True) # INC-1001
    title = mapped_column(String(255), nullable=False)
    severity = mapped_column(String(10), default="P2", nullable=False, index=True) # P0 | P1 | P2 | P3
    status = mapped_column(String(20), default="detected", nullable=False, index=True) # detected | investigating | mitigated | resolved
    service_affected = mapped_column(String(50), nullable=False, index=True)
    organization_id = mapped_column(String(36), nullable=True, index=True) # Optional tenant context
    detected_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    mitigated_at = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at = mapped_column(DateTime(timezone=True), nullable=True)
    owner_id = mapped_column(String(36), nullable=True)
    root_cause = mapped_column(Text, nullable=True)
    mitigation_steps = mapped_column(Text, nullable=True)
    postmortem_url = mapped_column(String(500), nullable=True)
    metadata_json = mapped_column(JSONBType, default=dict, nullable=False)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_incidents_sev_status", "severity", "status"),
    )


class AlertRule(Base):
    """Production Alert Rule definitions."""
    __tablename__ = "alert_rules"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    name = mapped_column(String(100), unique=True, nullable=False, index=True)
    metric_name = mapped_column(String(100), nullable=False, index=True)
    condition = mapped_column(String(10), default=">", nullable=False) # > | < | >= | <= | ==
    threshold = mapped_column(Float, nullable=False)
    severity = mapped_column(String(10), default="warning", nullable=False) # critical | warning | info
    is_enabled = mapped_column(Boolean, default=True, nullable=False)
    cooldown_minutes = mapped_column(Integer, default=15, nullable=False)
    description = mapped_column(Text, nullable=True)
    created_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class AlertHistory(Base):
    """Triggered Alert Execution History log."""
    __tablename__ = "alert_history"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    rule_id = mapped_column(String(36), nullable=False, index=True)
    rule_name = mapped_column(String(100), nullable=False)
    severity = mapped_column(String(10), nullable=False)
    metric_name = mapped_column(String(100), nullable=False)
    observed_value = mapped_column(Float, nullable=False)
    threshold_value = mapped_column(Float, nullable=False)
    status = mapped_column(String(20), default="firing", nullable=False, index=True) # firing | resolved | suppressed
    context = mapped_column(JSONBType, default=dict, nullable=False)
    fired_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    resolved_at = mapped_column(DateTime(timezone=True), nullable=True)


class MetricSnapshot(Base):
    """Periodic historical metric snapshot store for reporting and capacity forecasting."""
    __tablename__ = "metric_snapshots"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    metric_name = mapped_column(String(100), nullable=False, index=True)
    metric_type = mapped_column(String(20), default="gauge", nullable=False) # counter | gauge | histogram
    value = mapped_column(Float, nullable=False)
    tags = mapped_column(JSONBType, default=dict, nullable=False)
    recorded_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    __table_args__ = (
        Index("ix_metric_snapshots_name_time", "metric_name", "recorded_at"),
    )


class PerformanceProfile(Base):
    """Performance profiling records for API and DB slow path analysis."""
    __tablename__ = "performance_profiles"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    target_name = mapped_column(String(255), nullable=False, index=True) # Route path or DB Query pattern
    target_type = mapped_column(String(20), default="api", nullable=False) # api | database | queue | worker | ai
    count = mapped_column(Integer, default=1, nullable=False)
    p50_latency_ms = mapped_column(Float, nullable=False)
    p95_latency_ms = mapped_column(Float, nullable=False)
    p99_latency_ms = mapped_column(Float, nullable=False)
    error_rate_pct = mapped_column(Float, default=0.0, nullable=False)
    sample_context = mapped_column(JSONBType, default=dict, nullable=True)
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class HealthCheckResult(Base):
    """Historical record of subsystem health check executions."""
    __tablename__ = "health_check_results"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    subsystem = mapped_column(String(50), nullable=False, index=True) # database | redis | queue | search | ai | storage
    status = mapped_column(String(20), nullable=False) # healthy | degraded | unhealthy
    latency_ms = mapped_column(Float, nullable=False)
    details = mapped_column(JSONBType, default=dict, nullable=False)
    checked_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)


class CapacityForecast(Base):
    """Capacity forecasting store predicting resource exhaustion dates."""
    __tablename__ = "capacity_forecasts"

    id = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    resource_name = mapped_column(String(50), nullable=False, index=True) # db_storage | memory | ai_tokens | queue_backlog
    unit = mapped_column(String(20), nullable=False) # MB | GB | tokens | jobs
    current_value = mapped_column(Float, nullable=False)
    projected_30d = mapped_column(Float, nullable=False)
    projected_90d = mapped_column(Float, nullable=False)
    max_capacity = mapped_column(Float, nullable=False)
    exhaustion_estimated_date = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
