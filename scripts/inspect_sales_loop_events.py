import asyncio, asyncpg, json

DB = "postgresql://postgres.iymirycycichjbllucsr:BeetleLabs%402026@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"
ORG_ID = "a0317351-e076-493e-8b84-182f8c43666e"

async def main():
    conn = await asyncpg.connect(DB)
    events = await conn.fetch("""
        SELECT id, idempotency_key, event_type, tenant_id, lead_id, broker_id,
               actor_type, actor_id, payload, processing_state, source, occurred_at, created_at
        FROM sales_loop_events
        WHERE tenant_id = $1
        ORDER BY created_at ASC
    """, ORG_ID)
    
    print(f"Total sales_loop_events for org {ORG_ID}: {len(events)}")
    for ev in events:
        print("-" * 60)
        print(f"ID:          {ev['id']}")
        print(f"Event Type:  {ev['event_type']}")
        print(f"Lead ID:     {ev['lead_id']}")
        print(f"Source:      {ev['source']}")
        print(f"Idemp Key:   {ev['idempotency_key']}")
        print(f"Actor:       {ev['actor_type']} ({ev['actor_id']})")
        print(f"State:       {ev['processing_state']}")
        print(f"Payload:     {ev['payload']}")
        print(f"Occurred:    {ev['occurred_at']}")
        print(f"Created:     {ev['created_at']}")
    
    await conn.close()

asyncio.run(main())
