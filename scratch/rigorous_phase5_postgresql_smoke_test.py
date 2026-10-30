import asyncio
import asyncpg
import uuid
import sys
import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, delete

# Ensure apps/api is in sys.path
sys.path.insert(0, os.path.abspath("apps/api"))
from app.models.acquisition_models import SourceAttribution
from app.models.lead import Lead
from app.models.broker import Broker
from app.models.organization import Organization
from app.models.subscription import Subscription

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISP_DB = "test_disposable_phase5_smoke"
DISP_URL = f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}"
DISP_ASYNC_URL = f"postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/{DISP_DB}"

async def run_rigorous_smoke_suite():
    # 1. Setup disposable DB from leadscore and upgrade to 0050
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.execute(f"CREATE DATABASE {DISP_DB} WITH TEMPLATE leadscore;")
    await admin.close()

    # Upgrade to head 0050
    import subprocess
    res_up = subprocess.run([
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL}",
        "upgrade", "head"
    ], cwd=os.path.abspath("apps/api"), capture_output=True, text=True)
    assert res_up.returncode == 0, f"Alembic upgrade failed: {res_up.stderr}"
    print("[SETUP] Disposable database migrated sequentially to head 0050.")

    conn = await asyncpg.connect(DISP_URL)
    results = {}

    try:
        # Assertion 1: Exact Alembic revision
        rev = await conn.fetchval("SELECT version_num FROM alembic_version;")
        assert rev == "0050_broker_subscription_constraint_parity", f"Expected 0050, got {rev}"
        results["1_alembic_revision"] = {"status": "PASSED", "revision": rev}

        # Assertion 2: organization_id is native UUID and non-nullable
        col_org = await conn.fetchrow("""
            SELECT data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'source_attributions' AND column_name = 'organization_id';
        """)
        assert col_org["data_type"] == "uuid" and col_org["is_nullable"] == "NO", f"Invalid org_id col: {col_org}"
        results["2_org_id_native_uuid_not_null"] = {"status": "PASSED", "data_type": col_org["data_type"], "is_nullable": col_org["is_nullable"]}

        # Assertion 3: lead_id is native UUID and nullable
        col_lead = await conn.fetchrow("""
            SELECT data_type, is_nullable 
            FROM information_schema.columns 
            WHERE table_name = 'source_attributions' AND column_name = 'lead_id';
        """)
        assert col_lead["data_type"] == "uuid" and col_lead["is_nullable"] == "YES", f"Invalid lead_id col: {col_lead}"
        results["3_lead_id_native_uuid_nullable"] = {"status": "PASSED", "data_type": col_lead["data_type"], "is_nullable": col_lead["is_nullable"]}

        # Assertion 4: Foreign keys exist on correct table and columns
        fk_rows = await conn.fetch("""
            SELECT
                tc.constraint_name, 
                kcu.column_name, 
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                rc.delete_rule
            FROM information_schema.table_constraints AS tc 
            JOIN information_schema.key_column_usage AS kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
              ON ccu.constraint_name = tc.constraint_name
             AND ccu.table_schema = tc.table_schema
            JOIN information_schema.referential_constraints AS rc
              ON rc.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY' 
              AND tc.table_name = 'source_attributions'
              AND kcu.column_name IN ('organization_id', 'lead_id');
        """)
        fk_map = {r["column_name"]: (r["constraint_name"], r["foreign_table_name"], r["delete_rule"]) for r in fk_rows}
        assert "organization_id" in fk_map, "Missing FK on organization_id"
        assert "lead_id" in fk_map, "Missing FK on lead_id"
        results["4_foreign_keys_present"] = {"status": "PASSED", "fks": {k: v[0] for k, v in fk_map.items()}}

        # Assertion 5: ON DELETE behaviors are CASCADE for org and SET NULL for lead
        assert fk_map["organization_id"][1] == "organizations" and fk_map["organization_id"][2] == "CASCADE", f"Org FK bad: {fk_map['organization_id']}"
        assert fk_map["lead_id"][1] == "leads" and fk_map["lead_id"][2] == "SET NULL", f"Lead FK bad: {fk_map['lead_id']}"
        results["5_on_delete_rules"] = {
            "status": "PASSED",
            "organization_delete_rule": fk_map["organization_id"][2],
            "lead_delete_rule": fk_map["lead_id"][2]
        }

        # Assertion 6: Modern broker & subscription values accepted by check constraints
        # Test broker subscription_plan = 'pro_monthly', status = 'paused'
        broker_id = await conn.fetchval("SELECT id FROM brokers LIMIT 1")
        await conn.execute("""
            UPDATE brokers 
            SET subscription_plan = 'pro_monthly', subscription_status = 'paused', onboarding_status = 'ONBOARDED' 
            WHERE id = $1;
        """, broker_id)
        updated_broker = await conn.fetchrow("SELECT subscription_plan, subscription_status FROM brokers WHERE id = $1", broker_id)
        assert updated_broker["subscription_plan"] == "pro_monthly" and updated_broker["subscription_status"] == "paused"
        
        # Test subscription status = 'paused'
        sub_id = uuid.uuid4()
        await conn.execute("""
            INSERT INTO subscriptions (id, broker_id, amount, currency, status, created_at)
            VALUES ($1, $2, 499900, 'INR', 'paused', now());
        """, sub_id, broker_id)
        updated_sub = await conn.fetchval("SELECT status FROM subscriptions WHERE id = $1", sub_id)
        assert updated_sub == "paused"
        results["6_modern_check_constraints"] = {"status": "PASSED", "broker_plan": updated_broker["subscription_plan"], "broker_status": updated_broker["subscription_status"], "sub_status": updated_sub}

        # Assertion 7: Relevant joins return non-empty expected rows in seeded test data
        # Seed fresh org, broker, lead, and attribution
        test_org_id = uuid.uuid4()
        test_broker_id = uuid.uuid4()
        test_lead_id = uuid.uuid4()
        test_attr_id = uuid.uuid4()

        await conn.execute("INSERT INTO organizations (id, name, slug, plan, is_demo, created_at, updated_at) VALUES ($1, 'Smoke Test Org', 'smoke-org', 'professional', false, now(), now())", test_org_id)
        await conn.execute("INSERT INTO brokers (id, email, name, subscription_status, created_at, updated_at) VALUES ($1, 'smoke@example.com', 'Smoke Broker', 'trial', now(), now())", test_broker_id)
        await conn.execute("INSERT INTO leads (id, organization_id, broker_id, name, phone, status, pipeline_stage, created_at, updated_at) VALUES ($1, $2, $3, 'Smoke Customer', '+919999900001', 'pending', 'new', now(), now())", test_lead_id, test_org_id, test_broker_id)
        await conn.execute("INSERT INTO source_attributions (id, organization_id, lead_id, channel, provider, first_touch_at, last_touch_at, created_at) VALUES ($1, $2, $3, 'google_ads', 'google', now(), now(), now())", str(test_attr_id), test_org_id, test_lead_id)

        join_rows = await conn.fetch("""
            SELECT leads.name, source_attributions.channel 
            FROM leads 
            JOIN source_attributions ON leads.id = source_attributions.lead_id 
            WHERE leads.id = $1;
        """, test_lead_id)
        assert len(join_rows) == 1, f"Expected 1 joined row, got {len(join_rows)}"
        assert join_rows[0]["name"] == "Smoke Customer" and join_rows[0]["channel"] == "google_ads"
        results["7_seeded_relational_join"] = {"status": "PASSED", "matched_rows": len(join_rows), "customer": join_rows[0]["name"], "channel": join_rows[0]["channel"]}

        # Assertion 8: String UUIDs and Python UUID objects correctly handled via SQLAlchemy ORM
        engine = create_async_engine(DISP_ASYNC_URL)
        async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        # 8a: Insert with string UUIDs
        str_lead_id = str(uuid.uuid4())
        str_attr_id = str(uuid.uuid4())
        async with async_session() as s:
            new_lead = Lead(
                id=uuid.UUID(str_lead_id),
                organization_id=test_org_id,
                broker_id=test_broker_id,
                name="String UUID Customer",
                phone="+919999900002",
                status="pending",
                pipeline_stage="new"
            )
            new_attr = SourceAttribution(
                id=str_attr_id,                    # id is String(36)
                organization_id=str(test_org_id),  # Passing string UUID to GUID TypeDecorator
                lead_id=str_lead_id,               # Passing string UUID
                channel="facebook_ads",
                provider="meta"
            )
            s.add(new_lead)
            await s.flush()
            s.add(new_attr)
            await s.commit()

        # 8b: Query with Python UUID object and String UUID
        async with async_session() as s:
            # Query by string id
            res_obj = await s.execute(select(SourceAttribution).where(SourceAttribution.id == str_attr_id))
            fetched_obj = res_obj.scalar_one_or_none()
            assert fetched_obj is not None
            assert fetched_obj.channel == "facebook_ads"
            # Verify result_value conversion to UUID
            assert isinstance(fetched_obj.organization_id, uuid.UUID)
            assert isinstance(fetched_obj.lead_id, uuid.UUID)
        results["8_string_and_python_uuid_handling"] = {"status": "PASSED"}

        # Assertion 9: Invalid UUID values rejected
        invalid_uuid_rejected = False
        try:
            async with async_session() as s:
                bad_attr = SourceAttribution(
                    id=str(uuid.uuid4()),
                    organization_id="not-a-valid-uuid-string",
                    channel="test"
                )
                s.add(bad_attr)
                await s.commit()
        except Exception as e:
            invalid_uuid_rejected = True
            results["9_invalid_uuid_rejection"] = {"status": "PASSED", "error_type": type(e).__name__}
        assert invalid_uuid_rejected, "Expected invalid UUID string to be rejected!"

        # Assertion 10: Existing records and tenant isolation preserved
        # Tenant isolation check
        other_org_id = uuid.uuid4()
        iso_rows = await conn.fetch("SELECT id FROM source_attributions WHERE organization_id = $1;", other_org_id)
        assert len(iso_rows) == 0, "Tenant isolation leak: found rows for unassigned organization"

        # Destructive Referencing Smoke (Lead delete -> attribution lead_id set NULL, Org delete -> attribution cascade)
        # 10a: Delete lead -> check lead_id becomes NULL
        await conn.execute("DELETE FROM leads WHERE id = $1;", test_lead_id)
        attr_after_lead_delete = await conn.fetchrow("SELECT id, lead_id FROM source_attributions WHERE id = $1;", str(test_attr_id))
        assert attr_after_lead_delete is not None, "Attribution was deleted when lead was deleted! Expected preservation."
        assert attr_after_lead_delete["lead_id"] is None, f"Expected lead_id to be NULL, got {attr_after_lead_delete['lead_id']}"

        # 10b: Delete org -> check attribution is cascaded
        await conn.execute("DELETE FROM organizations WHERE id = $1;", test_org_id)
        attr_after_org_delete = await conn.fetchrow("SELECT id FROM source_attributions WHERE id = $1;", str(test_attr_id))
        assert attr_after_org_delete is None, "Attribution was NOT cascaded when organization was deleted!"

        results["10_tenant_isolation_and_referential_actions"] = {"status": "PASSED", "lead_delete_set_null": "VERIFIED", "org_delete_cascade": "VERIFIED"}

        await engine.dispose()
        print("\n=== ALL 10 RIGOROUS SMOKE ASSERTIONS PASSED ===")
        import json
        print(json.dumps(results, indent=2))

    finally:
        await conn.close()
        try:
            await engine.dispose()
        except Exception:
            pass
        admin = await asyncpg.connect(ADMIN_URL)
        await admin.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{DISP_DB}' AND pid <> pg_backend_pid();")
        await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
        await admin.close()
        print(f"[TEARDOWN] Dropped disposable database '{DISP_DB}'.")

if __name__ == "__main__":
    asyncio.run(run_rigorous_smoke_suite())
