"""
Volume 2 PART 10 — CRM Intelligence & Autonomous Sales Operations Engine Models
===============================================================================
SQLAlchemy 2.0 models for:
1. LeadHealthSnapshot        — Multi-dimensional health state (HEALTHY, COOLING, AT_RISK, NEGLECTED, etc.)
2. LeadRisk                  — Individual operational risks (severity, confidence, evidence)
3. SlaPolicy                 — Configurable tenant SLA policies (First Response, Viewing Follow-up)
4. SlaInstance               — Active SLA tracking timers per lead/activity
5. SlaBreach                 — Recorded SLA breach events with responsible broker & duration
6. PipelineHealthSnapshot    — Stage velocity, drop-off rates, stagnation counts, and revenue at risk
7. OpportunityHealthSnapshot — Deal health, momentum, competitor risk, and weighted expected revenue
8. AgentWorkloadSnapshot     — Agent capacity, active lead volume, meeting density, overload status
9. AnomalyEvent              — Statistical anomaly detections (volume surge, cancellation spike)
10. SalesInsight             — Explainable natural-language sales insights with evidence
11. InsightDismissal         — User dismissals/snoozes preventing repeated alert noise
12. NextBestAction           — Actionable operational recommendations with governance policies
13. ActionExecution          — Audit log of executed Next Best Actions
14. ManagerDailyBrief        — Real-time team operational summary for sales leaders
15. AgentDailyBrief          — Real-time prioritized action briefing for brokers
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from sqlalchemy import (
    String, Text, DateTime, Boolean, Integer, Float, JSON, Index,
    UniqueConstraint, ForeignKey
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")

def _gen_uuid() -> str:
    return str(uuid.uuid4())


class LeadHealthSnapshot(Base, TimestampMixin):
    """
    Dynamic lead health evaluation snapshot.
    Combines intent, momentum, recency, SLA compliance, and agent activity.
    """
    __tablename__ = "lead_health_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    health_state: Mapped[str] = mapped_column(String(30), default="HEALTHY", nullable=False, index=True)  # HEALTHY | IMPROVING | HOT | COOLING | AT_RISK | STALE | NEGLECTED | UNRESPONSIVE | CONVERTED | LOST
    health_score: Mapped[float] = mapped_column(Float, default=75.0, nullable=False)  # 0.0 to 100.0

    # 9 Distinct Health Sub-Dimensions (0.0 to 100.0)
    engagement_health: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    intent_health: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    response_health: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    follow_up_health: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    meeting_health: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    qualification_health: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    property_match_health: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    agent_attention_health: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)
    conversion_health: Mapped[float] = mapped_column(Float, default=70.0, nullable=False)

    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    decay_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    neglect_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evaluated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    risks: Mapped[List["LeadRisk"]] = relationship("LeadRisk", back_populates="health_snapshot", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_lead_health_org_state", "organization_id", "health_state"),
        Index("ix_lead_health_lead_eval", "lead_id", "evaluated_at"),
    )


class LeadRisk(Base, TimestampMixin):
    """
    Individual operational risk detected on a lead.
    """
    __tablename__ = "lead_risks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    snapshot_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("lead_health_snapshots.id", ondelete="SET NULL"), nullable=True)

    risk_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # NEGLECT | COOLING_INTENT | SLA_BREACH | VIEWING_CANCELLED | UNRESPONSIVE | COMPETITOR_THREAT
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False, index=True)  # LOW | MEDIUM | HIGH | CRITICAL
    confidence: Mapped[float] = mapped_column(Float, default=0.85, nullable=False)
    evidence: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_recovery_action: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", nullable=False, index=True)  # ACTIVE | RESOLVED | DISMISSED
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    health_snapshot: Mapped[Optional["LeadHealthSnapshot"]] = relationship("LeadHealthSnapshot", back_populates="risks")

    __table_args__ = (
        Index("ix_lead_risks_org_sev", "organization_id", "severity", "status"),
    )


class SlaPolicy(Base, TimestampMixin):
    """
    Configurable SLA rules per organization.
    """
    __tablename__ = "sla_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    policy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sla_type: Mapped[str] = mapped_column(String(50), nullable=False)  # FIRST_RESPONSE | QUALIFICATION | FOLLOW_UP | VIEWING_CONFIRMATION | HIGH_VALUE_LEAD
    target_duration_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    applies_to_tier: Mapped[str] = mapped_column(String(20), default="ALL", nullable=False)  # ALL | HOT | WARM | HIGH_VALUE
    escalate_to_manager: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class SlaInstance(Base, TimestampMixin):
    """
    Active timer tracking a specific SLA requirement on a lead.
    """
    __tablename__ = "sla_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    policy_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("sla_policies.id", ondelete="SET NULL"), nullable=True)

    sla_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_deadline_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="RUNNING", nullable=False, index=True)  # RUNNING | MET | BREACHED | CANCELLED
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    breaches: Mapped[List["SlaBreach"]] = relationship("SlaBreach", back_populates="instance", cascade="all, delete-orphan")


class SlaBreach(Base, TimestampMixin):
    """
    Recorded SLA violation event.
    """
    __tablename__ = "sla_breaches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    instance_id: Mapped[str] = mapped_column(String(36), ForeignKey("sla_instances.id", ondelete="CASCADE"), nullable=False, index=True)

    sla_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_deadline_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    breached_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    overdue_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    escalation_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    instance: Mapped["SlaInstance"] = relationship("SlaInstance", back_populates="breaches")


class PipelineHealthSnapshot(Base, TimestampMixin):
    """
    Aggregated pipeline stage metrics: count, value, velocity, stagnation, and risk.
    """
    __tablename__ = "pipeline_health_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    stage_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    stage_name: Mapped[str] = mapped_column(String(100), nullable=False)

    lead_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_pipeline_value_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    weighted_pipeline_value_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_stage_duration_days: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    stagnant_leads_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    conversion_rate_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    drop_off_rate_pct: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    revenue_at_risk_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    snapshot_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class OpportunityHealthSnapshot(Base, TimestampMixin):
    """
    Deal / Opportunity health and closing risk assessment.
    """
    __tablename__ = "opportunity_health_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    deal_health: Mapped[str] = mapped_column(String(20), default="STRONG", nullable=False)  # STRONG | STABLE | AT_RISK | CRITICAL
    momentum_score: Mapped[float] = mapped_column(Float, default=80.0, nullable=False)
    closing_probability: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    stagnation_days: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    competitor_threat_detected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revenue_at_risk_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    recommended_recovery_action: Mapped[str] = mapped_column(String(255), nullable=False)


class AgentWorkloadSnapshot(Base, TimestampMixin):
    """
    Sales agent workload, capacity utilization, and overload detection.
    """
    __tablename__ = "agent_workload_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    active_leads_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_priority_leads_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    open_tasks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    overdue_tasks_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    scheduled_meetings_today: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    workload_status: Mapped[str] = mapped_column(String(20), default="BALANCED", nullable=False, index=True)  # UNDERLOADED | BALANCED | OVERLOADED | CRITICAL
    capacity_utilization_pct: Mapped[float] = mapped_column(Float, default=50.0, nullable=False)
    rebalancing_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AnomalyEvent(Base, TimestampMixin):
    """
    Detected statistical anomalies across volume, response times, or conversion metrics.
    """
    __tablename__ = "anomaly_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # RESPONSE_TIME_SPIKE | CONVERSION_DROP | CANCELLATION_SURGE | LEAD_VOLUME_DROP
    severity: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False)  # LOW | MEDIUM | HIGH | CRITICAL
    expected_value: Mapped[float] = mapped_column(Float, nullable=False)
    actual_value: Mapped[float] = mapped_column(Float, nullable=False)
    deviation_pct: Mapped[float] = mapped_column(Float, nullable=False)
    anomaly_description: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str] = mapped_column(String(255), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class SalesInsight(Base, TimestampMixin):
    """
    Explainable natural-language sales and revenue insights with citations and action links.
    """
    __tablename__ = "sales_insights"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    insight_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # LEAD_INSIGHT | PIPELINE_INSIGHT | REVENUE_INSIGHT | AGENT_INSIGHT | SLA_INSIGHT | ANOMALY_INSIGHT
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="MEDIUM", nullable=False, index=True)  # LOW | MEDIUM | HIGH | URGENT
    impact_level: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.9, nullable=False)
    evidence: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    recommended_action: Mapped[str] = mapped_column(String(255), nullable=False)
    target_entity_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    target_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    dismissals: Mapped[List["InsightDismissal"]] = relationship("InsightDismissal", back_populates="insight", cascade="all, delete-orphan")


class InsightDismissal(Base, TimestampMixin):
    """
    Audit record of user dismissals/snoozes preventing repeated insight recreation.
    """
    __tablename__ = "insight_dismissals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    insight_id: Mapped[str] = mapped_column(String(36), ForeignKey("sales_insights.id", ondelete="CASCADE"), nullable=False, index=True)
    broker_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(20), default="DISMISSED", nullable=False)  # DISMISSED | SNOOZED | ACCEPTED
    snooze_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    insight: Mapped["SalesInsight"] = relationship("SalesInsight", back_populates="dismissals")


class OperationalNextBestAction(Base, TimestampMixin):
    """
    Prioritized operational actions generated for leads, opportunities, and agents.
    """
    __tablename__ = "crm_operational_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    lead_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)

    action_type: Mapped[str] = mapped_column(String(50), nullable=False)  # CALL_LEAD | SEND_WHATSAPP | SCHEDULE_VIEWING | RESCHEDULE_MEETING | ESCALATE_MANAGER | REASSIGN_AGENT | CREATE_TASK
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="HIGH", nullable=False, index=True)  # LOW | MEDIUM | HIGH | URGENT
    urgency_hours: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    potential_revenue_impact_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    governance_policy: Mapped[str] = mapped_column(String(30), default="RECOMMENDATION_ONLY", nullable=False)  # FULLY_AUTOMATIC | APPROVAL_REQUIRED | RECOMMENDATION_ONLY
    status: Mapped[str] = mapped_column(String(20), default="PENDING", nullable=False, index=True)  # PENDING | EXECUTED | REJECTED | EXPIRED

    executions: Mapped[List["ActionExecution"]] = relationship("ActionExecution", back_populates="action", cascade="all, delete-orphan")


class ActionExecution(Base, TimestampMixin):
    """
    Audit log of executed Next Best Actions.
    """
    __tablename__ = "action_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    action_id: Mapped[str] = mapped_column(String(36), ForeignKey("crm_operational_actions.id", ondelete="CASCADE"), nullable=False, index=True)
    executed_by: Mapped[str] = mapped_column(String(100), default="SYSTEM_AI", nullable=False)  # SYSTEM_AI | BROKER_1CLICK | MANAGER_OVERRIDE
    execution_status: Mapped[str] = mapped_column(String(20), default="SUCCESS", nullable=False)  # SUCCESS | FAILED
    result_payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    action: Mapped["OperationalNextBestAction"] = relationship("OperationalNextBestAction", back_populates="executions")


class ManagerDailyBrief(Base, TimestampMixin):
    """
    Executive operational summary generated for sales leadership.
    """
    __tablename__ = "manager_daily_briefs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    brief_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True)

    today_new_leads: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    high_intent_leads_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    at_risk_leads_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sla_breaches_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    upcoming_viewings_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    stagnant_deals_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revenue_at_risk_aed: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    overloaded_agents: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    top_manager_actions: Mapped[List[str]] = mapped_column(JSONBType, default=list, nullable=False)
    executive_summary: Mapped[str] = mapped_column(Text, nullable=False)


class AgentDailyBrief(Base, TimestampMixin):
    """
    Individual daily action briefing for brokers.
    """
    __tablename__ = "agent_daily_briefs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    broker_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    brief_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    top_leads_to_call: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    upcoming_meetings_today: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    overdue_follow_ups_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    urgent_tasks: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    daily_focus_summary: Mapped[str] = mapped_column(Text, nullable=False)
