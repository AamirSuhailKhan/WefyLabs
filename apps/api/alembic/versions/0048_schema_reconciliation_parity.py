"""Reconcile lead indexes, broker nullability, and city default for schema parity.

Revision ID: 0048_schema_reconciliation_parity
Revises: 0047_webhook_event_claims
Create Date: 2026-10-25 15:30:00.000000

Captures and formalizes schema adjustments:
1. Adds 3 missing lead performance indexes declared in ORM:
   - ix_leads_country_market on (country_code, market_id)
   - ix_leads_deleted_at on (deleted_at)
   - ix_leads_org_status on (organization_id, status)
2. Relaxes brokers contact nullability to support un-onboarded Google OAuth logins:
   - brokers.phone -> nullable=True
   - brokers.whatsapp_number -> nullable=True
   - brokers.city -> nullable=True
   - brokers.city -> drops legacy hardcoded 'Bengaluru' server default
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0048_schema_reconciliation_parity"
down_revision: Union[str, None] = "0047_webhook_event_claims"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── 1. Create missing lead indexes ──────────────────────────────────────
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_country_market "
        "ON leads (country_code, market_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_deleted_at "
        "ON leads (deleted_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_leads_org_status "
        "ON leads (organization_id, status)"
    )

    # ── 2. Reconcile broker contact nullability for Google OAuth onboarding ──
    op.execute("ALTER TABLE brokers ALTER COLUMN phone DROP NOT NULL")
    op.execute("ALTER TABLE brokers ALTER COLUMN whatsapp_number DROP NOT NULL")
    op.execute("ALTER TABLE brokers ALTER COLUMN city DROP NOT NULL")
    op.execute("ALTER TABLE brokers ALTER COLUMN city DROP DEFAULT")


def downgrade() -> None:
    # ── 1. Drop added lead indexes ──────────────────────────────────────────
    op.execute("DROP INDEX IF EXISTS ix_leads_org_status")
    op.execute("DROP INDEX IF EXISTS ix_leads_deleted_at")
    op.execute("DROP INDEX IF EXISTS ix_leads_country_market")

    # ── 2. Restore city server default ──────────────────────────────────────
    op.execute("ALTER TABLE brokers ALTER COLUMN city SET DEFAULT 'Bengaluru'")
