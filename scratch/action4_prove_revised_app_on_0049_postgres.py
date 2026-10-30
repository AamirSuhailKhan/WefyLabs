import asyncio
import uuid
import sys
from datetime import datetime, timezone

sys.path.insert(0, "apps/api")

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import select
from app.models.acquisition_models import SourceAttribution
from app.models.lead import Lead
from app.models.organization import Organization
from app.models.broker import Broker

PILOT_URL = "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/leadscore_pilot"

async def prove_0049_postgresql():
    engine = create_async_engine(PILOT_URL, echo=False)
    sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    org_id = uuid.uuid4()
    broker_id = uuid.uuid4()
    lead_id = uuid.uuid4()
    attr_id_1 = str(uuid.uuid4())
    attr_id_2 = str(uuid.uuid4())
    
    report = {}

    async with sf() as session:
        # Step 1: Create test organization, broker, and lead
        org = Organization(id=org_id, name="Action 4 Org", slug=f"act4-org-{org_id.hex[:8]}")
        broker = Broker(id=broker_id, email=f"act4_broker_{broker_id.hex[:6]}@test.com", name="Action 4 Broker")
        lead = Lead(
            id=lead_id,
            organization_id=org_id,
            broker_id=broker_id,
            phone="+971501112233",
            name="Action 4 Test Lead",
            source="WEBSITE",
            pipeline_stage="new"
        )
        session.add_all([org, broker, lead])
        await session.flush()
        report["step1_prerequisites"] = "SUCCESS"

        # Step 2: Insert SourceAttribution with native uuid.UUID objects
        attr_uuid = SourceAttribution(
            id=attr_id_1,
            organization_id=org_id,
            lead_id=lead_id,
            channel="WEBSITE",
            provider="meta_ads",
            utm_source="facebook",
            created_at=datetime.now(timezone.utc)
        )
        session.add(attr_uuid)
        await session.flush()
        report["step2_insert_uuid_object"] = "SUCCESS"

        # Step 3: Insert SourceAttribution with valid UUID strings (testing type coercion)
        attr_str = SourceAttribution(
            id=attr_id_2,
            organization_id=str(org_id),
            lead_id=str(lead_id),
            channel="GOOGLE",
            provider="google_ads",
            utm_source="google_search",
            created_at=datetime.now(timezone.utc)
        )
        session.add(attr_str)
        await session.flush()
        report["step3_insert_str_coerced_to_uuid"] = "SUCCESS"

        # Step 4: Query by native UUID object
        q1 = await session.execute(
            select(SourceAttribution).where(SourceAttribution.lead_id == lead_id)
        )
        records_q1 = q1.scalars().all()
        assert len(records_q1) == 2, f"Expected 2 attributions, got {len(records_q1)}"
        report["step4_query_by_uuid_object"] = f"SUCCESS (found {len(records_q1)})"

        # Step 5: Query by valid UUID string
        q2 = await session.execute(
            select(SourceAttribution).where(SourceAttribution.lead_id == str(lead_id))
        )
        records_q2 = q2.scalars().all()
        assert len(records_q2) == 2
        report["step5_query_by_uuid_str"] = f"SUCCESS (found {len(records_q2)})"

        # Step 6: Query with invalid UUID string (verifying strict rejection under Action 5)
        rejected = False
        try:
            stmt_invalid = select(SourceAttribution).where(SourceAttribution.lead_id == "invalid-not-a-uuid")
            await session.execute(stmt_invalid)
        except Exception as val_err:
            # SQLAlchemy wraps the type decorator's ValueError inside StatementError
            orig = getattr(val_err, "orig", val_err)
            if isinstance(orig, ValueError) or isinstance(val_err, ValueError):
                rejected = True
                report["step6_reject_invalid_uuid_string"] = f"SUCCESS: Strictly rejected with ValueError ('{orig}')"
            else:
                raise
        assert rejected, "Query with invalid UUID string must raise ValueError!"

        # Step 7: Relational JOIN Lead and SourceAttribution
        join_q = await session.execute(
            select(Lead.id, SourceAttribution.channel).join(
                SourceAttribution, Lead.id == SourceAttribution.lead_id
            ).where(Lead.id == lead_id).order_by(SourceAttribution.channel)
        )
        rows = join_q.all()
        assert len(rows) == 2
        assert [r[1] for r in rows] == ["GOOGLE", "WEBSITE"]
        report["step7_relational_join"] = f"SUCCESS (joined {len(rows)} rows: {rows})"

        # Step 8: Delete Lead and verify ON DELETE SET NULL cascade in PostgreSQL
        await session.delete(lead)
        await session.flush()
        session.expire_all()

        check_attr1 = (await session.execute(
            select(SourceAttribution).where(SourceAttribution.id == attr_id_1)
        )).scalar_one_or_none()
        check_attr2 = (await session.execute(
            select(SourceAttribution).where(SourceAttribution.id == attr_id_2)
        )).scalar_one_or_none()

        assert check_attr1 is not None and check_attr1.lead_id is None, "attr1 lead_id was not SET NULL!"
        assert check_attr2 is not None and check_attr2.lead_id is None, "attr2 lead_id was not SET NULL!"
        report["step8_on_delete_set_null"] = "SUCCESS: Both attributions preserved with lead_id set to NULL"

        # Step 9: Clean up test records (rollback transaction)
        await session.rollback()
        report["step9_clean_rollback"] = "SUCCESS: Pilot database preserved with zero mutations"

    await engine.dispose()
    return report

async def main():
    print("Executing Action 4: Real PostgreSQL + asyncpg validation on revision 0049...")
    rep = await prove_0049_postgresql()
    print("\n=== ACTION 4 PROOF RESULTS ON POSTGRESQL 0049 ===")
    for k, v in rep.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    asyncio.run(main())
