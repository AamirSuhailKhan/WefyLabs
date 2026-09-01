import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, Integer, Float, Text, DateTime, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

class MarketplaceItem(Base, TimestampMixin):
    """
    Developer Marketplace Registry Item for Workflow Templates, AI Prompt Packs,
    Portal Integrations, Analytics Dashboards, and Country Packs.
    """
    __tablename__ = "marketplace_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publisher_name: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True
    )  # workflow | ai_prompt | portal_integration | analytics | country_pack | theme | extension
    description: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0", nullable=False)
    price_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False) # 0.0 = Free
    downloads_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    rating: Mapped[float] = mapped_column(Float, default=5.0, nullable=False)
    security_status: Mapped[str] = mapped_column(String(20), default="verified", nullable=False) # pending | verified | flagged
    manifest_data: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

class MarketplaceInstallation(Base, TimestampMixin):
    """Tenant workspace installation records for marketplace apps and extensions."""
    __tablename__ = "marketplace_installations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    broker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("marketplace_items.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False) # active | uninstalled

    item: Mapped["MarketplaceItem"] = relationship("MarketplaceItem")
