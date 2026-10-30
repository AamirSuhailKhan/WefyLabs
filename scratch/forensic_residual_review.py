import asyncio
import asyncpg
import json

async def inspect_residual():
    conn = await asyncpg.connect('postgresql://postgres:postgres@127.0.0.1:5432/leadscore')
    await conn.execute('SET default_transaction_read_only = on;')
    
    rows = await conn.fetch('''
        SELECT id, organization_id, lead_id, channel, provider, landing_page, created_at 
        FROM source_attributions 
        WHERE id IN ('0577d0bf-5c75-4126-9e88-3ba0580972bb', 'e715c212-8acc-48a8-92d7-495e94f17131')
        ORDER BY created_at;
    ''')
    for r in rows:
        d = dict(r)
        d['created_at'] = str(d['created_at'])
        lead_exists = await conn.fetchval('SELECT count(*) FROM leads WHERE id::text = $1', d['lead_id'])
        org_exists = await conn.fetchval('SELECT count(*) FROM organizations WHERE id::text = $1', d['organization_id'])
        d['lead_exists_in_leads_table'] = lead_exists
        d['org_exists_in_orgs_table'] = org_exists
        print(json.dumps(d, indent=2))
        
    await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect_residual())

