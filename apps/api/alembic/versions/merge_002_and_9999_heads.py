"""Merge Branch A (002_enterprise_foundation) and Branch B+C (9999_production_baseline)

Revision ID: merge_002_and_9999_heads
Revises: 002_enterprise_foundation, 9999_production_baseline
Create Date: 2026-08-21

Reconciles the two historical heads into a single linear head for future migrations:
  - Branch A head: 002_enterprise_foundation
  - Branch B+C head: 9999_production_baseline

IMPORTANT:
upgrade() is a no-op because both branches represent tables already existing
in the production Supabase database.
downgrade() is prohibited to prevent accidental schema teardown.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'merge_002_and_9999_heads'
down_revision: Union[str, Sequence[str], None] = ('002_enterprise_foundation', '9999_production_baseline')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op merge: all underlying tables and models already exist in production.
    pass


def downgrade() -> None:
    raise NotImplementedError(
        "Downgrade of the merge baseline is disallowed to prevent accidental data loss."
    )
