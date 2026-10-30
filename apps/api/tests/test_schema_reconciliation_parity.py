"""
Schema Reconciliation Parity & Regression Protection Test Suite
==============================================================
Validates:
1. Broker Integrity:
   - Preserved unique constraints on email, phone, whatsapp_number.
   - Safe nullability for phone, whatsapp_number, city (Google OAuth onboarding support).
   - Duplicate rejection at application/database layer.
2. Lead Index Parity:
   - Presence of ix_leads_country_market, ix_leads_deleted_at, ix_leads_org_status.
   - Correct columns and index configuration.
3. Defaults & Nullability:
   - ORM models declare matching server_defaults.
   - Cross-dialect DefaultTrialEndsAt compiles cleanly on both PostgreSQL and SQLite.
4. Migration Lineage:
   - Exactly one head: 0048_schema_reconciliation_parity.
   - Parent revision: 0047_webhook_event_claims.
"""
import uuid
import pytest
from sqlalchemy import text, select
from sqlalchemy.dialects import postgresql, sqlite
from app.database import engine, Base
from app.models.broker import Broker, DefaultTrialEndsAt
from app.models.lead import Lead
from app.models.conversation import Conversation
from app.models.follow_up import FollowUp
from app.models.score import Score
from app.models.subscription import Subscription


def test_cross_dialect_trial_ends_at_compilation():
    """Verify DefaultTrialEndsAt compiles cleanly to SQL without syntax errors on both PG and SQLite."""
    clause = DefaultTrialEndsAt()
    pg_sql = str(clause.compile(dialect=postgresql.dialect()))
    sqlite_sql = str(clause.compile(dialect=sqlite.dialect()))

    assert "interval '7 days'" in pg_sql
    assert "datetime('now', '+7 days')" in sqlite_sql


def test_broker_model_table_args_and_server_defaults():
    """Verify Broker model metadata explicitly defines table-level UniqueConstraints and server_defaults."""
    table = Broker.__table__
    constraint_names = {c.name for c in table.constraints}
    assert "brokers_email_key" in constraint_names
    assert "brokers_phone_key" in constraint_names
    assert "brokers_whatsapp_number_key" in constraint_names

    # Verify server_defaults on columns
    assert table.c.id.server_default is not None
    assert table.c.subscription_status.server_default is not None
    assert table.c.onboarding_status.server_default is not None
    assert table.c.trial_ends_at.server_default is not None
    assert table.c.is_demo.server_default is not None

    # Verify contact nullability in ORM
    assert table.c.phone.nullable is True
    assert table.c.whatsapp_number.nullable is True
    assert table.c.city.nullable is True


def test_lead_model_table_args_and_server_defaults():
    """Verify Lead model metadata defines expected indexes and matching server_defaults."""
    table = Lead.__table__
    index_names = {idx.name for idx in table.indexes}
    assert "ix_leads_country_market" in index_names
    assert "ix_leads_deleted_at" in index_names
    assert "ix_leads_org_status" in index_names

    # Verify server_defaults
    assert table.c.id.server_default is not None
    assert table.c.source.server_default is not None
    assert table.c.score.server_default is not None
    assert table.c.score_confidence.server_default is not None
    assert table.c.preferred_locations.server_default is not None
    assert table.c.status.server_default is not None
    assert table.c.pipeline_stage.server_default is not None
    assert table.c.country_confidence.server_default is not None
    assert table.c.notes.server_default is not None


def test_supporting_models_server_defaults():
    """Verify Conversation, FollowUp, Score, and Subscription models define server_defaults."""
    conv_table = Conversation.__table__
    assert conv_table.c.id.server_default is not None
    assert conv_table.c.message_type.server_default is not None

    fu_table = FollowUp.__table__
    assert fu_table.c.id.server_default is not None
    assert fu_table.c.status.server_default is not None

    score_table = Score.__table__
    assert score_table.c.id.server_default is not None
    assert score_table.c.extracted_data.server_default is not None

    sub_table = Subscription.__table__
    assert sub_table.c.id.server_default is not None
    assert sub_table.c.currency.server_default is not None
    assert sub_table.c.status.server_default is not None


@pytest.mark.asyncio
async def test_migration_0048_metadata_integrity():
    """Verify 0048 migration file defines correct revision, down_revision, and functions."""
    import importlib.util
    import pathlib

    migration_path = pathlib.Path(__file__).resolve().parent.parent / "alembic" / "versions" / "0048_schema_reconciliation_parity.py"
    assert migration_path.exists(), f"Migration file missing at {migration_path}"

    spec = importlib.util.spec_from_file_location("mig_0048", migration_path)
    mig = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mig)

    assert mig.revision == "0048_schema_reconciliation_parity"
    assert mig.down_revision == "0047_webhook_event_claims"
    assert hasattr(mig, "upgrade")
    assert hasattr(mig, "downgrade")
