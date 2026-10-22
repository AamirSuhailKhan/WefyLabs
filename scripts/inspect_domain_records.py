import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv('apps/api/.env')
import asyncpg

def json_serial(obj):
    import datetime, uuid
    if isinstance(obj, (datetime.datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    return str(obj)

async def inspect():
    dsn = os.getenv('DATABASE_URL').replace('postgresql+asyncpg://', 'postgresql://')
    conn = await asyncpg.connect(dsn)

    # 1. Pilot Tenant
    pilot_tenants = await conn.fetch("SELECT * FROM pilot_tenants")
    print("PILOT_TENANTS:")
    for r in pilot_tenants:
        print(json.dumps({k: json_serial(v) for k, v in dict(r).items()}, indent=2))

    # 2. Pilot Human Decisions & Observations
    broker = await conn.fetchrow("SELECT * FROM brokers WHERE id = 'c193be18-4a6a-4030-9089-f94c42119189'")
    print("PILOT_BROKER:", json.dumps({k: json_serial(v) for k, v in dict(broker).items()}, indent=2) if broker else "None")

    members = await conn.fetch("SELECT * FROM organization_members WHERE organization_id = 'a0317351-e076-493e-8b84-182f8c43666e'")
    print(f"PILOT_ORG_MEMBERS ({len(members)}):")
    for m in members:
        print(json.dumps({k: json_serial(v) for k, v in dict(m).items()}, indent=2))

    observations = await conn.fetch("SELECT * FROM pilot_observations")

    print("PILOT_OBSERVATIONS:")
    for r in observations:
        print(json.dumps({k: json_serial(v) for k, v in dict(r).items()}, indent=2))

    decisions = await conn.fetch("SELECT * FROM pilot_human_decisions")
    print("PILOT_HUMAN_DECISIONS:")
    for r in decisions:
        print(json.dumps({k: json_serial(v) for k, v in dict(r).items()}, indent=2))

    # 3. Leads
    leads = await conn.fetch("SELECT id, name, phone, email, organization_id, broker_id, score, status, pipeline_stage, created_at FROM leads ORDER BY created_at DESC")
    print(f"LEADS ({len(leads)}):")
    for r in leads:
        print(json.dumps({k: json_serial(v) for k, v in dict(r).items()}, indent=2))

    # 4. Property Listings
    props = await conn.fetch("SELECT * FROM property_listings")
    print(f"PROPERTY_LISTINGS ({len(props)}):")
    for r in props:
        print(json.dumps({k: json_serial(v) for k, v in dict(r).items()}, indent=2))


    # 5. Site Visits
    visits = await conn.fetch("SELECT * FROM site_visits")
    print(f"SITE_VISITS ({len(visits)}):")
    for r in visits:
        print(json.dumps({k: json_serial(v) for k, v in dict(r).items()}, indent=2))

    # 6. Revenue Opportunities
    opps = await conn.fetch("SELECT * FROM revenue_opportunities")
    print(f"REVENUE_OPPORTUNITIES ({len(opps)}):")
    for r in opps:
        print(json.dumps({k: json_serial(v) for k, v in dict(r).items()}, indent=2))

    # 7. Deals, Deal Bookings, Deal Commissions
    deals = await conn.fetch("SELECT * FROM deals")
    print(f"DEALS ({len(deals)}):")
    for r in deals:
        print(json.dumps({k: json_serial(v) for k, v in dict(r).items()}, indent=2))

    bookings = await conn.fetch("SELECT * FROM deal_bookings")
    print(f"DEAL_BOOKINGS ({len(bookings)}):")
    for r in bookings:
        print(json.dumps({k: json_serial(v) for k, v in dict(r).items()}, indent=2))

    commissions = await conn.fetch("SELECT * FROM deal_commissions")
    print(f"DEAL_COMMISSIONS ({len(commissions)}):")
    for r in commissions:
        print(json.dumps({k: json_serial(v) for k, v in dict(r).items()}, indent=2))

    await conn.close()

if __name__ == '__main__':
    asyncio.run(inspect())
