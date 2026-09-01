"""
Volume 2 PART 12 — Workflow Automation & Autonomous Revenue Operations Engine Models
=====================================================================================
SQLAlchemy 2.0 models for:
1. WorkflowDefinition     — Master workflow definitions (name, trigger, status, tenant)
2. WorkflowVersion        — Immutable published snapshots (nodes DAG, edges, variables)
3. WorkflowInstance       — Execution run instance (state, current node, context payload)
4. WorkflowNodeExecution   — Individual node execution audit log (input, output, duration, errors)
5. WorkflowApproval       — Human-in-the-loop approval ticket & escalation
6. WorkflowWaitState      — Durable wait tracking (duration, date, domain event wait)
7. WorkflowTemplate       — Pre-packaged industry automation templates
8. WorkflowExecutionLock  — Distributed concurrency locking per entity
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


class WorkflowDefinition(Base, TimestampMixin):
    """
    Master workflow entity editable by admins.
    Status: DRAFT | VALIDATING | PUBLISHED | PAUSED | ARCHIVED | DEPRECATED
    """
    __tablename__ = "workflow_definitions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(50), default="lead_lifecycle", nullable=False)  # lead_lifecycle | viewing | deals | nurture | ops

    trigger_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # LeadCreated | LeadScoreChanged | SlaBreached | MeetingBooked | Manual
    trigger_config_json: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="DRAFT", nullable=False, index=True)  # DRAFT | VALIDATING | PUBLISHED | PAUSED | ARCHIVED
    active_version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    versions: Mapped[List["WorkflowVersion"]] = relationship(
        "WorkflowVersion", back_populates="definition", cascade="all, delete-orphan"
    )
    instances: Mapped[List["WorkflowInstance"]] = relationship(
        "WorkflowInstance", back_populates="definition", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_wf_def_org_status", "organization_id", "status"),
    )


class WorkflowVersion(Base, TimestampMixin):
    """
    Immutable published snapshot of a workflow DAG graph, nodes, edges, and variables.
    """
    __tablename__ = "workflow_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    workflow_definition_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # DAG Graph Structure
    nodes_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    edges_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    variables_schema: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    published_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    definition: Mapped["WorkflowDefinition"] = relationship("WorkflowDefinition", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("workflow_definition_id", "version_number", name="uq_wf_def_version"),
    )


class WorkflowInstance(Base, TimestampMixin):
    """
    Execution run instance representing a live or completed workflow execution.
    Status: PENDING | RUNNING | WAITING | PAUSED | COMPLETED | FAILED | CANCELLED | TIMED_OUT | COMPENSATING
    """
    __tablename__ = "workflow_instances"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    workflow_definition_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    workflow_version_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflow_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)  # lead_id or deal_id
    entity_type: Mapped[str] = mapped_column(String(30), default="LEAD", nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False, index=True)
    current_node_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Runtime Execution Context
    context_data: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    trigger_payload: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_test_run: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    definition: Mapped["WorkflowDefinition"] = relationship("WorkflowDefinition", back_populates="instances")
    node_executions: Mapped[List["WorkflowNodeExecution"]] = relationship(
        "WorkflowNodeExecution", back_populates="instance", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_wf_inst_org_status", "organization_id", "status"),
        Index("ix_wf_inst_entity", "entity_id", "status"),
    )


class WorkflowNodeExecution(Base, TimestampMixin):
    """
    Individual node execution record for auditability, tracing, and retry replay.
    """
    __tablename__ = "workflow_node_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    workflow_instance_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    node_type: Mapped[str] = mapped_column(String(50), nullable=False)  # ACTION | CONDITION | AI_DECISION | WAIT | APPROVAL | BRANCH | END
    node_name: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False)  # PENDING | RUNNING | WAITING | COMPLETED | FAILED | SKIPPED
    input_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    output_snapshot: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    duration_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    executed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    instance: Mapped["WorkflowInstance"] = relationship("WorkflowInstance", back_populates="node_executions")


# Backward compatibility alias
WorkflowExecution = WorkflowNodeExecution


class WorkflowApproval(Base, TimestampMixin):
    """
    Human-in-the-loop approval ticket blocking workflow execution until decided.
    """
    __tablename__ = "workflow_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    workflow_instance_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    context_summary: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)

    status: Mapped[str] = mapped_column(String(30), default="PENDING", nullable=False, index=True)  # PENDING | APPROVED | REJECTED | EXPIRED | ESCALATED
    assigned_role: Mapped[str] = mapped_column(String(50), default="manager", nullable=False)
    assigned_to_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)

    decision_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class WorkflowWaitState(Base, TimestampMixin):
    """
    Durable wait state tracking for timer or domain event pauses.
    """
    __tablename__ = "workflow_wait_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    workflow_instance_id: Mapped[str] = mapped_column(String(36), ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    node_id: Mapped[str] = mapped_column(String(100), nullable=False)

    wait_type: Mapped[str] = mapped_column(String(50), nullable=False)  # DURATION | DATE | EVENT_WAIT
    expected_event: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # e.g. CustomerResponse | PropertyViewed
    resume_deadline_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    is_resumed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    resumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class WorkflowTemplate(Base, TimestampMixin):
    """
    Pre-built industry automation template catalog.
    """
    __tablename__ = "workflow_templates"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    template_key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="lead_nurture", nullable=False)
    trigger_type: Mapped[str] = mapped_column(String(100), nullable=False)

    nodes_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    edges_json: Mapped[List[Dict[str, Any]]] = mapped_column(JSONBType, default=list, nullable=False)
    variables_schema: Mapped[Dict[str, Any]] = mapped_column(JSONBType, default=dict, nullable=False)
    is_system_template: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class WorkflowExecutionLock(Base, TimestampMixin):
    """
    Distributed concurrency lock preventing multiple workflows from racing on the same entity.
    """
    __tablename__ = "workflow_execution_locks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_gen_uuid)
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    workflow_definition_id: Mapped[str] = mapped_column(String(36), nullable=False)
    locked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    __table_args__ = (
        UniqueConstraint("organization_id", "entity_id", "workflow_definition_id", name="uq_wf_lock_entity"),
    )
