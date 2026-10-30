"""Reconcile broker and subscription plan and status check constraints with modern application domain.

Revision ID: 0050_broker_subscription_constraint_parity
Revises: 0049_source_attribution_uuid_parity
Create Date: 2026-10-29 15:30:00.000000

Captures and formalizes schema adjustments:
1. Reconciles ck_brokers_subscription_status to include ('trial', 'active', 'paused', 'past_due', 'cancelled', 'expired')
2. Reconciles ck_brokers_subscription_plan to include ('monthly', 'annual', 'starter', 'professional', 'starter_monthly', 'starter_annual', 'pro_monthly', 'pro_annual', 'premium_custom')
3. Adds ck_brokers_onboarding_status for ('AUTHENTICATED_NOT_ONBOARDED', 'ONBOARDING_IN_PROGRESS', 'ONBOARDED', 'SUSPENDED')
4. Reconciles ck_subscriptions_status to include ('created', 'active', 'paused', 'past_due', 'cancelled', 'completed', 'expired')
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0050_broker_subscription_constraint_parity"
down_revision: Union[str, None] = "0049_source_attribution_uuid_parity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Controlled lock & statement timeouts to prevent connection pool starvation or indefinite waits
        op.execute("SET lock_timeout = '5s';")
        op.execute("SET statement_timeout = '15s';")

        # 1. ck_brokers_subscription_status
        op.execute("ALTER TABLE brokers DROP CONSTRAINT IF EXISTS ck_brokers_subscription_status;")
        op.execute(
            "ALTER TABLE brokers ADD CONSTRAINT ck_brokers_subscription_status "
            "CHECK (subscription_status IN ('trial', 'active', 'paused', 'past_due', 'cancelled', 'expired'));"
        )

        # 2. ck_brokers_subscription_plan
        op.execute("ALTER TABLE brokers DROP CONSTRAINT IF EXISTS ck_brokers_subscription_plan;")
        op.execute(
            "ALTER TABLE brokers ADD CONSTRAINT ck_brokers_subscription_plan "
            "CHECK (subscription_plan IS NULL OR subscription_plan IN ("
            "'monthly', 'annual', 'starter', 'professional', 'starter_monthly', 'starter_annual', "
            "'pro_monthly', 'pro_annual', 'premium_custom'));"
        )

        # 3. ck_brokers_onboarding_status
        op.execute("ALTER TABLE brokers DROP CONSTRAINT IF EXISTS ck_brokers_onboarding_status;")
        op.execute(
            "ALTER TABLE brokers ADD CONSTRAINT ck_brokers_onboarding_status "
            "CHECK (onboarding_status IN ('AUTHENTICATED_NOT_ONBOARDED', 'ONBOARDING_IN_PROGRESS', 'ONBOARDED', 'SUSPENDED'));"
        )

        # 4. ck_subscriptions_status
        op.execute("ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS ck_subscriptions_status;")
        op.execute(
            "ALTER TABLE subscriptions ADD CONSTRAINT ck_subscriptions_status "
            "CHECK (status IN ('created', 'active', 'paused', 'past_due', 'cancelled', 'completed', 'expired'));"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("SET lock_timeout = '5s';")
        op.execute("SET statement_timeout = '15s';")

        # Downgrade Safeguards: Fail-closed before narrowing check constraints if modern values exist
        violating_broker_status = bind.execute(
            sa.text("SELECT count(*) FROM brokers WHERE subscription_status NOT IN ('trial', 'active', 'cancelled', 'expired');")
        ).scalar()
        if violating_broker_status and violating_broker_status > 0:
            raise RuntimeError(
                f"DOWNGRADE ABORTED: Found {violating_broker_status} brokers with modern subscription_status ('paused', 'past_due'). "
                "Legacy 001 constraints would fail and cause data corruption."
            )

        violating_broker_plans = bind.execute(
            sa.text("SELECT count(*) FROM brokers WHERE subscription_plan IS NOT NULL AND subscription_plan NOT IN ('monthly', 'annual');")
        ).scalar()
        if violating_broker_plans and violating_broker_plans > 0:
            raise RuntimeError(
                f"DOWNGRADE ABORTED: Found {violating_broker_plans} brokers with modern subscription_plan ('pro_monthly', 'starter', etc.). "
                "Legacy 001 constraints would fail."
            )

        violating_sub_status = bind.execute(
            sa.text("SELECT count(*) FROM subscriptions WHERE status NOT IN ('created', 'active', 'cancelled', 'completed');")
        ).scalar()
        if violating_sub_status and violating_sub_status > 0:
            raise RuntimeError(
                f"DOWNGRADE ABORTED: Found {violating_sub_status} subscriptions with modern status ('paused', 'past_due', 'expired'). "
                "Legacy 001 constraints would fail."
            )

        # Revert to 001 constraints
        op.execute("ALTER TABLE brokers DROP CONSTRAINT IF EXISTS ck_brokers_onboarding_status;")

        op.execute("ALTER TABLE brokers DROP CONSTRAINT IF EXISTS ck_brokers_subscription_status;")
        op.execute(
            "ALTER TABLE brokers ADD CONSTRAINT ck_brokers_subscription_status "
            "CHECK (subscription_status IN ('trial', 'active', 'cancelled', 'expired'));"
        )

        op.execute("ALTER TABLE brokers DROP CONSTRAINT IF EXISTS ck_brokers_subscription_plan;")
        op.execute(
            "ALTER TABLE brokers ADD CONSTRAINT ck_brokers_subscription_plan "
            "CHECK (subscription_plan IS NULL OR subscription_plan IN ('monthly', 'annual'));"
        )

        op.execute("ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS ck_subscriptions_status;")
        op.execute(
            "ALTER TABLE subscriptions ADD CONSTRAINT ck_subscriptions_status "
            "CHECK (status IN ('created', 'active', 'cancelled', 'completed'));"
        )

