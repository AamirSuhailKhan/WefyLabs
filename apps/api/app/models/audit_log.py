import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy import String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base

JSONBType = JSONB().with_variant(JSON(), "sqlite")

class AuditLog(Base):
    """
    Immutable Audit Log entity.
    Tracks every entity mutation, auth event, export, AI action, and admin operation.
    Enterprise SOC2 Type II / ISO27001 / GDPR compliant.
    NEVER deleted. NEVER modified after creation.
    """
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    workspace_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brokers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    actor_type: Mapped[str] = mapped_column(String(20), default="user", nullable=False)  # user | system | ai | webhook | api_key
    action: Mapped[str] = mapped_column(String(100), nullable=False, index=True)          # lead.create | auth.login | api_key.rotate
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)   # lead | broker | organization | api_key
    resource_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    previous_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, nullable=True)
    new_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, nullable=True)
    changes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONBType, nullable=True)  # Diff summary {field: {before, after}}
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    device: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    browser: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    api_key_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    risk_score: Mapped[Optional[float]] = mapped_column(nullable=True)
    geo_country: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    __table_args__ = (
        Index("ix_audit_org_action", "organization_id", "action"),
        Index("ix_audit_org_created", "organization_id", "created_at"),
        Index("ix_audit_resource", "resource_type", "resource_id"),
    )
