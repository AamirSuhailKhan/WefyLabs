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
        "X-WefyLabs-Organization-Id": org_id,
        "Content-Type": "application/json"
    }

    endpoints = [
        ("GET", "/api/v1/properties", {}),
        ("GET", "/api/v1/deals", {}),
        ("GET", "/api/v1/deals/summary", {}),
        ("GET", "/api/v1/matches/dashboard", {}),
        ("GET", "/api/v1/leads/1d3d636e-1460-4507-bc3c-2ac0f19f7250/matches", {}),
        ("GET", "/api/v1/revenue-intelligence/overview", {}),
        ("GET", "/api/v1/command-center/summary", {}),
        ("GET", "/api/v1/crm/dashboard", {}),
        ("GET", "/api/v1/transactions", {}),
    ]

    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for method, path, params in endpoints:
            try:
                resp = await client.request(method, path, headers=headers, params=params)
                print(f"[{resp.status_code}] {method} {path}")
                if resp.status_code != 200:
                    print(f"   Response: {resp.text[:200]}")
                else:
                    data = resp.json()
                    summary = f"Type: {type(data).__name__}"
                    if isinstance(data, list):
                        summary += f", Count: {len(data)}"
                    elif isinstance(data, dict):
                        summary += f", Keys: {list(data.keys())[:6]}"
                    print(f"   Success: {summary}")
            except Exception as e:
                print(f"[ERR] {method} {path}: {e}")

if __name__ == '__main__':
    asyncio.run(run())
