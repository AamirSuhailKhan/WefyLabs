"""
PART 24.1 — Password Reset & Team Member Invitation Models
==========================================================
SQLAlchemy 2.0 models for:
- PasswordResetToken: Single-use, time-bound (15m), hashed password reset tokens.
- OrganizationInvitation: Single-use, time-bound (7d), role-scoped team invitations.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import (
    String, DateTime, ForeignKey, Index, UniqueConstraint, Uuid
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin

UUIDType = Uuid(as_uuid=True)



def _gen_uuid() -> uuid.UUID:
    return uuid.uuid4()


class PasswordResetToken(Base, TimestampMixin):
    """
    Secure password reset token store.
    Stores only the SHA-256 hash of the raw token (raw token is never stored in DB).
    Single-use enforced by `used_at`.
    """
    __tablename__ = "password_reset_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        primary_key=True,
        default=_gen_uuid
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    broker = relationship("Broker", backref="password_reset_tokens")


class OrganizationInvitation(Base, TimestampMixin):
    """
    Organization member invitation record.
    Stores SHA-256 hash of the invite token, target email, role, and expiration.
    Single-use enforced by `status` and `accepted_at`.
    """
    __tablename__ = "organization_invitations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        primary_key=True,
        default=_gen_uuid
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    invited_by_id: Mapped[uuid.UUID] = mapped_column(
        UUIDType,
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), default="agent", nullable=False) # owner | admin | manager | agent
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True) # pending | accepted | revoked | expired
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization", backref="invitations")
    invited_by = relationship("Broker", backref="sent_invitations")
