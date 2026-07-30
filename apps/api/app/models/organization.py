import uuid
from typing import Optional, List
from sqlalchemy import String, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.base_mixins import TimestampMixin, SoftDeleteMixin

class Organization(Base, TimestampMixin, SoftDeleteMixin):
    """
    Enterprise Organization Entity for Multi-Tenant Brokerage Hierarchy.
    (Organization -> Team / Branch -> Broker / Agent -> Lead).
    """
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(50), default="pro", nullable=False) # starter | pro | enterprise
    country_code: Mapped[str] = mapped_column(String(2), default="IN", nullable=False, index=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    members: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

class OrganizationMember(Base, TimestampMixin):
    """Junction table associating Brokers with Organizations and Assigning RBAC Roles."""
    __tablename__ = "organization_members"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        primary_key=True
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("brokers.id", ondelete="CASCADE"),
        primary_key=True
    )
    role: Mapped[str] = mapped_column(String(50), default="agent", nullable=False) # owner | admin | manager | agent

    organization: Mapped["Organization"] = relationship("Organization", back_populates="members")
