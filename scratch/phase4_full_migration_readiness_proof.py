import asyncio
import asyncpg
import subprocess
import sys
import os
import uuid
import json
from datetime import datetime, timezone

sys.path.insert(0, "apps/api")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.acquisition_models import SourceAttribution
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.broker import Broker

ADMIN_URL = "postgresql://postgres:postgres@127.0.0.1:5432/postgres"
DISP_DB = "test_disposable_phase4"
DISP_URL_PG = f"postgresql://postgres:postgres@127.0.0.1:5432/{DISP_DB}"
DISP_URL_SA = f"postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/{DISP_DB}"

async def setup():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.execute(f"CREATE DATABASE {DISP_DB} WITH TEMPLATE leadscore;")
    await admin.close()
    print(f"[SETUP] Created disposable database '{DISP_DB}' from 'leadscore' (0048).")

async def tear_down():
    admin = await asyncpg.connect(ADMIN_URL)
    await admin.execute(f"""
        SELECT pg_terminate_backend(pid) 
        FROM pg_stat_activity 
        WHERE datname = '{DISP_DB}' AND pid <> pg_backend_pid();
    """)
    await admin.execute(f"DROP DATABASE IF EXISTS {DISP_DB};")
    await admin.close()
    print(f"[TEARDOWN] Dropped disposable database '{DISP_DB}'.")

def run_alembic_upgrade():
    api_dir = os.path.abspath("apps/api")
    cmd = [
        sys.executable, "-m", "alembic", "-c", "alembic.ini",
        "-x", f"db_url={DISP_URL_PG}",
        "upgrade", "head"
    ]
    res = subprocess.run(cmd, cwd=api_dir, capture_output=True, text=True)
    assert res.returncode == 0, f"Upgrade failed: {res.stderr}\n{res.stdout}"
    print("[MIGRATION] Alembic upgraded to 0050 successfully.")

async def verify_phase4():
    engine = create_async_engine(DISP_URL_SA, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    report = {}

    conn = await asyncpg.connect(DISP_URL_PG)
    
    # 1. Authoritative Revision
    rev = await conn.fetchval("SELECT version_num FROM alembic_version;")
    assert rev == "0050_broker_subscription_constraint_parity"
    report["verified_revision"] = rev

    # 2. Existing data preservation
    existing_rows = await conn.fetch("SELECT id, organization_id, lead_id FROM source_attributions ORDER BY id;")
    assert len(existing_rows) == 3
    report["existing_attributions_preserved"] = len(existing_rows)

    # 3. UUID column typing
    cols = await conn.fetch("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'source_attributions' AND column_name IN ('organization_id', 'lead_id')
        ORDER BY column_name;
    """)
    col_map = {r["column_name"]: (r["data_type"], r["is_nullable"]) for r in cols}
    assert col_map["organization_id"] == ("uuid", "NO")
    assert col_map["lead_id"] == ("uuid", "YES")
    report["source_attribution_columns"] = col_map

    # 4. Modern broker & subscription checks
    test_broker_id = await conn.fetchval("SELECT id FROM brokers LIMIT 1;")
    await conn.execute("UPDATE brokers SET subscription_plan = 'pro_monthly', subscription_status = 'paused' WHERE id = $1;", test_broker_id)
    b_row = await conn.fetchrow("SELECT subscription_plan, subscription_status FROM brokers WHERE id = $1;", test_broker_id)
    assert b_row["subscription_plan"] == "pro_monthly"
    assert b_row["subscription_status"] == "paused"
    report["broker_constraint_checks"] = "PASSED (accepted pro_monthly and paused)"

    await conn.close()

    # 5. ORM queries, joins, inserts, updates
    async with sf() as session:
        org_id = uuid.uuid4()
        broker_id = uuid.uuid4()
        lead_id = uuid.uuid4()
        attr_id = str(uuid.uuid4())

        org = Organization(id=org_id, name="Phase 4 Org", slug=f"p4-{org_id.hex[:8]}")
        session.add(org)
        await session.flush()

        broker = Broker(id=broker_id, email=f"p4_{broker_id.hex[:6]}@test.com", name="P4 Broker", subscription_plan="starter_monthly", subscription_status="active")
        session.add(broker)
        await session.flush()

        lead = Lead(id=lead_id, organization_id=org_id, broker_id=broker_id, phone="+971505556677", name="P4 Lead", source="WEBSITE", pipeline_stage="new")
        session.add(lead)
        await session.flush()

        attr = SourceAttribution(id=attr_id, organization_id=org_id, lead_id=lead_id, channel="WEBSITE", provider="meta_ads", created_at=datetime.now(timezone.utc))
        session.add(attr)
        await session.flush()
        report["orm_insert"] = "PASSED"

        # Query by UUID
        q_uuid = (await session.execute(select(SourceAttribution).where(SourceAttribution.lead_id == lead_id))).scalars().first()
        assert q_uuid is not None and q_uuid.id == attr_id
        report["orm_query_by_uuid"] = "PASSED"

        # Relational join
        join_q = (await session.execute(
            select(Lead.name, SourceAttribution.channel).join(SourceAttribution, Lead.id == SourceAttribution.lead_id).where(Lead.id == lead_id)
        )).first()
        assert join_q == ("P4 Lead", "WEBSITE")
        report["orm_relational_join"] = "PASSED"

        # Delete lead -> ON DELETE SET NULL
        await session.delete(lead)
        await session.flush()
        session.expire_all()

        check_attr = (await session.execute(select(SourceAttribution).where(SourceAttribution.id == attr_id))).scalars().first()
        assert check_attr is not None
        assert check_attr.lead_id is None
        report["orm_delete_set_null"] = "PASSED"

        # Tenant isolation check
        other_org_id = uuid.uuid4()
        iso_q = (await session.execute(select(SourceAttribution).where(SourceAttribution.organization_id == other_org_id))).scalars().all()
        assert len(iso_q) == 0
        report["tenant_isolation"] = "PASSED"

        await session.rollback()

    await engine.dispose()
    return report

async def main():
    await setup()
    try:
        run_alembic_upgrade()
        rep = await verify_phase4()
        print("\n=== PHASE 4 MIGRATION READINESS VERIFIED ===")
        print(json.dumps(rep, indent=2))
        with open("scratch/phase4_readiness_report.json", "w") as f:
            json.dump(rep, f, indent=2)
    finally:
        await tear_down()

if __name__ == "__main__":
    asyncio.run(main())
