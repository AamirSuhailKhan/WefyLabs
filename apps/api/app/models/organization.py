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
    # ISO Alpha-2 country code — no default; must be explicitly set during org creation
    country_code: Mapped[Optional[str]] = mapped_column(String(2), nullable=True, index=True)
    # ── Global / Multi-Country Fields ────────────────────────────────────────
    # List of market UUIDs this org operates in — drives market-scoped data isolation
    operating_market_ids: Mapped[Optional[list]] = mapped_column(JSON, default=list, nullable=True)
    # Reporting currency for cross-market analytics — stored as ISO 4217 code
    reporting_currency_code: Mapped[Optional[str]] = mapped_column(String(3), nullable=True)   # "USD", "INR"
    # Organization's default IANA timezone (resolved via TimezoneService hierarchy)
    default_timezone: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)         # "Asia/Dubai"
    # Data residency region: india | middle-east | europe | north-america | apac
    data_residency_region: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSON, default=dict, nullable=True)

    members: Mapped[List["OrganizationMember"]] = relationship(
        "OrganizationMember",
        back_populates="organization",
        cascade="all, delete-orphan"
    )

class Workspace(Base, TimestampMixin, SoftDeleteMixin):
    """Sub-tenant Workspace partition within an Organization."""
    __tablename__ = "workspaces"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

class Department(Base, TimestampMixin):
    """Organizational unit / Department inside an Organization."""
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)

class RoleModel(Base, TimestampMixin):
    """Database-driven RBAC Role (Owner, Admin, Manager, Agent, Marketing, Custom)."""
    __tablename__ = "rbac_roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_system_role: Mapped[bool] = mapped_column(default=False, nullable=False)

class PermissionModel(Base, TimestampMixin):
    """Database-driven Granular Permission (e.g. leads:create, deals:update_stage)."""
    __tablename__ = "rbac_permissions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    module: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # leads | deals | billing | analytics
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

class RolePermission(Base, TimestampMixin):
    """Junction table mapping Roles to Permissions."""
    __tablename__ = "rbac_role_permissions"

    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rbac_roles.id", ondelete="CASCADE"),
        primary_key=True
    )
    permission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("rbac_permissions.id", ondelete="CASCADE"),
        primary_key=True
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
