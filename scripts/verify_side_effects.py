import asyncio, asyncpg, json

async def main():
    conn = await asyncpg.connect('postgresql://postgres.iymirycycichjbllucsr:BeetleLabs%402026@aws-0-ap-south-1.pooler.supabase.com:5432/postgres')
    
    # 1. Pilot Tenant autonomy
    pilot = await conn.fetchrow("SELECT * FROM pilot_tenants WHERE organization_id = 'a0317351-e076-493e-8b84-182f8c43666e'")
    print("Pilot Autonomy:", pilot["configured_autonomy_level"])
    print("Current Stage: ", pilot["current_stage"])
    
    # 2. Check provider telemetry / dispatches
    # Check if there are any external actions recorded
    obs = await conn.fetch("SELECT * FROM pilot_observations WHERE pilot_id = $1", str(pilot["id"]))
    print(f"Observations count: {len(obs)}")
    for o in obs:
        print(f"  Obs {o['id']}: action={o['recommended_action']}, mode={o['execution_mode']}, policy={o['policy_decision']}")
    
    # 3. Check whatsapp, email, webhook communications for pilot leads
    leads = ['1d3d636e-1460-4507-bc3c-2ac0f19f7250', '2434cac9-3b94-49fb-a377-789f4ad785f6', '47d1dc97-2458-4dec-980f-a0d3afa24601']
    for table in ['whatsapp_messages', 'email_logs', 'booking_transactions']:
        try:
            cnt = await conn.fetchval(f"SELECT count(*) FROM {table} WHERE lead_id = ANY($1::uuid[])", leads)
            print(f"  {table} for pilot leads: {cnt}")
        except Exception as e:
            print(f"  {table} check: {e}")
            
    # 4. Audit events
    audits = await conn.fetch("SELECT * FROM pilot_audit_events WHERE pilot_id = $1 ORDER BY sequence_number ASC", str(pilot["id"]))
    print(f"Audit events: {len(audits)}")
    for a in audits:
        print(f"  Seq {a['sequence_number']}: {a['event_type']} | hash={a['current_hash'][:16]} | prev={a['previous_hash'][:16] if a['previous_hash'] else 'None'}")
        
    await conn.close()

asyncio.run(main())
