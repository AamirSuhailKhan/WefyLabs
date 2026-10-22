import sys, asyncio, json
sys.path.insert(0, 'apps/api')
from dotenv import load_dotenv; load_dotenv('apps/api/.env')
from sqlalchemy import text
from app.database import async_session_maker

CANONICAL_ORG = "a0317351-e076-493e-8b84-182f8c43666e"
ENROLLMENT_TIME = "2026-10-02 12:02:16.753959+00:00"

async def main():
    async with async_session_maker() as db:
        # Tables to inspect
        tables = [
            ("pilot_tenants", "organization_id", None),
            ("sales_loop_events", "tenant_id", None),
            ("pilot_observations", "organization_id", "is_synthetic"),
            ("pilot_human_decisions", "organization_id", None),
            ("pilot_audit_events", "organization_id", None),
            ("pilot_metric_snapshots", "organization_id", "is_synthetic"),
            ("leads", "organization_id", None),
            ("deals", "organization_id", None),
            ("site_visits", "organization_id", None),
            ("revenue_opportunities", "organization_id", None),
            ("deal_bookings", "organization_id", None),
            ("deal_commissions", "organization_id", None),
        ]
        
        results = {}
        for tbl, org_col, syn_col in tables:
            try:
                # 1. Total records globally
                q_total_glob = f"SELECT count(*) FROM {tbl}"
                tot_glob = (await db.execute(text(q_total_glob))).scalar()
                
                # 2. Total records for canonical org
                q_total_org = f"SELECT count(*) FROM {tbl} WHERE {org_col} = :org"
                tot_org = (await db.execute(text(q_total_org), {"org": CANONICAL_ORG})).scalar()

                # 3. Created in last 24h
                q_24h = f"SELECT count(*) FROM {tbl} WHERE {org_col} = :org AND created_at >= NOW() - INTERVAL '24 hours'"
                try:
                    c_24h = (await db.execute(text(q_24h), {"org": CANONICAL_ORG})).scalar()
                except Exception:
                    # Some tables might have different timestamp column
                    c_24h = "N/A"

                # 4. Created in last 48h
                q_48h = f"SELECT count(*) FROM {tbl} WHERE {org_col} = :org AND created_at >= NOW() - INTERVAL '48 hours'"
                try:
                    c_48h = (await db.execute(text(q_48h), {"org": CANONICAL_ORG})).scalar()
                except Exception:
                    c_48h = "N/A"

                # 5. Created after pilot enrollment
                q_post_enroll = f"SELECT count(*) FROM {tbl} WHERE {org_col} = :org AND created_at >= :enrolled_at"
                try:
                    c_post = (await db.execute(text(q_post_enroll), {"org": CANONICAL_ORG, "enrolled_at": ENROLLMENT_TIME})).scalar()
                except Exception:
                    c_post = "N/A"

                # 6. Synthetic vs non-synthetic
                if syn_col:
                    q_syn = f"SELECT count(*) FROM {tbl} WHERE {org_col} = :org AND {syn_col} = true"
                    q_nonsyn = f"SELECT count(*) FROM {tbl} WHERE {org_col} = :org AND ({syn_col} = false OR {syn_col} IS NULL)"
                    c_syn = (await db.execute(text(q_syn), {"org": CANONICAL_ORG})).scalar()
                    c_nonsyn = (await db.execute(text(q_nonsyn), {"org": CANONICAL_ORG})).scalar()
                else:
                    c_syn = 0
                    c_nonsyn = tot_org

                results[tbl] = {
                    "total_global": tot_glob,
                    "total_canonical_org": tot_org,
                    "created_last_24h": c_24h,
                    "created_last_48h": c_48h,
                    "created_after_enrollment": c_post,
                    "synthetic_count": c_syn,
                    "non_synthetic_count": c_nonsyn,
                    "tenant_mismatch": tot_glob - tot_org if tot_glob >= tot_org else 0
                }
            except Exception as e:
                results[tbl] = {"error": str(e)}

        print(json.dumps(results, indent=2))

asyncio.run(main())
