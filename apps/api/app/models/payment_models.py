"""
BeetleLabs Production Payment & Billing Models
==============================================
Normalized relational models for Razorpay payment processing, orders,
transactions, refunds, webhook event replay protection, and audit trails.

Security & Compliance:
- Zero raw cardholder data or payment secrets stored.
- UUID primary keys for platform portability.
- Multi-tenant isolation: every record is bound to a broker_id / organization_id.
- Strong unique constraints on provider IDs and idempotency keys.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from sqlalchemy import (
    Column, String, Integer, Text, DateTime, ForeignKey,
    Boolean, Index, UniqueConstraint, CheckConstraint, func
)
from sqlalchemy.types import TypeDecorator, CHAR, JSON
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import relationship, Mapped, mapped_column

from app.database import Base

if TYPE_CHECKING:
    from app.models.broker import Broker


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Handles UUID objects AND string representations seamlessly in SQLite and PostgreSQL.
    """
    impl = CHAR(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
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
        else:
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


class PaymentStatus(str, Enum):
    """Authoritative Payment State Machine States."""
    ORDER_CREATED = "ORDER_CREATED"
    PAYMENT_ATTEMPTED = "PAYMENT_ATTEMPTED"
    PAYMENT_AUTHORIZED = "PAYMENT_AUTHORIZED"
    PAYMENT_CAPTURED = "PAYMENT_CAPTURED"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    PAYMENT_CANCELLED = "PAYMENT_CANCELLED"
    REFUND_REQUESTED = "REFUND_REQUESTED"
    REFUND_PROCESSING = "REFUND_PROCESSING"
    REFUNDED = "REFUNDED"
    REFUND_FAILED = "REFUND_FAILED"


class RefundStatus(str, Enum):
    """Refund lifecycle states."""
    REFUND_REQUESTED = "REFUND_REQUESTED"
    REFUND_PROCESSING = "REFUND_PROCESSING"
    REFUNDED = "REFUNDED"
    REFUND_FAILED = "REFUND_FAILED"


class WebhookEventStatus(str, Enum):
    """Webhook event processing status."""
    RECEIVED = "RECEIVED"
    PROCESSED = "PROCESSED"
    FAILED = "FAILED"
    IGNORED = "IGNORED"


class PaymentOrder(Base):
    """
    Payment Order Model.
    Represents a commercial intent to purchase or subscribe, synced with Razorpay Order.
    """
    __tablename__ = "payment_orders"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    organization_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    razorpay_order_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    plan_id: Mapped[str] = mapped_column(String(100), nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # in paise (e.g. 499900 = ₹4,999.00)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=PaymentStatus.ORDER_CREATED.value,
        nullable=False,
        index=True
    )
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    receipt: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notes: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    transactions: Mapped[List["PaymentTransaction"]] = relationship(
        "PaymentTransaction",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    refunds: Mapped[List["PaymentRefund"]] = relationship(
        "PaymentRefund",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    broker: Mapped["Broker"] = relationship("Broker", foreign_keys=[broker_id], lazy="selectin")


class PaymentTransaction(Base):
    """
    Payment Transaction Model.
    Represents an individual payment attempt and capture record synced from Razorpay.
    """
    __tablename__ = "payment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("payment_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    organization_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    razorpay_payment_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    razorpay_order_id: Mapped[Optional[str]] = mapped_column(String(255), index=True, nullable=True)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # in paise
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=PaymentStatus.PAYMENT_ATTEMPTED.value,
        nullable=False,
        index=True
    )
    method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # card, upi, netbanking, wallet
    bank: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    wallet: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    vpa: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    fee: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Razorpay fee in paise
    tax: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # GST in paise

    error_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error_source: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_step: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    captured_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    order: Mapped[Optional["PaymentOrder"]] = relationship("PaymentOrder", back_populates="transactions")
    refunds: Mapped[List["PaymentRefund"]] = relationship(
        "PaymentRefund",
        back_populates="transaction",
        cascade="all, delete-orphan",
        lazy="selectin"
    )
    broker: Mapped["Broker"] = relationship("Broker", foreign_keys=[broker_id], lazy="selectin")


class PaymentRefund(Base):
    """
    Payment Refund Model.
    Tracks full or partial refunds with idempotency protection and Razorpay sync.
    """
    __tablename__ = "payment_refunds"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    transaction_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("payment_transactions.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    order_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("payment_orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    broker_id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        ForeignKey("brokers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    organization_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    razorpay_refund_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    razorpay_payment_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)  # in paise
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=RefundStatus.REFUND_REQUESTED.value,
        nullable=False,
        index=True
    )
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    receipt: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    transaction: Mapped[Optional["PaymentTransaction"]] = relationship("PaymentTransaction", back_populates="refunds")
    order: Mapped[Optional["PaymentOrder"]] = relationship("PaymentOrder", back_populates="refunds")
    broker: Mapped["Broker"] = relationship("Broker", foreign_keys=[broker_id], lazy="selectin")


class PaymentWebhookEvent(Base):
    """
    Webhook Event Record.
    Provides strict replay protection and audit log for every incoming Razorpay webhook.
    """
    __tablename__ = "payment_webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    event_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(
        String(50),
        default=WebhookEventStatus.RECEIVED.value,
        nullable=False,
        index=True
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )


class PaymentAuditLog(Base):
    """
    Payment Audit Log.
    Tracks all administrative, system, and merchant actions on the payment subsystem.
    """
    __tablename__ = "payment_audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID(),
        primary_key=True,
        default=uuid.uuid4
    )
    broker_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        GUID(),
        ForeignKey("brokers.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )
    organization_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    actor_type: Mapped[str] = mapped_column(String(50), default="SYSTEM", nullable=False)
    actor_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    previous_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    new_state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False
    )
