"""Part 31 Customer Onboarding, Tenant Activation & Demo Mode Schema

Revision ID: 0024_onboarding_activation_demo
Revises: 0023_agent_command_center
Create Date: 2026-09-12 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision = '0024_onboarding_activation_demo'
down_revision = '0023_agent_command_center'
branch_labels = None
depends_on = None

UUIDType = UUID(as_uuid=True).with_variant(sa.CHAR(36), "sqlite")
JSONType = JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    org_cols = [c["name"] for c in inspector.get_columns("organizations")] if "organizations" in tables else []
    broker_cols = [c["name"] for c in inspector.get_columns("brokers")] if "brokers" in tables else []

    # 1. Alter organizations table
    if "organizations" in tables:
        with op.batch_alter_table("organizations") as batch_op:
            if "business_type" not in org_cols:
                batch_op.add_column(sa.Column("business_type", sa.String(50), nullable=True))
            if "currency_code" not in org_cols:
                batch_op.add_column(sa.Column("currency_code", sa.String(10), server_default="INR", nullable=True))
            if "team_size" not in org_cols:
                batch_op.add_column(sa.Column("team_size", sa.String(50), nullable=True))
            if "is_demo" not in org_cols:
                batch_op.add_column(sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False))
                batch_op.create_index("ix_organizations_is_demo", ["is_demo"])

    # 2. Alter brokers table
    if "brokers" in tables:
        with op.batch_alter_table("brokers") as batch_op:
            if "is_demo" not in broker_cols:
                batch_op.add_column(sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False))
                batch_op.create_index("ix_brokers_is_demo", ["is_demo"])

    # 3. Create onboarding_states table
    if "onboarding_states" not in tables:
        op.create_table(
            "onboarding_states",
            sa.Column("id", UUIDType, primary_key=True, nullable=False),
            sa.Column("organization_id", UUIDType, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("broker_id", UUIDType, sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("current_step", sa.String(50), server_default="ORGANIZATION_SETUP", nullable=False),
            sa.Column("completed_steps", JSONType, server_default="[]", nullable=False),
            sa.Column("skipped_steps", JSONType, server_default="[]", nullable=False),
            sa.Column("is_completed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("step_data", JSONType, server_default="{}", nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_onboarding_org", "onboarding_states", ["organization_id"])
        op.create_index("ix_onboarding_broker", "onboarding_states", ["broker_id"])
        op.create_index("ix_onboarding_completed", "onboarding_states", ["is_completed"])

    # 4. Create tenant_activations table
    if "tenant_activations" not in tables:
        op.create_table(
            "tenant_activations",
            sa.Column("id", UUIDType, primary_key=True, nullable=False),
            sa.Column("organization_id", UUIDType, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("is_activated", sa.Boolean(), server_default=sa.text("false"), nullable=False),
            sa.Column("activation_score", sa.Integer(), server_default="0", nullable=False),
            sa.Column("completed_milestones", JSONType, server_default="[]", nullable=False),
            sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("time_to_activate_seconds", sa.Integer(), nullable=True),
            sa.Column("first_property_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("first_lead_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("first_match_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("first_followup_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_activation_org", "tenant_activations", ["organization_id"])
        op.create_index("ix_activation_status", "tenant_activations", ["is_activated"])

    # 5. Create demo_sessions table
    if "demo_sessions" not in tables:
        op.create_table(
            "demo_sessions",
            sa.Column("id", UUIDType, primary_key=True, nullable=False),
            sa.Column("demo_organization_id", UUIDType, sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, unique=True),
            sa.Column("demo_broker_id", UUIDType, sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
            sa.Column("session_token", sa.String(64), nullable=False, unique=True),
            sa.Column("status", sa.String(20), server_default="active", nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by_ip", sa.String(45), nullable=True),
            sa.Column("metadata_json", JSONType, server_default="{}", nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
        op.create_index("ix_demo_sessions_token", "demo_sessions", ["session_token"])
        op.create_index("ix_demo_sessions_status", "demo_sessions", ["status"])
        op.create_index("ix_demo_sessions_expires", "demo_sessions", ["expires_at"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "demo_sessions" in tables:
        op.drop_table("demo_sessions")
    if "tenant_activations" in tables:
        op.drop_table("tenant_activations")
    if "onboarding_states" in tables:
        op.drop_table("onboarding_states")

    if "brokers" in tables:
        broker_cols = [c["name"] for c in inspector.get_columns("brokers")]
        with op.batch_alter_table("brokers") as batch_op:
            if "is_demo" in broker_cols:
                batch_op.drop_index("ix_brokers_is_demo")
                batch_op.drop_column("is_demo")

    if "organizations" in tables:
        org_cols = [c["name"] for c in inspector.get_columns("organizations")]
        with op.batch_alter_table("organizations") as batch_op:
            if "is_demo" in org_cols:
                batch_op.drop_index("ix_organizations_is_demo")
                batch_op.drop_column("is_demo")
            if "team_size" in org_cols:
                batch_op.drop_column("team_size")
            if "currency_code" in org_cols:
                batch_op.drop_column("currency_code")
            if "business_type" in org_cols:
                batch_op.drop_column("business_type")
