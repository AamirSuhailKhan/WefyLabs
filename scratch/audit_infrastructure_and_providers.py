import asyncio
import os
import json
from dotenv import load_dotenv

load_dotenv('apps/api/.env')
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text
import redis

async def audit_infra():
    # 1. DB Active Connections & Limits
    db_url = os.environ.get('DATABASE_URL')
    engine = create_async_engine(db_url, poolclass=NullPool)
    
    async with engine.connect() as conn:
        print("=== 1. POSTGRES CONNECTION & POOL STATUS ===")
        res = await conn.execute(text("""
            SELECT count(*), state 
            FROM pg_stat_activity 
            GROUP BY state
        """))
        print("pg_stat_activity by state:")
        total_conns = 0
        for r in res.fetchall():
            print(f"  State: {r[1]} -> Count: {r[0]}")
            total_conns += r[0]
        print(f"Total active DB connections across all clients: {total_conns}")

        max_conn_res = await conn.execute(text("SHOW max_connections;"))
        max_conn = max_conn_res.scalar()
        print(f"PostgreSQL max_connections: {max_conn}")

        # Check outbound message / webhook tables
        print("\n=== 2. OUTBOUND PROVIDER SAFETY AUDIT ===")
        outbound_tables = [
            "channel_messages",
            "communication_consents",
            "consent_records",
            "outbox_events",
            "payment_webhook_events",
            "deal_bookings"
        ]
        org_id = "a0317351-e076-493e-8b84-182f8c43666e"
        for ot in outbound_tables:
            try:
                async with conn.begin_nested():
                    res = await conn.execute(text(f"SELECT COUNT(*) FROM {ot}"))
                    cnt = res.scalar()
                    print(f"  Table '{ot}' total count: {cnt}")
            except Exception as e:
                print(f"  Table '{ot}': {e.orig if hasattr(e, 'orig') else e}")

    # 2. Redis & Celery Status
    print("\n=== 3. REDIS & WORKER HEALTH ===")
    redis_url = os.environ.get('REDIS_URL') or os.environ.get('UPSTASH_REDIS_URL') or os.environ.get('CELERY_BROKER_URL')
    print("Redis Broker URL:", redis_url[:30] if redis_url else "NOT CONFIGURED")
    if redis_url:
        try:
            r = redis.from_url(redis_url)
            ping_ok = r.ping()
            print(f"Redis Ping: {ping_ok}")
            
            # Inspect queues
            queues = ["sales-loop-orchestration", "lead_queue", "notification_queue", "celery"]
            for q in queues:
                try:
                    q_len = r.llen(q)
                    print(f"  Queue '{q}' length: {q_len}")
                except Exception as e:
                    print(f"  Queue '{q}': {e}")
        except Exception as e:
            print(f"Redis connection error: {e}")

    # 3. Celery Beat Schedule Inspection
    print("\n=== 4. CELERY BEAT SCHEDULE INSPECTION ===")
    import sys
    sys.path.insert(0, 'apps/api')
    try:
        from app.celery_app import celery_app
        beat_schedule = celery_app.conf.beat_schedule
        print(f"Registered Beat schedules ({len(beat_schedule)}):")
        for name, entry in beat_schedule.items():
            task = entry.get('task')
            sched = entry.get('schedule')
            if 'pilot' in name.lower() or 'snapshot' in name.lower() or 'autonomous' in name.lower():
                print(f"  * {name}: {task} -> {sched}")
            else:
                print(f"    {name}: {task} -> {sched}")
    except Exception as e:
        print(f"Beat schedule inspection error: {e}")

if __name__ == '__main__':
    asyncio.run(audit_infra())
