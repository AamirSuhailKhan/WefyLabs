import asyncio
import asyncpg
import uuid

async def test_coercion():
    conn_pilot = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/leadscore_pilot')
    row_pilot = await conn_pilot.fetchrow('SELECT id, organization_id, lead_id FROM source_attributions LIMIT 1;')
    test_uuid = row_pilot['lead_id']
    test_str = str(test_uuid)
    
    # 1. UUID obj on UUID col
    try:
        r = await conn_pilot.fetch('SELECT * FROM source_attributions WHERE lead_id = $1;', test_uuid)
        print('1. UUID obj on UUID col: SUCCESS, rows:', len(r))
    except Exception as e:
        print('1. UUID obj on UUID col: FAILED:', e)

    # 2. String on UUID col
    try:
        r = await conn_pilot.fetch('SELECT * FROM source_attributions WHERE lead_id = $1;', test_str)
        print('2. String on UUID col: SUCCESS, rows:', len(r))
    except Exception as e:
        print('2. String on UUID col: FAILED:', e)

    await conn_pilot.close()

    # 3. String on VARCHAR col (in leadscore)
    conn_live = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/leadscore')
    row_live = await conn_live.fetchrow('SELECT id, organization_id, lead_id FROM source_attributions LIMIT 1;')
    live_lead_str = row_live['lead_id']
    live_lead_uuid = uuid.UUID(live_lead_str)

    try:
        r = await conn_live.fetch('SELECT * FROM source_attributions WHERE lead_id = $1;', live_lead_str)
        print('3. String on VARCHAR col: SUCCESS, rows:', len(r))
    except Exception as e:
        print('3. String on VARCHAR col: FAILED:', e)

    # 4. UUID obj on VARCHAR col (in leadscore)
    try:
        r = await conn_live.fetch('SELECT * FROM source_attributions WHERE lead_id = $1;', live_lead_uuid)
        print('4. UUID obj on VARCHAR col: SUCCESS, rows:', len(r))
    except Exception as e:
        print('4. UUID obj on VARCHAR col: FAILED:', e)

    await conn_live.close()

if __name__ == '__main__':
    asyncio.run(test_coercion())
