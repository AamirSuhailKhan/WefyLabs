import asyncio
import time
from sqlalchemy import text
from app.database import AsyncSessionLocal, engine

async def single_worker_load(worker_id: int, iterations: int):
    latencies = []
    acquired = 0
    errors = 0
    for i in range(iterations):
        t0 = time.perf_counter()
        try:
            async with AsyncSessionLocal() as session:
                acquired += 1
                res = await session.execute(text("SELECT 1 AS ping"))
                val = res.scalar()
                t1 = time.perf_counter()
                latencies.append((t1 - t0) * 1000.0)
        except Exception as e:
            errors += 1
            latencies.append(-1.0)
        await asyncio.sleep(0.02)
    return {
        "worker_id": worker_id,
        "acquired": acquired,
        "errors": errors,
        "avg_ms": sum(l for l in latencies if l > 0) / max(1, len([l for l in latencies if l > 0])),
        "max_ms": max(latencies) if latencies else 0,
        "min_ms": min(l for l in latencies if l > 0) if any(l > 0 for l in latencies) else 0
    }

async def run_capacity_test():
    print("--- RUNNING PHASE 2C.5 SYNTHETIC CAPACITY STRESS TEST ---")
    
    # 1. Baseline single query latency
    t0 = time.perf_counter()
    async with AsyncSessionLocal() as s:
        await s.execute(text("SELECT 1"))
    t1 = time.perf_counter()
    baseline_ping = (t1 - t0) * 1000.0
    print(f"Direct PG Ping Latency: {baseline_ping:.2f} ms")

    # 2. Concurrency load test: 10 concurrent tasks x 5 queries = 50 total queries
    concurrency_levels = [1, 3, 5, 8]
    results = {}
    for c in concurrency_levels:
        t_start = time.perf_counter()
        tasks = [single_worker_load(w, 5) for w in range(c)]
        worker_res = await asyncio.gather(*tasks)
        t_end = time.perf_counter()
        
        all_avg = sum(w["avg_ms"] for w in worker_res) / len(worker_res)
        all_max = max(w["max_ms"] for w in worker_res)
        total_errors = sum(w["errors"] for w in worker_res)
        
        results[f"concurrency_{c}"] = {
            "concurrency": c,
            "total_queries": c * 5,
            "duration_sec": t_end - t_start,
            "avg_latency_ms": all_avg,
            "max_latency_ms": all_max,
            "errors": total_errors
        }
        print(f"Concurrency {c:2d}: {c*5:2d} queries | Duration: {t_end-t_start:.2f}s | Avg Latency: {all_avg:.2f} ms | Max: {all_max:.2f} ms | Errors: {total_errors}")

    # 3. Connection state after test
    async with AsyncSessionLocal() as s:
        res = await s.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"))
        active_backends = res.scalar()
    print(f"Active PostgreSQL server backends after test: {active_backends}")

    await engine.dispose()
    return results

if __name__ == "__main__":
    asyncio.run(run_capacity_test())
