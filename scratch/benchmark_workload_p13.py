import asyncio
import time
import statistics
import uuid
import sys
import os
import json
from typing import Dict, List, Any

sys.path.insert(0, os.path.abspath("apps/api"))
sys.path.insert(0, os.path.abspath("."))

os.environ["ENV"] = "production"
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_test_acceptance"
os.environ["REDIS_URL"] = "redis://127.0.0.1:6379/0"
os.environ["SECRET_KEY"] = "benchmark_secret_key_testing_32chars_min"
os.environ["AUTO_CREATE_SCHEMA_ON_STARTUP"] = "false"
os.environ["PILOT_MODE"] = "RECOMMEND_ONLY"
os.environ["WHATSAPP_ENABLED"] = "false"
os.environ["FOLLOWUP_HUB_DISPATCH_ENABLED"] = "false"

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import AsyncAdaptedQueuePool
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database import get_db
from app.core.database_safety import validate_test_database_target, TestEntityTracker
from app.modules.auth.service import create_access_token
from app.models.organization import Organization, OrganizationMember
from app.models.broker import Broker
from app.models.lead import Lead

TEST_DB_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/leadscore_test_acceptance"

async def run_benchmark():
    print("=" * 70)
    print("WEFYLABS PHASE 13 PRODUCTION-GRADE WORKLOAD & LATENCY BENCHMARK")
    print("=" * 70)
    
    # 1. Validate safety
    validate_test_database_target(TEST_DB_URL, env="testing")
    
    # 2. Setup Production AsyncAdaptedQueuePool engine
    prod_engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        poolclass=AsyncAdaptedQueuePool,
        pool_size=10,
        max_overflow=10,
        pool_timeout=15.0,
        pool_pre_ping=True
    )
    session_factory = async_sessionmaker(
        bind=prod_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )

    async def override_get_db():
        async with session_factory() as sess:
            yield sess

    app.dependency_overrides[get_db] = override_get_db

    # 3. Seed test organization and lead
    tracker = TestEntityTracker(test_run_id=f"perf_p13_{uuid.uuid4().hex[:6]}")
    org_id = uuid.uuid4()
    broker_id = uuid.uuid4()
    lead_id = uuid.uuid4()

    async with session_factory() as session:
        org = Organization(
            id=org_id,
            name="P13 Benchmark Realty",
            slug=f"p13-{str(org_id)[:8]}",
            plan="enterprise",
            is_demo=False,
            country_code="IN",
            currency_code="INR"
        )
        broker = Broker(
            id=broker_id,
            name="P13 Performance Agent",
            email=f"agent_{str(broker_id)[:8]}@perf.test",
            phone="+919876540001",
            subscription_status="active"
        )
        session.add_all([org, broker])
        tracker.register("organizations", org_id)
        tracker.register("brokers", broker_id)

        member = OrganizationMember(organization_id=org_id, broker_id=broker_id, role="owner")
        session.add(member)
        tracker.register_membership(org_id, broker_id)

        lead = Lead(
            id=lead_id,
            organization_id=org_id,
            broker_id=broker_id,
            name="Rohan Verma",
            phone="+919876540002",
            status="pending",
            pipeline_stage="new",
            budget_min=15000000,
            budget_max=25000000,
            property_type="3bhk",
            notes=[]
        )
        session.add(lead)
        tracker.register("leads", lead_id)
        await session.commit()

    print("[FIXTURE] Seeding completed: Org, Broker, and Lead provisioned.")

    token = create_access_token(data={"sub": str(broker_id), "org_id": str(org_id), "role": "owner"})
    headers = {
        "Authorization": f"Bearer {token}",
        "X-WefyLabs-Organization-Id": str(org_id),
    }

    # 4. Workload Definitions
    workloads = [
        {"name": "health_live", "method": "GET", "url": "/health/live", "json": None, "auth": False},
        {"name": "health_ready", "method": "GET", "url": "/health/ready", "json": None, "auth": False},
        {"name": "lead_detail", "method": "GET", "url": f"/api/v1/leads/{lead_id}", "json": None, "auth": True},
        {"name": "lead_list", "method": "GET", "url": "/api/v1/leads?page=1&page_size=10", "json": None, "auth": True},
        {"name": "canonical_search", "method": "GET", "url": "/api/v1/search?q=luxury+3bhk+apartment", "json": None, "auth": True},
        {"name": "scoring_qualify", "method": "POST", "url": "/api/v1/scoring/qualify", "json": {"lead_id": str(lead_id), "budget_max": 25000000, "property_type": "apartment_3bhk"}, "auth": True},
        {"name": "revenue_funnel", "method": "GET", "url": "/api/v1/revenue-intelligence/funnel", "json": None, "auth": True},
        {"name": "calendar_slots", "method": "POST", "url": "/api/v1/calendar/slots/search", "json": {"lead_id": str(lead_id), "days_ahead": 7, "duration_minutes": 30}, "auth": True},
    ]

    transport = ASGITransport(app=app)
    results: Dict[str, List[float]] = {w["name"]: [] for w in workloads}
    status_counts: Dict[str, int] = {}
    
    TOTAL_ITERATIONS = 25  # 25 requests * 8 endpoints = 200 total requests
    CONCURRENCY = 4

    print(f"\n[EXECUTION] Starting benchmark: {TOTAL_ITERATIONS * len(workloads)} total requests across {len(workloads)} endpoints (Concurrency: {CONCURRENCY})...")
    
    t_bench_start = time.perf_counter()
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Warmup (1 pass)
        for w in workloads:
            h = headers if w["auth"] else {}
            if w["method"] == "GET":
                await client.get(w["url"], headers=h)
            else:
                await client.post(w["url"], json=w["json"], headers=h)
        print("[WARMUP] Cache & connection pool pre-warmed.")

        # Benchmark runner
        sem = asyncio.Semaphore(CONCURRENCY)

        async def execute_request(w):
            h = headers if w["auth"] else {}
            async with sem:
                t0 = time.perf_counter()
                if w["method"] == "GET":
                    resp = await client.get(w["url"], headers=h)
                else:
                    resp = await client.post(w["url"], json=w["json"], headers=h)
                t1 = time.perf_counter()
                latency_ms = (t1 - t0) * 1000
                results[w["name"]].append(latency_ms)
                status = f"{resp.status_code}"
                status_counts[status] = status_counts.get(status, 0) + 1

        tasks = []
        for _ in range(TOTAL_ITERATIONS):
            for w in workloads:
                tasks.append(execute_request(w))

        await asyncio.gather(*tasks)

    t_bench_end = time.perf_counter()
    total_duration = t_bench_end - t_bench_start
    total_reqs = sum(len(v) for v in results.values())
    throughput = total_reqs / total_duration

    print("\n" + "=" * 70)
    print("BENCHMARK METRICS & PERCENTILE BREAKDOWN")
    print("=" * 70)
    print(f"Total Requests Processed: {total_reqs}")
    print(f"Overall Duration:        {total_duration:.2f} s")
    print(f"Throughput:              {throughput:.1f} req/s")
    print(f"Status Code Summary:     {status_counts}")
    
    all_latencies = []
    print(f"\n{'Endpoint Name':<20} | {'Count':<5} | {'Min (ms)':<8} | {'Median (p50)':<12} | {'p90 (ms)':<8} | {'p95 (ms)':<8} | {'p99 (ms)':<8} | {'Max (ms)':<8}")
    print("-" * 95)
    for name, latencies in results.items():
        all_latencies.extend(latencies)
        l_sorted = sorted(latencies)
        count = len(l_sorted)
        p50 = statistics.median(l_sorted)
        p90 = l_sorted[int(count * 0.90)]
        p95 = l_sorted[int(count * 0.95)]
        p99 = l_sorted[int(count * 0.99)]
        print(f"{name:<20} | {count:<5} | {min(l_sorted):<8.2f} | {p50:<12.2f} | {p90:<8.2f} | {p95:<8.2f} | {p99:<8.2f} | {max(l_sorted):<8.2f}")

    all_sorted = sorted(all_latencies)
    print("-" * 95)
    overall_p50 = statistics.median(all_sorted)
    overall_p90 = all_sorted[int(len(all_sorted) * 0.90)]
    overall_p95 = all_sorted[int(len(all_sorted) * 0.95)]
    overall_p99 = all_sorted[int(len(all_sorted) * 0.99)]
    print(f"{'OVERALL AGGREGATE':<20} | {len(all_sorted):<5} | {min(all_sorted):<8.2f} | {overall_p50:<12.2f} | {overall_p90:<8.2f} | {overall_p95:<8.2f} | {overall_p99:<8.2f} | {max(all_sorted):<8.2f}")

    # Teardown
    async with session_factory() as sess:
        await tracker.safe_cleanup(sess)
    await prod_engine.dispose()
    print("\n[TEARDOWN] Synthetic entities purged safely.")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
