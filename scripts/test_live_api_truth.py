import asyncio
import os
import sys
import json
import uuid
from pathlib import Path

api_dir = Path("apps/api").resolve()
sys.path.insert(0, str(api_dir))

from dotenv import load_dotenv
load_dotenv('apps/api/.env')

import jwt
import httpx
from app.config import settings
from app.main import app

async def run_audit():
    print("=== EXECUTING LIVE API CONTRACT AUDIT FOR PILOT TENANT ===")

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
        ("GET", "/api/v1/auth/me", {}),
        ("GET", "/api/v1/leads", {"limit": 50}),
        ("GET", "/api/v1/property-listings", {"limit": 50}),
        ("GET", "/api/v1/deals", {}),
        ("GET", "/api/v1/site-visits", {}),
        ("GET", "/api/v1/tasks", {}),
        ("GET", "/api/v1/revenue-intelligence/overview", {}),
        ("GET", "/api/v1/command-center/summary", {}),
        ("GET", "/api/v1/communication/v2/inbox", {}),
        ("GET", "/api/v1/matching/units", {"lead_id": "1d3d636e-1460-4507-bc3c-2ac0f19f7250"}),
    ]

    transport = httpx.ASGITransport(app=app)
    results = []

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        for method, path, params in endpoints:
            try:
                resp = await client.request(method, path, headers=headers, params=params)
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
                results.append({
                    "endpoint": path,
                    "method": method,
                    "status_code": resp.status_code,
                    "response": data
                })
                print(f"[{resp.status_code}] {method} {path}")
            except Exception as e:
                print(f"[ERR] {method} {path}: {e}")
                results.append({
                    "endpoint": path,
                    "method": method,
                    "status_code": "ERROR",
                    "response": str(e)
                })

    with open("scripts/live_api_audit_results.json", "w", encoding="utf-8") as out:
        json.dump(results, out, indent=2, default=str)
    print("Saved scripts/live_api_audit_results.json")

if __name__ == '__main__':
    asyncio.run(run_audit())
