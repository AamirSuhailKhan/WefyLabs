"""
Part 30 — AI Real-Estate Agent Daily Command Center Models
===========================================================
Stores operational command center state including dismissed or snoozed
priority items, preventing repetitive alert fatigue while strictly preserving
the underlying CRM records (Leads, Tasks, Meetings, Follow-ups).
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Column, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class GUID(TypeDecorator):
    """Platform-independent GUID type compatible with SQLite and PostgreSQL."""
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(UUID(as_uuid=True))
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


UUIDType = GUID()


def _gen_uuid():
    return str(uuid.uuid4())


class CommandCenterDismissal(Base):
    """
    Tracks an agent's dismissal or temporary snooze of a priority action item
    in the Daily Command Center. Preserves semantic separation from CRM entity deletion.
    """
    __tablename__ = "command_center_dismissals"

    id = Column(String(36), primary_key=True, default=_gen_uuid)
    organization_id = Column(String(36), nullable=False, index=True)
    broker_id = Column(UUIDType, ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    item_key = Column(String(255), nullable=False, index=True)
    entity_type = Column(String(50), nullable=False)  # lead | task | meeting | match | property
    entity_id = Column(String(64), nullable=False)
    action_type = Column(String(30), default="dismissed", nullable=False)  # dismissed | snoozed
    snoozed_until = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("organization_id", "broker_id", "item_key", name="uq_cmd_center_dismissal"),
        Index("ix_cmd_center_broker_item", "broker_id", "item_key"),
        Index("ix_cmd_center_snooze", "broker_id", "snoozed_until"),
    )
