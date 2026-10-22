import asyncio, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'apps', 'api'))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'apps', 'api', '.env'))
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

async def check():
    url = os.environ['DATABASE_URL'].replace('postgresql://', 'postgresql+asyncpg://')
    engine = create_async_engine(url)
    async with engine.connect() as conn:
        for tbl in ['pilot_metric_snapshots', 'pilot_evidence_records', 'pilot_cohort_guards', 'pilot_stage_transitions']:
            res = await conn.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = :t ORDER BY ordinal_position"), {"t": tbl})
            cols = res.fetchall()
            print(f"=== {tbl} ===")
            for c in cols:
                print(f"  {c[0]} ({c[1]})")
            cnt = await conn.execute(text(f"SELECT COUNT(*) FROM {tbl}"))
            print(f"  COUNT: {cnt.scalar()}\n")

if __name__ == '__main__':
    asyncio.run(check())
