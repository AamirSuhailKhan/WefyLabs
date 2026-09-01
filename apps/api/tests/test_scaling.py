import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.auth.service import create_access_token

@pytest.mark.asyncio
async def test_sub_second_scaling_benchmarks(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Get Scaling System Metrics
        res_metrics = await ac.get("/api/v1/scale/metrics")
        assert res_metrics.status_code == 200
        data_m = res_metrics.json()
        assert "1,000,000 Brokers" in data_m["target_capacity"]
        assert "cache_stats" in data_m
        assert "db_connection_pool" in data_m

        # 2. Execute Load Benchmark Simulation
        load_payload = {"simulated_concurrent_requests": 1000}
        res_load = await ac.post("/api/v1/scale/load-test", json=load_payload, headers=headers)
        assert res_load.status_code == 200
        data_l = res_load.json()
        assert data_l["total_requests"] == 1000
        assert data_l["sub_second_pass"] is True
        assert data_l["p99_latency_ms"] < 1000.0

    app.dependency_overrides.clear()
