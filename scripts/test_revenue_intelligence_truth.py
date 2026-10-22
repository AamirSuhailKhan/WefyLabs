import asyncio
import os
import sys
import json
from pathlib import Path

api_dir = Path("apps/api").resolve()
sys.path.insert(0, str(api_dir))

from dotenv import load_dotenv
load_dotenv('apps/api/.env')

import jwt
import httpx
from app.config import settings
from app.main import app

async def run():
    broker_id = "c193be18-4a6a-4030-9089-f94c42119189"
    org_id = "a0317351-e076-493e-8b84-182f8c43666e"

    payload = {
        "sub": broker_id,
        "email": "aamir.fresh@bmu.edu.in",
        "iat": 1728000000,
        "exp": 1828000000
    }
    token = jwt.encode(payload, settings.SUPABASE_JWT_SECRET, algorithm="HS256")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    endpoints = [
        "/api/v1/revenue-intelligence/overview",
        "/api/v1/revenue-intelligence/funnel",
        "/api/v1/revenue-intelligence/leakage",
        "/api/v1/revenue-intelligence/leakage/items",
        "/api/v1/revenue-intelligence/attribution",
        "/api/v1/revenue-intelligence/outcomes",
        "/api/v1/revenue-intelligence/actions",
        "/api/v1/revenue-intelligence/data-quality",
        "/api/v1/revenue-intelligence/team",
        "/api/v1/revenue/action-queue?limit=10",
        "/api/v1/revenue/briefing",
        "/api/v1/revenue/demand-intelligence",
    ]

    results = {}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as client:
        for ep in endpoints:
            resp = await client.get(ep, headers=headers)
            print(f"=== {ep} -> {resp.status_code} ===")
            try:
                data = resp.json()
                results[ep] = {"status": resp.status_code, "data": data}
                print(json.dumps(data, indent=2)[:500])
            except Exception as e:
                results[ep] = {"status": resp.status_code, "text": resp.text[:500]}
                print(resp.text[:500])

    with open("scripts/revenue_intelligence_live_results.json", "w") as f:
        json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run())
