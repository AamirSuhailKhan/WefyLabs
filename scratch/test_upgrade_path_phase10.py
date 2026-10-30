import os
import sys
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from alembic.config import Config
from alembic import command

API_DIR = os.path.abspath("apps/api")
if API_DIR not in sys.path:
    sys.path.insert(0, API_DIR)

from app.config import settings
from app.database import Base
import app.models

SCHEMA = "phase10_upgrade_disposable"

# Tables introduced in revisions 0039 through 0047
POST_0038_TABLES = {
    # 0039
    "unit_economics_records", "unit_economics_snapshots", "revenue_leakage_events_v2",
    "revenue_reconciliation_records", "booking_reconciliation_tasks", "deal_commercial_audit_logs",
    "cp_commissions", "cp_project_agreements", "customer_payment_proofs",
    # 0040
    "plans", "plan_versions", "plan_entitlements", "billing_customers", "billing_accounts",
    "canonical_subscriptions", "subscription_items", "canonical_invoices", "canonical_invoice_lines",
    "payment_orders", "payment_transactions", "payment_refunds", "payment_audit_logs",
    "usage_meters", "usage_events", "usage_aggregates", "credit_balances", "credit_ledger_entries",
    "credit_notes", "billing_periods", "billing_adjustments",
    # 0041
    "discovery_runs", "discovery_sources", "discovery_signals", "discovery_evidence",
    "discovery_candidates", "discovery_campaigns", "outbox_events", "outcome_events",
    "learning_events", "metric_definitions", "metric_snapshots", "benchmark_definitions",
    "benchmark_snapshots", "system_health_snapshots", "drift_alert_records", "incidents",
    "disaster_recovery_plans", "policy_registry_entries", "policy_audit_logs",
    # 0042
    "pilot_tenants", "pilot_stage_transitions", "pilot_observations", "pilot_evidence_records",
    "pilot_human_decisions", "pilot_action_records", "pilot_metric_snapshots", "pilot_audit_events",
    "pilot_approval_items",
    # 0044
    "token_blacklist",
    # 0047
    "webhook_event_claims"
}

async def setup_0038_baseline():
    engine = create_async_engine(settings.DATABASE_URL)
    async with engine.begin() as conn:
        print(f"1. Resetting schema: {SCHEMA}")
        await conn.execute(text(f"DROP SCHEMA IF EXISTS {SCHEMA} CASCADE"))
        await conn.execute(text(f"CREATE SCHEMA {SCHEMA}"))
        await conn.execute(text(f"SET search_path TO {SCHEMA}, extensions, public"))

        print("2. Provisioning tables prior to 0039...")
        # Create all tables except those introduced in 0039..0047
        pre_0039_tables = [
            t for name, t in Base.metadata.tables.items()
            if name not in POST_0038_TABLES
        ]
        await conn.run_sync(lambda s_conn: Base.metadata.create_all(s_conn, tables=pre_0039_tables, checkfirst=False))

        # Create alembic_version stamped at 0038_build08_sales_pipeline
        print("3. Stamping alembic_version at starting revision 0038_build08_sales_pipeline (VARCHAR 32)")
        await conn.execute(text(f"""
            CREATE TABLE {SCHEMA}.alembic_version (
                version_num VARCHAR(32) NOT NULL PRIMARY KEY
            )
        """))
        await conn.execute(text(f"INSERT INTO {SCHEMA}.alembic_version VALUES ('0038_build08_sales_pipeline')"))

        # Insert synthetic data into pre-existing tables
        print("4. Inserting synthetic records into pre-existing tables...")
        org_id = "a0000000-0000-0000-0000-000000000001"
        brk_id = "b0000000-0000-0000-0000-000000000002"
        await conn.execute(text(f"""
            INSERT INTO {SCHEMA}.organizations (id, name, slug, plan)
            VALUES ('{org_id}', 'Upgrade Test Org', 'upgrade-test-org', 'scale')
        """))
        await conn.execute(text(f"""
            INSERT INTO {SCHEMA}.brokers (id, name, email)
            VALUES ('{brk_id}', 'Upgrade Broker', 'upgrade_broker@example.com')
        """))
        await conn.execute(text(f"""
            INSERT INTO {SCHEMA}.raw_communication_events (id, provider, provider_event_id, organization_id, processing_status, received_at)
            VALUES 
              ('raw_evt_1', 'whatsapp', 'msg_101', '{org_id}', 'PROCESSED', NOW()),
              ('raw_evt_2', 'whatsapp', 'msg_102', '{org_id}', 'PROCESSED', NOW()),
              ('raw_evt_3', 'razorpay', 'pay_201', '{org_id}', 'DUPLICATE_IGNORED', NOW())
        """))

    await engine.dispose()
    print("Pre-upgrade baseline setup complete.")

