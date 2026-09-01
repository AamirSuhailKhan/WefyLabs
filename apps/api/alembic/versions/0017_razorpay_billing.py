"""
Part 23.4 — Alembic Migration 0017: Razorpay Production Payments & Billing
========================================================================
Additive forward migration creating tables for:
- payment_orders
- payment_transactions
- payment_refunds
- payment_webhook_events
- payment_audit_logs

Data Safety: ZERO destructive operations. All existing tables and data preserved.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0017_razorpay_billing"
down_revision = "0016_lead_sources_alignment"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. payment_orders ─────────────────────────────────────────────────────
    op.create_table(
        "payment_orders",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_id", sa.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=True),
        sa.Column("razorpay_order_id", sa.String(255), nullable=False),
        sa.Column("plan_id", sa.String(100), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("status", sa.String(50), server_default="ORDER_CREATED", nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("receipt", sa.String(255), nullable=True),
        sa.Column("notes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_orders_broker_id", "payment_orders", ["broker_id"], if_not_exists=True)
    op.create_index("ix_payment_orders_organization_id", "payment_orders", ["organization_id"], if_not_exists=True)
    op.create_index("ix_payment_orders_razorpay_order_id", "payment_orders", ["razorpay_order_id"], unique=True, if_not_exists=True)
    op.create_index("ix_payment_orders_idempotency_key", "payment_orders", ["idempotency_key"], unique=True, if_not_exists=True)
    op.create_index("ix_payment_orders_status", "payment_orders", ["status"], if_not_exists=True)

    # ── 2. payment_transactions ───────────────────────────────────────────────
    op.create_table(
        "payment_transactions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", sa.UUID(as_uuid=True), sa.ForeignKey("payment_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("broker_id", sa.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=True),
        sa.Column("razorpay_payment_id", sa.String(255), nullable=False),
        sa.Column("razorpay_order_id", sa.String(255), nullable=True),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("method", sa.String(50), nullable=True),
        sa.Column("bank", sa.String(100), nullable=True),
        sa.Column("wallet", sa.String(100), nullable=True),
        sa.Column("vpa", sa.String(255), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("contact", sa.String(50), nullable=True),
        sa.Column("fee", sa.Integer(), nullable=True),
        sa.Column("tax", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.Column("error_description", sa.Text(), nullable=True),
        sa.Column("error_source", sa.String(100), nullable=True),
        sa.Column("error_step", sa.String(100), nullable=True),
        sa.Column("error_reason", sa.String(100), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_transactions_broker_id", "payment_transactions", ["broker_id"], if_not_exists=True)
    op.create_index("ix_payment_transactions_order_id", "payment_transactions", ["order_id"], if_not_exists=True)
    op.create_index("ix_payment_transactions_razorpay_payment_id", "payment_transactions", ["razorpay_payment_id"], unique=True, if_not_exists=True)
    op.create_index("ix_payment_transactions_razorpay_order_id", "payment_transactions", ["razorpay_order_id"], if_not_exists=True)
    op.create_index("ix_payment_transactions_status", "payment_transactions", ["status"], if_not_exists=True)

    # ── 3. payment_refunds ────────────────────────────────────────────────────
    op.create_table(
        "payment_refunds",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("transaction_id", sa.UUID(as_uuid=True), sa.ForeignKey("payment_transactions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_id", sa.UUID(as_uuid=True), sa.ForeignKey("payment_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("broker_id", sa.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("organization_id", sa.String(64), nullable=True),
        sa.Column("razorpay_refund_id", sa.String(255), nullable=False),
        sa.Column("razorpay_payment_id", sa.String(255), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("status", sa.String(50), server_default="REFUND_REQUESTED", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("receipt", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_refunds_broker_id", "payment_refunds", ["broker_id"], if_not_exists=True)
    op.create_index("ix_payment_refunds_transaction_id", "payment_refunds", ["transaction_id"], if_not_exists=True)
    op.create_index("ix_payment_refunds_razorpay_refund_id", "payment_refunds", ["razorpay_refund_id"], unique=True, if_not_exists=True)
    op.create_index("ix_payment_refunds_razorpay_payment_id", "payment_refunds", ["razorpay_payment_id"], if_not_exists=True)
    op.create_index("ix_payment_refunds_idempotency_key", "payment_refunds", ["idempotency_key"], unique=True, if_not_exists=True)

    # ── 4. payment_webhook_events ─────────────────────────────────────────────
    op.create_table(
        "payment_webhook_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", sa.String(255), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(50), server_default="RECEIVED", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_webhook_events_event_id", "payment_webhook_events", ["event_id"], unique=True, if_not_exists=True)
    op.create_index("ix_payment_webhook_events_event_type", "payment_webhook_events", ["event_type"], if_not_exists=True)
    op.create_index("ix_payment_webhook_events_status", "payment_webhook_events", ["status"], if_not_exists=True)

    # ── 5. payment_audit_logs ─────────────────────────────────────────────────
    op.create_table(
        "payment_audit_logs",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_id", sa.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("organization_id", sa.String(64), nullable=True),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(50), nullable=False),
        sa.Column("resource_id", sa.String(255), nullable=False),
        sa.Column("actor_type", sa.String(50), server_default="SYSTEM", nullable=False),
        sa.Column("actor_id", sa.String(255), nullable=True),
        sa.Column("previous_state", sa.String(50), nullable=True),
        sa.Column("new_state", sa.String(50), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_payment_audit_logs_broker_id", "payment_audit_logs", ["broker_id"], if_not_exists=True)
    op.create_index("ix_payment_audit_logs_event_type", "payment_audit_logs", ["event_type"], if_not_exists=True)
    op.create_index("ix_payment_audit_logs_resource_id", "payment_audit_logs", ["resource_id"], if_not_exists=True)


def downgrade():
    op.drop_table("payment_audit_logs")
    op.drop_table("payment_webhook_events")
    op.drop_table("payment_refunds")
    op.drop_table("payment_transactions")
    op.drop_table("payment_orders")
