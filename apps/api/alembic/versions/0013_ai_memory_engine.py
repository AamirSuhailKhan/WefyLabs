"""AI Memory Engine - stub to repair broken Alembic DAG.

Revision ID: 0013_ai_memory_engine
Revises: b8e2d4f1a9c3
Create Date: 2026-08-21

STUB: This revision was missing from the repository, causing alembic
heads and alembic history to crash with KeyError: 0013_ai_memory_engine.

Reconstructed as an empty stub to repair the DAG linkage only.
No DDL is executed. All memory subsystem tables were initialized
directly via SQLAlchemy Base.metadata and are fully present in
the production Supabase database.

Memory subsystem tables present in production DB:
  memory_records, memory_evidence, memory_versions, memory_objections,
  memory_property_feedback, memory_audit_logs, memory_retention_policies,
  memory_deletion_requests
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_ai_memory_engine"
down_revision = "b8e2d4f1a9c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # STUB -- memory tables already exist in production DB.
    # This revision exists only to satisfy the Alembic DAG.
    pass


def downgrade() -> None:
    # STUB -- no-op.
    pass
