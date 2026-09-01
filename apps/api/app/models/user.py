"""
BeetleLabs User Model
======================
Enterprise User entity representing agents, admins, managers, and team members.
Belongs to an Organization. Supports multi-role RBAC, SSO, and device tracking.
Co-exists with Broker model during legacy migration phase.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy import String, DateTime, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base_mixins import AuditMixin, TenantMixin


class User(Base, TenantMixin, AuditMixin):
    """
    Enterprise User model.
    Supercedes legacy Broker model over time while sharing organization & tenant hierarchy.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True, index=True)
    whatsapp_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Kolkata", nullable=False)
    locale: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    auth_provider: Mapped[str] = mapped_column(String(30), default="supabase", nullable=False)
    external_auth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)
    
    subscription_status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    subscription_plan: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_users_org_active", "organization_id", "is_active"),
        Index("ix_users_email_active", "email", "is_active"),
    )
