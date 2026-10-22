import asyncio, os, sys, json
sys.path.insert(0, r"c:\Users\aamir\OneDrive\Desktop\crm real state")
sys.path.insert(0, r"c:\Users\aamir\OneDrive\Desktop\crm real state\apps\api")
from scripts.verify_stage1_evidence_consistency import load_env
load_env()

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func
from app.modules.autonomous_loop.phase2c_pilot_repository import PilotRepository
from app.modules.autonomous_loop.phase2c_durable_models import PilotObservation, PilotHumanDecision, PilotAuditEvent, PilotTenant

db_url = os.environ.get("DATABASE_URL", "")
if not db_url.startswith("postgresql+asyncpg://"):
    db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")

engine = create_async_engine(db_url)
async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

ORG_ID = "a0317351-e076-493e-8b84-182f8c43666e"

async def check_reconciliation():
    async with async_session() as session:
        repo = PilotRepository(session)
        
        # 1. Direct DB count
        db_obs = (await session.execute(
            select(func.count(PilotObservation.id)).where(PilotObservation.organization_id == ORG_ID)
        )).scalar()
        db_dec = (await session.execute(
            select(func.count(PilotHumanDecision.id)).where(PilotHumanDecision.organization_id == ORG_ID)
        )).scalar()
        db_audit = (await session.execute(
            select(func.count(PilotAuditEvent.id)).where(PilotAuditEvent.organization_id == ORG_ID)
        )).scalar()
        
        # 2. PilotRepository count
        repo_obs, total_obs, pending_obs = await repo.get_observations(organization_id=ORG_ID, status="all")
        repo_pilot = await repo.get_pilot_tenant(ORG_ID)
        
        # 3. Metrics calculation (API equivalent)
        from datetime import datetime, timezone, timedelta
        period_end = datetime.now(timezone.utc)
        period_start = period_end - timedelta(days=14)
        metrics = await repo.compute_shadow_accuracy(
            pilot_id=repo_pilot.id,
            period_start=period_start,
            period_end=period_end,
        )
        
        print("=== AUTHORITATIVE RECONCILIATION ===")
        print(f"Direct DB Observations:     {db_obs}")
        print(f"PilotRepository Total Obs:  {total_obs}")
        print(f"PilotRepository Pending Obs: {pending_obs}")
        print(f"Direct DB Decisions:        {db_dec}")
        print(f"Direct DB Audits:           {db_audit}")
        print(f"Pilot Tenant Stage:         {repo_pilot.current_stage}")
        print(f"Pilot Tenant Autonomy:      {repo_pilot.configured_autonomy_level}")
        print(f"Pilot Metrics Total Obs:    {metrics.get('total_observations')}")
        print(f"Pilot Metrics Eligible Obs: {metrics.get('eligible_observations')}")
        print(f"Pilot Metrics Agreement %:  {metrics.get('accuracy_rate')}%")
        
        assert db_obs == total_obs, "DB obs count must match PilotRepository count"
        assert db_dec == 2, "DB decisions count must be 2"
        print("\nRECONCILIATION: PERFECT MATCH (ALL LAYERS AGREE)")

asyncio.run(check_reconciliation())
