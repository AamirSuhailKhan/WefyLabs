import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, DateTime, ForeignKey, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

class DeveloperApiKey(Base, TimestampMixin):
    """
    Developer API Keys for external apps, CLI tools, and enterprise API access.
    """
    __tablename__ = "developer_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    api_key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    prefix: Mapped[str] = mapped_column(String(12), nullable=False) # e.g. btl_live_
    scopes: Mapped[dict] = mapped_column(JSON, default=list, nullable=False) # e.g. ["leads:read", "leads:write", "webhooks:manage"]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class WebhookSubscription(Base, TimestampMixin):
    """
    Real-time Webhook Engine Subscriptions for Domain Events.
    """
    __tablename__ = "webhook_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    target_url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(100), nullable=False) # HMAC verification secret
    events: Mapped[dict] = mapped_column(JSON, default=list, nullable=False) # ["LeadCreated", "LeadQualified", "DealWon"]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
