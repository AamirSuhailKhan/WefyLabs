import asyncio
import asyncpg

DB_URL = "postgresql://postgres.iymirycycichjbllucsr:BeetleLabs%402026@aws-0-ap-south-1.pooler.supabase.com:5432/postgres"

async def run():
    conn = await asyncpg.connect(DB_URL)
    cols = await conn.fetch("SELECT column_name FROM information_schema.columns WHERE table_name='pilot_audit_events' ORDER BY ordinal_position")
    col_names = [r['column_name'] for r in cols]
    print("Columns in pilot_audit_events:", col_names)
    rows = await conn.fetch("SELECT * FROM pilot_audit_events ORDER BY sequence_number")
    print(f"Total rows: {len(rows)}")
    broken_links = 0
    prev_hash = None
    for r in rows:
        d = dict(r)
        seq = d.get('sequence_number')
        cur_h = d.get('current_hash')
        prev_h = d.get('previous_hash')
        ev_type = d.get('event_type')
        if seq > 1 and prev_h != prev_hash:
            print(f"BROKEN LINK at seq {seq}: prev_hash={prev_h} != expected {prev_hash}")
            broken_links += 1
        else:
            print(f"Seq {seq}: {ev_type} | prev_h={str(prev_h)[:12]} | cur_h={str(cur_h)[:12]} [VERIFIED]")
        prev_hash = cur_h
    print(f"BROKEN AUDIT LINKS: {broken_links}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(run())
