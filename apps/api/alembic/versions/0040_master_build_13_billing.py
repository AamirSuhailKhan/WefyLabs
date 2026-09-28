"""Master Build 13 — Canonical Billing, Usage, Entitlements & Revenue OS

Revision ID: 0040_master_build_13_billing
Revises: 0039_build09_revenue_intelligence
Create Date: 2026-09-27 16:35:00.000000

Creates:
  - billing_customers
  - billing_accounts
  - plans
  - plan_versions
  - plan_entitlements
  - canonical_subscriptions
  - subscription_items
  - billing_periods
  - usage_meters
  - usage_events
  - usage_aggregates
  - canonical_invoices
  - canonical_invoice_lines
  - credit_balances
  - credit_ledger_entries
  - credit_notes
  - billing_adjustments
  - entitlement_grants
  - entitlement_consumptions
  - cost_events
  - unit_economics_snapshots
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0040_master_build_13_billing"
down_revision = "0039_build09_revenue_intelligence"
branch_labels = None
depends_on = None

MoneyType = sa.Numeric(precision=20, scale=4)
PctType = sa.Numeric(precision=7, scale=4)


def upgrade():
    # ── 1. billing_customers ──────────────────────────────────────────────────
    op.create_table(
        "billing_customers",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("legal_name", sa.String(255), nullable=False),
        sa.Column("billing_email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("tax_identifier", sa.String(100), nullable=True),
        sa.Column("address_line1", sa.String(255), nullable=True),
        sa.Column("address_line2", sa.String(255), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("country_code", sa.String(2), server_default="IN", nullable=False),
        sa.Column("postal_code", sa.String(20), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_billing_cust_org", "billing_customers", ["organization_id"], if_not_exists=True)
    op.create_index("ix_billing_cust_email", "billing_customers", ["billing_email"], if_not_exists=True)

    # ── 2. billing_accounts ───────────────────────────────────────────────────
    op.create_table(
        "billing_accounts",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("billing_customer_id", sa.UUID(as_uuid=True), sa.ForeignKey("billing_customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(50), server_default="razorpay", nullable=False),
        sa.Column("provider_customer_id", sa.String(255), nullable=True),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("billing_email", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), server_default="ACTIVE", nullable=False),
        sa.Column("default_payment_method_ref", sa.String(255), nullable=True),
        sa.Column("tax_exempt", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_payload", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_billing_acc_org", "billing_accounts", ["organization_id"], if_not_exists=True)
    op.create_index("ix_billing_acc_provider_cust", "billing_accounts", ["provider_customer_id"], if_not_exists=True)

    # ── 3. plans ──────────────────────────────────────────────────────────────
    op.create_table(
        "plans",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_plans_code", "plans", ["code"], if_not_exists=True)

    # ── 4. plan_versions ──────────────────────────────────────────────────────
    op.create_table(
        "plan_versions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_id", sa.UUID(as_uuid=True), sa.ForeignKey("plans.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("interval", sa.String(20), server_default="MONTHLY", nullable=False),
        sa.Column("price", MoneyType, nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("trial_days", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("plan_id", "version", "interval", name="uq_plan_version_interval"),
    )
    op.create_index("ix_plan_versions_plan", "plan_versions", ["plan_id"], if_not_exists=True)

    # ── 5. plan_entitlements ──────────────────────────────────────────────────
    op.create_table(
        "plan_entitlements",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("plan_version_id", sa.UUID(as_uuid=True), sa.ForeignKey("plan_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entitlement_key", sa.String(100), nullable=False),
        sa.Column("entitlement_type", sa.String(50), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.Column("boolean_value", sa.Boolean(), nullable=True),
        sa.Column("enforcement_policy", sa.String(50), server_default="HARD_LIMIT", nullable=False),
        sa.Column("overage_allowed", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("overage_unit_price", MoneyType, nullable=True),
        sa.Column("reset_period", sa.String(20), server_default="MONTHLY", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("plan_version_id", "entitlement_key", name="uq_plan_version_entitlement"),
    )
    op.create_index("ix_plan_entitlements_version", "plan_entitlements", ["plan_version_id"], if_not_exists=True)
    op.create_index("ix_plan_entitlements_key", "plan_entitlements", ["entitlement_key"], if_not_exists=True)

    # ── 6. canonical_subscriptions ────────────────────────────────────────────
    op.create_table(
        "canonical_subscriptions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("billing_account_id", sa.UUID(as_uuid=True), sa.ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("plan_version_id", sa.UUID(as_uuid=True), sa.ForeignKey("plan_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(50), server_default="TRIALING", nullable=False),
        sa.Column("current_period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancel_at_period_end", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("grace_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_subscription_id", sa.String(255), nullable=True),
        sa.Column("metadata_payload", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_canon_sub_org", "canonical_subscriptions", ["organization_id"], if_not_exists=True)
    op.create_index("ix_canon_sub_account", "canonical_subscriptions", ["billing_account_id"], if_not_exists=True)
    op.create_index("ix_canon_sub_status", "canonical_subscriptions", ["status"], if_not_exists=True)

    # ── 7. subscription_items ─────────────────────────────────────────────────
    op.create_table(
        "subscription_items",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("subscription_id", sa.UUID(as_uuid=True), sa.ForeignKey("canonical_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("item_type", sa.String(50), server_default="SEAT", nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("unit_price", MoneyType, nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_sub_items_sub", "subscription_items", ["subscription_id"], if_not_exists=True)

    # ── 8. billing_periods ────────────────────────────────────────────────────
    op.create_table(
        "billing_periods",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", sa.UUID(as_uuid=True), sa.ForeignKey("canonical_subscriptions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(50), server_default="OPEN", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "subscription_id", "period_start", "period_end", name="uq_billing_period_org_sub"),
    )
    op.create_index("ix_billing_periods_org", "billing_periods", ["organization_id"], if_not_exists=True)
    op.create_index("ix_billing_periods_sub", "billing_periods", ["subscription_id"], if_not_exists=True)

    # ── 9. usage_meters ───────────────────────────────────────────────────────
    op.create_table(
        "usage_meters",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("aggregation_type", sa.String(50), server_default="COUNT", nullable=False),
        sa.Column("source_event", sa.String(100), nullable=False),
        sa.Column("is_billable", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("reset_policy", sa.String(50), server_default="BILLING_PERIOD", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_usage_meters_code", "usage_meters", ["code"], if_not_exists=True)

    # ── 10. usage_events ──────────────────────────────────────────────────────
    op.create_table(
        "usage_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("meter_id", sa.UUID(as_uuid=True), sa.ForeignKey("usage_meters.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("event_name", sa.String(100), nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("billing_period_id", sa.UUID(as_uuid=True), sa.ForeignKey("billing_periods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("metadata_payload", sa.JSON(), server_default="{}", nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_usage_event_org_idemp"),
    )
    op.create_index("ix_usage_events_org_meter_time", "usage_events", ["organization_id", "meter_id", "occurred_at"], if_not_exists=True)

    # ── 11. usage_aggregates ──────────────────────────────────────────────────
    op.create_table(
        "usage_aggregates",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("meter_id", sa.UUID(as_uuid=True), sa.ForeignKey("usage_meters.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("billing_period_id", sa.UUID(as_uuid=True), sa.ForeignKey("billing_periods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), server_default="0.0", nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("last_aggregated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "meter_id", "billing_period_id", name="uq_usage_agg_org_meter_period"),
    )
    op.create_index("ix_usage_agg_org_period", "usage_aggregates", ["organization_id", "period_start", "period_end"], if_not_exists=True)

    # ── 12. canonical_invoices ────────────────────────────────────────────────
    op.create_table(
        "canonical_invoices",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("billing_account_id", sa.UUID(as_uuid=True), sa.ForeignKey("billing_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("subscription_id", sa.UUID(as_uuid=True), sa.ForeignKey("canonical_subscriptions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("billing_period_id", sa.UUID(as_uuid=True), sa.ForeignKey("billing_periods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_number", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(50), server_default="DRAFT", nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("subtotal", MoneyType, server_default="0.0", nullable=False),
        sa.Column("discount_amount", MoneyType, server_default="0.0", nullable=False),
        sa.Column("tax_amount", MoneyType, server_default="0.0", nullable=False),
        sa.Column("credit_amount", MoneyType, server_default="0.0", nullable=False),
        sa.Column("total", MoneyType, server_default="0.0", nullable=False),
        sa.Column("amount_paid", MoneyType, server_default="0.0", nullable=False),
        sa.Column("amount_due", MoneyType, server_default="0.0", nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("metadata_payload", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_canon_inv_org", "canonical_invoices", ["organization_id"], if_not_exists=True)
    op.create_index("ix_canon_inv_number", "canonical_invoices", ["invoice_number"], if_not_exists=True)
    op.create_index("ix_canon_inv_status", "canonical_invoices", ["status"], if_not_exists=True)

    # ── 13. canonical_invoice_lines ───────────────────────────────────────────
    op.create_table(
        "canonical_invoice_lines",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("invoice_id", sa.UUID(as_uuid=True), sa.ForeignKey("canonical_invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), server_default="1.0", nullable=False),
        sa.Column("unit_price", MoneyType, nullable=False),
        sa.Column("subtotal", MoneyType, nullable=False),
        sa.Column("discount", MoneyType, server_default="0.0", nullable=False),
        sa.Column("tax_amount", MoneyType, server_default="0.0", nullable=False),
        sa.Column("total", MoneyType, nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("plan_version_id", sa.UUID(as_uuid=True), sa.ForeignKey("plan_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("meter_id", sa.UUID(as_uuid=True), sa.ForeignKey("usage_meters.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_type", sa.String(50), nullable=True),
        sa.Column("source_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_canon_inv_lines_inv", "canonical_invoice_lines", ["invoice_id"], if_not_exists=True)

    # ── 14. credit_balances ───────────────────────────────────────────────────
    op.create_table(
        "credit_balances",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("balance", MoneyType, server_default="0.0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("organization_id", "currency", name="uq_credit_balance_org_curr"),
    )
    op.create_index("ix_credit_bal_org", "credit_balances", ["organization_id"], if_not_exists=True)

    # ── 15. credit_ledger_entries ─────────────────────────────────────────────
    op.create_table(
        "credit_ledger_entries",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_type", sa.String(50), nullable=False),
        sa.Column("amount", MoneyType, nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("balance_after", MoneyType, nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("reference_type", sa.String(50), nullable=True),
        sa.Column("reference_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_credit_ledger_org_time", "credit_ledger_entries", ["organization_id", "created_at"], if_not_exists=True)

    # ── 16. credit_notes ──────────────────────────────────────────────────────
    op.create_table(
        "credit_notes",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", sa.UUID(as_uuid=True), sa.ForeignKey("canonical_invoices.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("credit_number", sa.String(100), nullable=False, unique=True),
        sa.Column("amount", MoneyType, nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("status", sa.String(50), server_default="ISSUED", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_credit_notes_org", "credit_notes", ["organization_id"], if_not_exists=True)
    op.create_index("ix_credit_notes_inv", "credit_notes", ["invoice_id"], if_not_exists=True)

    # ── 17. billing_adjustments ───────────────────────────────────────────────
    op.create_table(
        "billing_adjustments",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("invoice_id", sa.UUID(as_uuid=True), sa.ForeignKey("canonical_invoices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("adjustment_type", sa.String(50), nullable=False),
        sa.Column("amount", MoneyType, nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.String(64), nullable=True),
        sa.Column("approved_by", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_billing_adj_org", "billing_adjustments", ["organization_id"], if_not_exists=True)

    # ── 18. entitlement_grants ────────────────────────────────────────────────
    op.create_table(
        "entitlement_grants",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("entitlement_key", sa.String(100), nullable=False),
        sa.Column("limit_value", sa.Integer(), nullable=True),
        sa.Column("boolean_value", sa.Boolean(), nullable=True),
        sa.Column("source", sa.String(50), server_default="MANUAL_OVERRIDE", nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ent_grants_org_key", "entitlement_grants", ["organization_id", "entitlement_key"], if_not_exists=True)

    # ── 19. entitlement_consumptions ──────────────────────────────────────────
    op.create_table(
        "entitlement_consumptions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("entitlement_key", sa.String(100), nullable=False),
        sa.Column("billing_period_id", sa.UUID(as_uuid=True), sa.ForeignKey("billing_periods.id", ondelete="SET NULL"), nullable=True),
        sa.Column("quantity", sa.Integer(), server_default="1", nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("action_reference", sa.String(255), nullable=True),
    )
    op.create_index("ix_ent_consump_org_key_time", "entitlement_consumptions", ["organization_id", "entitlement_key", "consumed_at"], if_not_exists=True)

    # ── 20. cost_events ───────────────────────────────────────────────────────
    op.create_table(
        "cost_events",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("service", sa.String(50), nullable=False),
        sa.Column("vendor", sa.String(50), nullable=False),
        sa.Column("unit", sa.String(50), nullable=False),
        sa.Column("quantity", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("unit_cost", MoneyType, nullable=False),
        sa.Column("total_cost", MoneyType, nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source_reference", sa.String(255), nullable=True),
        sa.Column("metadata_payload", sa.JSON(), server_default="{}", nullable=False),
    )
    op.create_index("ix_cost_events_org_service_time", "cost_events", ["organization_id", "service", "occurred_at"], if_not_exists=True)

    # ── 21. unit_economics_snapshots ──────────────────────────────────────────
    op.create_table(
        "unit_economics_snapshots",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("organization_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(3), server_default="INR", nullable=False),
        sa.Column("mrr", MoneyType, server_default="0.0", nullable=False),
        sa.Column("arr", MoneyType, server_default="0.0", nullable=False),
        sa.Column("gross_revenue", MoneyType, server_default="0.0", nullable=False),
        sa.Column("net_revenue", MoneyType, server_default="0.0", nullable=False),
        sa.Column("refunds", MoneyType, server_default="0.0", nullable=False),
        sa.Column("credits", MoneyType, server_default="0.0", nullable=False),
        sa.Column("payment_fees", MoneyType, server_default="0.0", nullable=False),
        sa.Column("ai_cost", MoneyType, server_default="0.0", nullable=False),
        sa.Column("messaging_cost", MoneyType, server_default="0.0", nullable=False),
        sa.Column("storage_cost", MoneyType, server_default="0.0", nullable=False),
        sa.Column("other_cost", MoneyType, server_default="0.0", nullable=False),
        sa.Column("total_variable_cost", MoneyType, server_default="0.0", nullable=False),
        sa.Column("gross_profit", MoneyType, server_default="0.0", nullable=False),
        sa.Column("gross_margin_pct", PctType, server_default="0.0", nullable=False),
        sa.Column("cac", MoneyType, nullable=True),
        sa.Column("ltv", MoneyType, nullable=True),
        sa.Column("data_quality_notes", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_unit_econ_snapshot_org_period", "unit_economics_snapshots", ["organization_id", "period_start", "period_end"], if_not_exists=True)


def downgrade():
    op.drop_table("unit_economics_snapshots")
    op.drop_table("cost_events")
    op.drop_table("entitlement_consumptions")
    op.drop_table("entitlement_grants")
    op.drop_table("billing_adjustments")
    op.drop_table("credit_notes")
    op.drop_table("credit_ledger_entries")
    op.drop_table("credit_balances")
    op.drop_table("canonical_invoice_lines")
    op.drop_table("canonical_invoices")
    op.drop_table("usage_aggregates")
    op.drop_table("usage_events")
    op.drop_table("usage_meters")
    op.drop_table("billing_periods")
    op.drop_table("subscription_items")
    op.drop_table("canonical_subscriptions")
    op.drop_table("plan_entitlements")
    op.drop_table("plan_versions")
    op.drop_table("plans")
    op.drop_table("billing_accounts")
    op.drop_table("billing_customers")
