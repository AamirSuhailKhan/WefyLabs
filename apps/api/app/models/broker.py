import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, TYPE_CHECKING
from sqlalchemy import String, DateTime, CheckConstraint, text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.lead import Lead
    from app.models.subscription import Subscription

def default_trial_ends_at() -> datetime:
    return datetime.now(timezone.utc) + timedelta(days=7)

class Broker(Base):
    __tablename__ = "brokers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    agency_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    city: Mapped[str] = mapped_column(String(100), default="Bengaluru", nullable=False)
    whatsapp_number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    subscription_status: Mapped[str] = mapped_column(
        String(20),
        default="trial",
        nullable=False
    )
    trial_ends_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=default_trial_ends_at,
        nullable=False
    )
    subscription_plan: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    razorpay_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    razorpay_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "subscription_status IN ('trial', 'active', 'cancelled', 'expired')",
            name="ck_brokers_subscription_status"
        ),
        CheckConstraint(
            "subscription_plan IS NULL OR subscription_plan IN ('monthly', 'annual')",
            name="ck_brokers_subscription_plan"
        ),
    )

    leads: Mapped[List["Lead"]] = relationship("Lead", back_populates="broker", cascade="all, delete-orphan")
    subscriptions: Mapped[List["Subscription"]] = relationship("Subscription", back_populates="broker", cascade="all, delete-orphan")

    @property
    def trial_days_remaining(self) -> int:
        if not self.trial_ends_at:
            return 0
        ends_at = self.trial_ends_at
        if ends_at.tzinfo is None:
            ends_at = ends_at.replace(tzinfo=timezone.utc)
        diff = (ends_at - datetime.now(timezone.utc)).total_seconds()
        return max(0, int(diff // 86400))
