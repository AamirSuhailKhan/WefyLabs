"""Add atomic provider webhook idempotency claims.

Revision ID: 0047_webhook_event_claims
Revises: 0046_broker_google_subject
Create Date: 2026-10-21
"""
from alembic import op


revision = "0047_webhook_event_claims"
down_revision = "0046_broker_google_subject"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_event_claims (
            id VARCHAR(36) PRIMARY KEY,
            provider VARCHAR(50) NOT NULL,
            provider_event_id VARCHAR(255) NOT NULL,
            organization_id VARCHAR(36) NOT NULL,
            claimed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_webhook_event_claim_provider_org_event
                UNIQUE (provider, organization_id, provider_event_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_webhook_event_claims_organization_id "
        "ON webhook_event_claims (organization_id)"
    )
    # Seed existing completed deliveries so deploying this protection does not
    # make already-processed provider events process again after rollout.
    op.execute(
        """
        INSERT INTO webhook_event_claims (id, provider, provider_event_id, organization_id, claimed_at)
        SELECT md5(provider || ':' || COALESCE(organization_id, 'global') || ':' || provider_event_id),
               provider, provider_event_id, COALESCE(organization_id, 'global'), MIN(received_at)
        FROM raw_communication_events
        WHERE provider_event_id IS NOT NULL
          AND processing_status IN ('PROCESSED', 'DUPLICATE_IGNORED')
        GROUP BY provider, COALESCE(organization_id, 'global'), provider_event_id
        ON CONFLICT (provider, organization_id, provider_event_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_webhook_event_claims_organization_id")
    op.execute("DROP TABLE IF EXISTS webhook_event_claims")
