import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, JSON, Integer, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

JSONBType = JSONB().with_variant(JSON(), "sqlite")

class WorkflowDefinition(Base, TimestampMixin):
    """
    Visual Workflow Automation Definition Model storing node graphs (Triggers, Conditions, Actions).
    """
    __tablename__ = "workflow_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    trigger_type: Mapped[str] = mapped_column(String(100), default="lead_created", nullable=False)

    nodes: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)
    edges: Mapped[Optional[list]] = mapped_column(JSONBType, default=list, nullable=True)

    executions: Mapped[List["WorkflowExecution"]] = relationship("WorkflowExecution", back_populates="workflow", cascade="all, delete-orphan")

class WorkflowExecution(Base, TimestampMixin):
    """Execution run audit log."""
    __tablename__ = "workflow_executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default="success", nullable=False) # running | success | failed
    trigger_payload: Mapped[Optional[dict]] = mapped_column(JSONBType, default=dict, nullable=True)
    executed_nodes_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    workflow: Mapped["WorkflowDefinition"] = relationship("WorkflowDefinition", back_populates="executions")
