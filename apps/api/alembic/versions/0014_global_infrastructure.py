"""
Alembic Migration — Part 14: Global Multi-Country Infrastructure & Localization Engine
=======================================================================================
Revision: 0014_global_infrastructure
Creates:
  - countries
  - markets
  - market_configurations
  - country_configuration_versions
  - currencies
  - exchange_rates
  - exchange_rate_snapshots
  - holiday_calendars
  - holidays
  - translations
  - property_schemas
  - property_fields
  - provider_configurations
  - provider_health
  - compliance_policies
  - consent_records
  - data_residency_policies
  - regional_pipelines
  - regional_pipeline_stages
  - market_feature_flags
  - market_rollouts

Modifies:
  - leads: +country_code, +market_id, +locale, +country_confidence, +country_inference_source, +budget_currency
           -ck_leads_property_type, -ck_leads_pipeline_stage, -ck_leads_source
  - organizations: +operating_market_ids, +reporting_currency_code, +default_timezone, +data_residency_region
  - property_listings: +country_code, +market_id, +extended_fields, currency→currency_code, built_up_area_sqft→area_value+area_unit
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# ──────────────────────────────────────────────────────────────────────────────
revision = "0014_global_infrastructure"
down_revision = "0013_ai_memory_engine"
branch_labels = None
depends_on = None
# ──────────────────────────────────────────────────────────────────────────────


def upgrade() -> None:
    conn = op.get_bind()

    # ─────────────────────────────────────────────────────────────────────────
    # CURRENCIES
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "currencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("code", sa.String(3), nullable=False, unique=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("native_name", sa.String(100), nullable=True),
        sa.Column("symbol", sa.String(10), nullable=False),
        sa.Column("symbol_native", sa.String(10), nullable=True),
        sa.Column("decimal_digits", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("display_unit", sa.String(30), nullable=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index("ix_currencies_code", "currencies", ["code"], unique=True)

    # ─────────────────────────────────────────────────────────────────────────
    # COUNTRIES
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "countries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("iso_alpha2", sa.String(2), nullable=False, unique=True),
        sa.Column("iso_alpha3", sa.String(3), nullable=True),
        sa.Column("numeric_code", sa.String(3), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("native_name", sa.String(100), nullable=True),
        sa.Column("flag_emoji", sa.String(10), nullable=True),
        sa.Column("default_currency_code", sa.String(3), nullable=False),
        sa.Column("supported_currency_codes", postgresql.ARRAY(sa.String(3)), nullable=True),
        sa.Column("default_timezone", sa.String(100), nullable=False),
        sa.Column("supported_timezones", postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column("default_language_code", sa.String(10), nullable=False, server_default="en"),
        sa.Column("supported_language_codes", postgresql.ARRAY(sa.String(10)), nullable=True),
        sa.Column("is_rtl", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("date_format", sa.String(20), nullable=False, server_default="DD/MM/YYYY"),
        sa.Column("phone_country_code", sa.String(5), nullable=True),
        sa.Column("launch_status", sa.String(20), nullable=False, server_default="PLANNED"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "launch_status IN ('PLANNED', 'INTERNAL', 'BETA', 'ACTIVE', 'SUSPENDED')",
            name="ck_countries_launch_status"
        ),
    )
    op.create_index("ix_countries_iso_alpha2", "countries", ["iso_alpha2"], unique=True)
    op.create_index("ix_countries_is_enabled", "countries", ["is_enabled"])

    # ─────────────────────────────────────────────────────────────────────────
    # MARKETS
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("country_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("countries.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("timezone", sa.String(100), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("language_codes", postgresql.ARRAY(sa.String(10)), nullable=True),
        sa.Column("weekend_days", postgresql.ARRAY(sa.Integer()), nullable=True),  # 0=Mon,...,6=Sun
        sa.Column("property_type_codes", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("lead_source_codes", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("launch_status", sa.String(20), nullable=False, server_default="PLANNED"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_markets_slug", "markets", ["slug"], unique=True)
    op.create_index("ix_markets_country_id", "markets", ["country_id"])

    # ─────────────────────────────────────────────────────────────────────────
    # MARKET CONFIGURATIONS
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "market_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("override_currency_code", sa.String(3), nullable=True),
        sa.Column("override_timezone", sa.String(100), nullable=True),
        sa.Column("override_property_types", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("override_lead_sources", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("additional_config", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # MARKET ROLLOUTS
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "market_rollouts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rollout_status", sa.String(20), nullable=False, server_default="INTERNAL"),
        sa.Column("checklist_completed", postgresql.JSONB(), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("organization_id", "market_id", name="uq_market_rollouts_org_market"),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # EXCHANGE RATES & SNAPSHOTS
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "exchange_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("rate_type", sa.String(20), nullable=False, server_default="MARKET"),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_exchange_rates_pair_active", "exchange_rates", ["base_currency", "quote_currency", "is_active"])

    op.create_table(
        "exchange_rate_snapshots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("base_currency", sa.String(3), nullable=False),
        sa.Column("quote_currency", sa.String(3), nullable=False),
        sa.Column("rate", sa.Numeric(precision=20, scale=8), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_exchange_rate_snapshots_pair_date", "exchange_rate_snapshots", ["base_currency", "quote_currency", "snapshot_date"])

    # ─────────────────────────────────────────────────────────────────────────
    # HOLIDAY CALENDARS & HOLIDAYS
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "holiday_calendars",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_holiday_calendars_market_year", "holiday_calendars", ["market_id", "year"])

    op.create_table(
        "holidays",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("calendar_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("holiday_calendars.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("holiday_type", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # TRANSLATIONS
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "translations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("namespace", sa.String(100), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("namespace", "key", "locale", name="uq_translations_ns_key_locale"),
    )
    op.create_index("ix_translations_ns_locale", "translations", ["namespace", "locale"])

    # ─────────────────────────────────────────────────────────────────────────
    # PROPERTY SCHEMAS & FIELDS
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "property_schemas",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("country_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("countries.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("property_type_codes", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("area_units", postgresql.ARRAY(sa.String(20)), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "property_fields",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("schema_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("property_schemas.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_key", sa.String(100), nullable=False),
        sa.Column("field_label", sa.String(200), nullable=False),
        sa.Column("field_type", sa.String(30), nullable=False),  # text|number|select|boolean
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("select_options", postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # PROVIDER CONFIGURATIONS & HEALTH
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "provider_configurations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider_type", sa.String(30), nullable=False),  # PAYMENT|WHATSAPP|SMS|EMAIL|FX
        sa.Column("provider_code", sa.String(50), nullable=False),  # razorpay|stripe|tap|360dialog
        sa.Column("priority", sa.Integer(), nullable=False, server_default="1"),  # 1=primary, 2=secondary, 3=fallback
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("config_json", postgresql.JSONB(), nullable=True),
        sa.Column("secret_ref", sa.String(255), nullable=True),  # vault path
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_provider_configs_org_market_type", "provider_configurations", ["organization_id", "market_id", "provider_type"])

    op.create_table(
        "provider_health",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("provider_configuration_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("provider_configurations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # COMPLIANCE POLICIES
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "compliance_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("country_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("countries.id", ondelete="CASCADE"), nullable=True),
        sa.Column("policy_key", sa.String(100), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("rule_json", postgresql.JSONB(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_compliance_policies_category_status", "compliance_policies", ["category", "status"])

    # ─────────────────────────────────────────────────────────────────────────
    # CONSENT RECORDS
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "consent_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("purpose", sa.String(50), nullable=False, server_default="marketing"),
        sa.Column("source", sa.String(30), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('GRANTED', 'DENIED', 'WITHDRAWN', 'EXPIRED')",
            name="ck_consent_records_status"
        ),
    )
    op.create_index("ix_consent_records_lead_channel", "consent_records", ["lead_id", "channel", "purpose"])

    # ─────────────────────────────────────────────────────────────────────────
    # DATA RESIDENCY POLICIES
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "data_residency_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("country_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("countries.id", ondelete="CASCADE"), nullable=True),
        sa.Column("policy_key", sa.String(100), nullable=False),
        sa.Column("storage_region", sa.String(50), nullable=False),
        sa.Column("allowed_transfer_regions", postgresql.ARRAY(sa.String(50)), nullable=True),
        sa.Column("pii_fields", postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("requires_encryption", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # REGIONAL PIPELINES
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "regional_pipelines",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "regional_pipeline_stages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("pipeline_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("regional_pipelines.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_won", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allowed_next_stages", postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # MARKET FEATURE FLAGS
    # ─────────────────────────────────────────────────────────────────────────
    op.create_table(
        "market_feature_flags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("market_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("markets.id", ondelete="CASCADE"), nullable=True),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("flag_key", sa.String(100), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("config_json", postgresql.JSONB(), nullable=True),
        sa.Column("rollout_percentage", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("market_id", "organization_id", "flag_key", name="uq_market_feature_flags"),
    )

    # ─────────────────────────────────────────────────────────────────────────
    # ALTER EXISTING TABLES — LEADS
    # ─────────────────────────────────────────────────────────────────────────

    # Drop hardcoded India-specific constraints
    _drop_constraint_if_exists(conn, "leads", "ck_leads_property_type")
    _drop_constraint_if_exists(conn, "leads", "ck_leads_pipeline_stage")
    _drop_constraint_if_exists(conn, "leads", "ck_leads_source")

    # Widen pipeline_stage column (was String(30))
    op.alter_column("leads", "pipeline_stage", type_=sa.String(100))

    # Add global fields
    op.add_column("leads", sa.Column("country_code", sa.String(2), nullable=True))
    op.add_column("leads", sa.Column("market_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("leads", sa.Column("locale", sa.String(10), nullable=True))
    op.add_column("leads", sa.Column("country_confidence", sa.Float(), nullable=False, server_default="0.0"))
    op.add_column("leads", sa.Column("country_inference_source", sa.String(30), nullable=True))
    op.add_column("leads", sa.Column("budget_currency", sa.String(3), nullable=True))

    op.create_index("ix_leads_country_code", "leads", ["country_code"])
    op.create_index("ix_leads_market_id", "leads", ["market_id"])
    op.create_index("ix_leads_country_market", "leads", ["country_code", "market_id"])

    # ─────────────────────────────────────────────────────────────────────────
    # ALTER EXISTING TABLES — ORGANIZATIONS
    # ─────────────────────────────────────────────────────────────────────────

    # country_code — change from String(2) NOT NULL DEFAULT "IN" → nullable, no default
    op.alter_column("organizations", "country_code", nullable=True, server_default=None)

    op.add_column("organizations", sa.Column("operating_market_ids", postgresql.JSONB(), nullable=True))
    op.add_column("organizations", sa.Column("reporting_currency_code", sa.String(3), nullable=True))
    op.add_column("organizations", sa.Column("default_timezone", sa.String(100), nullable=True))
    op.add_column("organizations", sa.Column("data_residency_region", sa.String(50), nullable=True))

    # ─────────────────────────────────────────────────────────────────────────
    # ALTER EXISTING TABLES — PROPERTY LISTINGS
    # ─────────────────────────────────────────────────────────────────────────

    # Rename currency → currency_code (no default)
    _rename_column_if_exists(conn, "property_listings", "currency", "currency_code")
    op.alter_column("property_listings", "currency_code", server_default=None)

    # Rename built_up_area_sqft → area_value; add area_unit
    _rename_column_if_exists(conn, "property_listings", "built_up_area_sqft", "area_value")
    _add_column_if_not_exists(conn, "property_listings", "area_unit", "VARCHAR(20) NOT NULL DEFAULT 'sqft'")

    # City/locality — make nullable (remove Dubai/Dubai Marina defaults)
    op.alter_column("property_listings", "city", nullable=True, server_default=None)
    op.alter_column("property_listings", "locality", nullable=True, server_default=None)

    # Widen property_type (was String(50) → String(100))
    op.alter_column("property_listings", "property_type", type_=sa.String(100))

    # Add global fields
    op.add_column("property_listings", sa.Column("country_code", sa.String(2), nullable=True))
    op.add_column("property_listings", sa.Column("market_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("property_listings", sa.Column("extended_fields", postgresql.JSONB(), nullable=True))

    op.create_index("ix_property_listings_country_code", "property_listings", ["country_code"])
    op.create_index("ix_property_listings_market_id", "property_listings", ["market_id"])


def downgrade() -> None:
    """
    Rollback this migration.
    IMPORTANT: Column drops from leads/organizations/property_listings are irreversible
    if data exists. Run only in development/test environments.
    """
    conn = op.get_bind()

    # Remove new indexes and columns from existing tables
    op.drop_index("ix_property_listings_market_id", "property_listings")
    op.drop_index("ix_property_listings_country_code", "property_listings")
    op.drop_column("property_listings", "extended_fields")
    op.drop_column("property_listings", "market_id")
    op.drop_column("property_listings", "country_code")

    op.drop_index("ix_leads_country_market", "leads")
    op.drop_index("ix_leads_market_id", "leads")
    op.drop_index("ix_leads_country_code", "leads")
    op.drop_column("leads", "budget_currency")
    op.drop_column("leads", "country_inference_source")
    op.drop_column("leads", "country_confidence")
    op.drop_column("leads", "locale")
    op.drop_column("leads", "market_id")
    op.drop_column("leads", "country_code")

    op.drop_column("organizations", "data_residency_region")
    op.drop_column("organizations", "default_timezone")
    op.drop_column("organizations", "reporting_currency_code")
    op.drop_column("organizations", "operating_market_ids")

    # Drop new tables (reverse order to respect FK constraints)
    for table in [
        "market_feature_flags", "regional_pipeline_stages", "regional_pipelines",
        "data_residency_policies", "consent_records", "compliance_policies",
        "provider_health", "provider_configurations", "property_fields",
        "property_schemas", "translations", "holidays", "holiday_calendars",
        "exchange_rate_snapshots", "exchange_rates", "market_rollouts",
        "market_configurations", "markets", "countries", "currencies",
    ]:
        op.drop_table(table)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _drop_constraint_if_exists(conn, table: str, name: str):
    """Drop a constraint only if it exists — safe for re-runs."""
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.table_constraints "
        "WHERE constraint_name = :name AND table_name = :table"
    ), {"name": name, "table": table})
    if result.scalar() > 0:
        op.drop_constraint(name, table)


def _rename_column_if_exists(conn, table: str, old_name: str, new_name: str):
    """Rename column only if old column exists and new doesn't."""
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name = :table AND column_name = :col"
    ), {"table": table, "col": old_name})
    if result.scalar() > 0:
        result2 = conn.execute(sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_name = :table AND column_name = :col"
        ), {"table": table, "col": new_name})
        if result2.scalar() == 0:
            op.alter_column(table, old_name, new_column_name=new_name)


def _add_column_if_not_exists(conn, table: str, column_name: str, column_def: str):
    """Add column only if it doesn't already exist."""
    result = conn.execute(sa.text(
        "SELECT COUNT(*) FROM information_schema.columns "
        "WHERE table_name = :table AND column_name = :col"
    ), {"table": table, "col": column_name})
    if result.scalar() == 0:
        conn.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {column_name} {column_def}"))
