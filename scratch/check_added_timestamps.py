import asyncio
import asyncpg

async def check_added():
    conn = await asyncpg.connect("postgresql://postgres:postgres@127.0.0.1:5432/leadscore")
    for tbl in [
        "agent_workload_snapshots",
        "forecast_snapshot_records",
        "pipeline_health_snapshots",
        "prediction_drift_records",
        "prediction_inference_records",
        "sales_loop_audit_entries",
        "sales_loop_events",
        "source_attributions"
    ]:
        cols = [r['column_name'] for r in await conn.fetch("""
            SELECT column_name FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = $1
        """, tbl)]
        time_col = next((c for c in cols if 'time' in c or 'created' in c or 'snapshot_at' in c or 'timestamp' in c), None)
        if time_col:
            q = f'SELECT min("{time_col}") as earliest, max("{time_col}") as latest, count(*) as cnt FROM "{tbl}"'
            res = await conn.fetchrow(q)
            print(f"{tbl:30} {time_col:20} earliest: {res['earliest']} latest: {res['latest']} cnt: {res['cnt']}")
        else:
            cnt = await conn.fetchval(f'SELECT count(*) FROM "{tbl}"')
            print(f"{tbl:30} (no time col) cnt: {cnt}")
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_added())

