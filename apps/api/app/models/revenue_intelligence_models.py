"""
Part 11 — Revenue Intelligence Domain Models
=============================================
Two new tables that are WRITTEN TO only by the Revenue Intelligence Layer.
They are NEVER the authoritative source for any transactional fact.

1. RevenueFunnelSnapshot   — Periodic point-in-time funnel state per org.
                             Feeds trend charts and time-series comparisons.
2. RevenueLeakageEvent     — Immutable log entry when a lead exits the funnel
                             without converting. Evidence-based; pulled from
                             real lead/opportunity state — never fabricated.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON,
    Index, UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")


class RevenueFunnelSnapshot(Base, TimestampMixin):
    """
    Periodic point-in-time snapshot of the revenue funnel for a given org.

    Each row represents the state of the funnel at a specific calendar date.
    Snapshots are ADDITIVE — historical rows are never mutated.
    The `metrics` JSONB field stores all computed stage counts and rates
    so the schema stays stable even as funnel stages evolve.

    Uniqueness: one snapshot per (organization_id, snapshot_date, period_type).
    Upsert semantics: if a snapshot for today already exists, it is overwritten
    with fresher data (idempotent capture).
    """
    __tablename__ = "revenue_funnel_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    # Period granularity: DAILY | WEEKLY | MONTHLY
    period_type: Mapped[str] = mapped_column(String(20), default="DAILY", nullable=False)
    # The calendar date this snapshot represents (UTC date, stored as datetime at midnight)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # ── Funnel stage counts (also embedded in metrics for extensibility) ──────
    total_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads_contacted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads_qualified: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads_site_visit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads_negotiation: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads_converted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    leads_lost: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # ── Revenue counts ────────────────────────────────────────────────────────
    active_opportunities: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    # Estimated pipeline value = sum of budget_max for qualified+ leads (nullable — may be 0)
    estimated_pipeline_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Confirmed commission from completed deals in this org
    confirmed_revenue: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Extended metrics as JSONB (conversion rates, velocity, etc.) ─────────
    metrics: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "snapshot_date", "period_type", name="uq_funnel_snapshot_org_date_period"),
        Index("ix_funnel_snap_org_date", "organization_id", "snapshot_date"),
    )


class RevenueLeakageEvent(Base, TimestampMixin):
    """
    Immutable record that a lead exited the revenue funnel without converting.

    Created by LeakageDetector when it detects a lead in `lost` status or
    a lead that has been stale beyond the configured threshold.

    IMPORTANT:
    - This table is append-only. No updates. No deletes.
    - It does NOT alter the lead record. It is purely observational.
    - `leakage_reason` is a heuristic classification — not a definitive verdict.
    - `estimated_value_lost` is derived from lead.budget_max — always labelled
      as an estimate in API responses.
    """
    __tablename__ = "revenue_leakage_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # The pipeline stage the lead was in when leakage was detected
    lost_at_stage: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # How many days the lead was in that stage before leakage
    days_in_stage: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Heuristic reason category:
    # NO_CONTACT | NO_FOLLOW_UP | BUDGET_MISMATCH | STALE | EXPLICIT_LOSS | EXPIRED_OPPORTUNITY | UNKNOWN
    leakage_reason: Mapped[str] = mapped_column(String(50), default="UNKNOWN", nullable=False, index=True)
    # The lead's acquisition source channel at time of leakage
    source_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    # Upper-bound revenue estimate based on lead.budget_max (nullable — may not be set)
    # ALWAYS labelled as estimate in API responses
    estimated_value_lost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # The lead's score at time of leakage (hot/warm/cold)
    lead_score_at_loss: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    # Indicates whether any revenue opportunity existed for this lead
    had_open_opportunity: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # UTC datetime when the leakage was detected (not when the lead became lost)
    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("ix_leakage_org_stage", "organization_id", "lost_at_stage"),
        Index("ix_leakage_org_detected", "organization_id", "detected_at"),
        Index("ix_leakage_lead", "lead_id"),
    )
