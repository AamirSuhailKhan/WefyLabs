"""Reconcile SourceAttribution column types and referential integrity.

Revision ID: 0049_source_attribution_uuid_parity
Revises: 0048_schema_reconciliation_parity
Create Date: 2026-10-28 21:15:00.000000

Captures and formalizes schema adjustments:
1. Reconciles source_attributions.organization_id from VARCHAR(36) to native UUID
   with FK to organizations.id (ON DELETE CASCADE)
2. Reconciles source_attributions.lead_id from VARCHAR(36) to native UUID (nullable)
   with FK to leads.id (ON DELETE SET NULL)
3. Preserves historical marketing attribution even if lead records are purged or merged
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0049_source_attribution_uuid_parity"
down_revision: Union[str, None] = "0048_schema_reconciliation_parity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Controlled lock & statement timeouts to prevent connection pool starvation or indefinite waits
        op.execute("SET lock_timeout = '5s';")
        op.execute("SET statement_timeout = '15s';")
        op.execute("ALTER TABLE source_attributions ALTER COLUMN lead_id DROP NOT NULL;")
        op.execute(
            "ALTER TABLE source_attributions "
            "ALTER COLUMN organization_id TYPE uuid USING organization_id::uuid, "
            "ALTER COLUMN lead_id TYPE uuid USING lead_id::uuid;"
        )
        op.execute(
            "ALTER TABLE source_attributions "
            "DROP CONSTRAINT IF EXISTS fk_source_attributions_organization_id;"
        )
        op.execute(
            "ALTER TABLE source_attributions "
            "ADD CONSTRAINT fk_source_attributions_organization_id "
            "FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;"
        )
        # Reconcile orphaned lead references where the lead entity was purged/deleted prior to FK enforcement
        # Preserves historical marketing attribution while satisfying referential integrity
        op.execute(
            "UPDATE source_attributions "
            "SET lead_id = NULL "
            "WHERE lead_id IS NOT NULL "
            "  AND NOT EXISTS (SELECT 1 FROM leads WHERE leads.id = source_attributions.lead_id);"
        )
        op.execute(
            "ALTER TABLE source_attributions "
            "DROP CONSTRAINT IF EXISTS fk_source_attributions_lead_id;"
        )
        op.execute(
            "ALTER TABLE source_attributions "
            "ADD CONSTRAINT fk_source_attributions_lead_id "
            "FOREIGN KEY (lead_id) REFERENCES leads(id) ON DELETE SET NULL;"
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Controlled lock & statement timeouts
        op.execute("SET lock_timeout = '5s';")
        op.execute("SET statement_timeout = '15s';")
        # Strategy 1 Safety Guard: Fail-closed before dropping constraints if nulls exist
        null_count = bind.execute(
            sa.text("SELECT count(*) FROM source_attributions WHERE lead_id IS NULL;")
        ).scalar()
        if null_count and null_count > 0:
            raise RuntimeError(
                f"DOWNGRADE ABORTED: Found {null_count} source_attributions records with NULL lead_id. "
                "PostgreSQL 0048 schema enforces NOT NULL on lead_id. "
                "To roll back safely without data loss, adopt the forward-recovery pattern (Migration 0050) "
                "or restore original lead entities."
            )

        op.execute(
            "ALTER TABLE source_attributions "
            "DROP CONSTRAINT IF EXISTS fk_source_attributions_lead_id, "
            "DROP CONSTRAINT IF EXISTS fk_source_attributions_organization_id;"
        )
        op.execute(
            "ALTER TABLE source_attributions "
            "ALTER COLUMN lead_id TYPE character varying(36) USING lead_id::text, "
            "ALTER COLUMN organization_id TYPE character varying(36) USING organization_id::text;"
        )
        op.execute("ALTER TABLE source_attributions ALTER COLUMN lead_id SET NOT NULL;")

