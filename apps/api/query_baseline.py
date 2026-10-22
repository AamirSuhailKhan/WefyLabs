import asyncio, sys
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv('.env')
from sqlalchemy import text
from app.database import async_session_maker

async def main():
    async with async_session_maker() as db:
        # Pilot tenants - actual columns
        r = await db.execute(text(
            'SELECT id, organization_id, current_stage, pilot_status, configured_autonomy_level, enrolled_at '
            'FROM pilot_tenants'
        ))
        rows = r.fetchall()
        print('=== PILOT TENANTS ===')
        for row in rows:
            print(f'  id={row[0]}, org={row[1]}, stage={row[2]}, pilot_status={row[3]}, autonomy={row[4]}, enrolled={row[5]}')

        # Human decisions count
        r2 = await db.execute(text('SELECT count(*) FROM pilot_human_decisions'))
        print(f'=== HUMAN DECISIONS: {r2.scalar()} ===')

        # Recent human decisions
        r2b = await db.execute(text(
            'SELECT id, observation_id, organization_id, lead_id, human_actor_id, decision_type, decided_at '
            'FROM pilot_human_decisions ORDER BY decided_at DESC LIMIT 5'
        ))
        rows2b = r2b.fetchall()
        print('=== RECENT HUMAN DECISIONS ===')
        for row in rows2b:
            print(f'  id={row[0]}, obs={row[1]}, org={row[2]}, lead={row[3]}, actor={row[4]}, type={row[5]}, at={row[6]}')
        if not rows2b:
            print('  (none)')

        # Genuine days - from metric snapshots where metric_name indicates genuine activity
        r3 = await db.execute(text(
            "SELECT metric_name, count(*) FROM pilot_metric_snapshots GROUP BY metric_name ORDER BY metric_name"
        ))
        print('=== METRIC SNAPSHOTS BY NAME ===')
        for row in r3.fetchall():
            print(f'  {row[0]}: {row[1]}')

        r3b = await db.execute(text('SELECT count(*) FROM pilot_metric_snapshots'))
        print(f'=== TOTAL METRIC SNAPSHOTS: {r3b.scalar()} ===')

        # pilot_observations by is_synthetic
        r4 = await db.execute(text(
            'SELECT is_synthetic, count(*) FROM pilot_observations GROUP BY is_synthetic'
        ))
        print('=== PILOT OBSERVATIONS ===')
        for row in r4.fetchall():
            print(f'  is_synthetic={row[0]}, count={row[1]}')

        # Recent pilot observations
        r4b = await db.execute(text(
            'SELECT id, lead_id, is_synthetic, policy_decision, pilot_stage, observed_at '
            'FROM pilot_observations ORDER BY observed_at DESC LIMIT 5'
        ))
        rows4b = r4b.fetchall()
        print('=== RECENT PILOT OBSERVATIONS ===')
        for row in rows4b:
            print(f'  id={row[0]}, lead={row[1]}, synthetic={row[2]}, policy={row[3]}, stage={row[4]}, at={row[5]}')
        if not rows4b:
            print('  (none)')

        # sales_loop_events by processing_state
        r5 = await db.execute(text(
            'SELECT processing_state, count(*) FROM sales_loop_events GROUP BY processing_state'
        ))
        print('=== SALES LOOP EVENTS BY STATE ===')
        for row in r5.fetchall():
            print(f'  {row[0]}: {row[1]}')

        # Recent sales loop events
        r5b = await db.execute(text(
            'SELECT id, lead_id, event_type, processing_state, source, created_at '
            'FROM sales_loop_events ORDER BY created_at DESC LIMIT 5'
        ))
        rows5b = r5b.fetchall()
        print('=== RECENT SALES LOOP EVENTS ===')
        for row in rows5b:
            print(f'  id={row[0]}, lead={row[1]}, type={row[2]}, state={row[3]}, src={row[4]}, at={row[5]}')
        if not rows5b:
            print('  (none)')

        # Leads count total and recent
        r6 = await db.execute(text('SELECT count(*) FROM leads WHERE deleted_at IS NULL'))
        print(f'=== TOTAL ACTIVE LEADS: {r6.scalar()} ===')

        r7 = await db.execute(text(
            "SELECT count(*) FROM leads WHERE created_at >= NOW() - INTERVAL '7 days' AND deleted_at IS NULL"
        ))
        print(f'=== LEADS LAST 7 DAYS: {r7.scalar()} ===')

        # Recent leads
        r8 = await db.execute(text(
            'SELECT id, name, email, source, status, organization_id, created_at '
            'FROM leads WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 5'
        ))
        rows8 = r8.fetchall()
        print('=== RECENT LEADS ===')
        for row in rows8:
            print(f'  id={row[0]}, name={row[1]}, email={row[2]}, source={row[3]}, status={row[4]}, org={row[5]}, at={row[6]}')
        if not rows8:
            print('  (none)')

        # Audit events
        r9 = await db.execute(text('SELECT count(*) FROM pilot_audit_events'))
        print(f'=== PILOT AUDIT EVENTS: {r9.scalar()} ===')

        # Organizations
        r10 = await db.execute(text(
            'SELECT id, name, slug, plan, created_at FROM organizations WHERE deleted_at IS NULL ORDER BY created_at DESC LIMIT 5'
        ))
        rows10 = r10.fetchall()
        print('=== ORGANIZATIONS ===')
        for row in rows10:
            print(f'  id={row[0]}, name={row[1]}, slug={row[2]}, plan={row[3]}, at={row[4]}')
        if not rows10:
            print('  (none)')

        # Integrations tables discovery
        r11 = await db.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE '%integrat%'"
        ))
        print('=== INTEGRATION TABLES ===')
        for row in r11.fetchall():
            print(f'  {row[0]}')

asyncio.run(main())