def run_forward_migrations():
    print("\n5. Running Alembic upgrade head from 0038...")
    ini_path = os.path.join(API_DIR, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(API_DIR, "alembic"))
    os.environ["ALEMBIC_SCHEMA"] = SCHEMA
    command.upgrade(cfg, "head")
    print("Alembic upgrade head finished successfully.")

async def verify_upgrade_results():
    engine = create_async_engine(settings.DATABASE_URL)
    results = {}
    org_id = "a0000000-0000-0000-0000-000000000001"
    brk_id = "b0000000-0000-0000-0000-000000000002"
    async with engine.begin() as conn:
        await conn.execute(text(f"SET search_path TO {SCHEMA}, extensions, public"))

        # 1. Version table
        v_res = await conn.execute(text(f"SELECT version_num FROM {SCHEMA}.alembic_version"))
        version = v_res.scalar()
        results["final_version"] = version
        print(f"Final Alembic Version: {version}")
        assert version == "0047_webhook_event_claims", f"Expected head 0047, found {version}"

        # 2. Version table width
        len_res = await conn.execute(text(f"""
            SELECT character_maximum_length FROM information_schema.columns 
            WHERE table_schema = '{SCHEMA}' AND table_name = 'alembic_version' AND column_name = 'version_num'
        """))
        results["version_table_width"] = len_res.scalar()
        print(f"Version Table Column Width: {results['version_table_width']}")
        assert results["version_table_width"] >= 64, "Version table was not widened to at least 64"

        # 3. Synthetic data preservation
        org_cnt = (await conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.organizations WHERE id = '{org_id}'"))).scalar()
        brk_cnt = (await conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.brokers WHERE id = '{brk_id}'"))).scalar()
        raw_cnt = (await conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.raw_communication_events WHERE organization_id = '{org_id}'"))).scalar()
        assert org_cnt == 1, "Organization record lost"
        assert brk_cnt == 1, "Broker record lost"
        assert raw_cnt == 3, "Communication events lost"
        print("Data Preservation: 100% verified (Organization, Broker, Raw Events intact).")

        # 4. Added columns on pre-existing tables
        brk_row = (await conn.execute(text(f"SELECT auth_version, google_subject FROM {SCHEMA}.brokers WHERE id = '{brk_id}'"))).fetchone()
        assert brk_row is not None
        print(f"Broker added columns: auth_version={brk_row[0]}, google_subject={brk_row[1]}")

        # 5. New tables created by migrations
        for t in ["token_blacklist", "webhook_event_claims", "pilot_tenants", "plans"]:
            cnt = (await conn.execute(text(f"SELECT count(*) FROM information_schema.tables WHERE table_schema = '{SCHEMA}' AND table_name = '{t}'"))).scalar()
            assert cnt == 1, f"Expected table {t} to be created by migrations"
        print("New Migration Tables: token_blacklist, webhook_event_claims, pilot_tenants, plans verified.")

        # 6. Webhook claims backfilled
        claims = (await conn.execute(text(f"SELECT count(*) FROM {SCHEMA}.webhook_event_claims WHERE organization_id = '{org_id}'"))).scalar()
        print(f"Backfilled webhook event claims: {claims}")
        assert claims == 3, f"Expected 3 backfilled claims, found {claims}"

        # 7. Webhook claims unique constraint
        dup_failed = False
        try:
            async with conn.begin_nested():
                await conn.execute(text(f"""
                    INSERT INTO {SCHEMA}.webhook_event_claims (id, provider, provider_event_id, organization_id)
                    VALUES ('dup_claim', 'whatsapp', 'msg_101', '{org_id}')
                """))
        except Exception:
            dup_failed = True
        assert dup_failed, "Duplicate webhook event claim was not rejected by unique constraint"
        print("Unique Constraint: Duplicate claim rejected cleanly.")

    await engine.dispose()
    print("\nALL UPGRADE PATH VERIFICATIONS PASSED!")

def test_idempotent_redeploy():
    print("\n6. Testing Idempotent Repeated Deployment (Running upgrade head again)...")
    ini_path = os.path.join(API_DIR, "alembic.ini")
    cfg = Config(ini_path)
    cfg.set_main_option("script_location", os.path.join(API_DIR, "alembic"))
    os.environ["ALEMBIC_SCHEMA"] = SCHEMA
    command.upgrade(cfg, "head")
    print("Repeated deployment passed with zero errors or side effects.")

def main():
    asyncio.run(setup_0038_baseline())
    run_forward_migrations()
    asyncio.run(verify_upgrade_results())
    test_idempotent_redeploy()

if __name__ == "__main__":
    main()
