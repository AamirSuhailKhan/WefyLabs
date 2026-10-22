import asyncio
import httpx

async def test_isolation():
    async with httpx.AsyncClient(base_url="http://127.0.0.1:8000") as client:
        # 1. Login as Alpha
        res_a = await client.post("/api/v1/auth/login", json={"email": "broker.alpha.test@wefylabs.internal", "password": "TestPassword123!"})
        assert res_a.status_code == 200, f"Alpha login failed: {res_a.text}"
        token_a = res_a.json()["access_token"]
        org_a = "530a0335-5969-41d3-b5af-52d13e9ac393"
        org_b = "47ce32e4-2845-48f7-93d4-4f700c6cf844"

        # 2. Login as Beta
        res_b = await client.post("/api/v1/auth/login", json={"email": "broker.beta.test@wefylabs.internal", "password": "TestPassword123!"})
        assert res_b.status_code == 200, f"Beta login failed: {res_b.text}"
        token_b = res_b.json()["access_token"]

        # 3. Alpha lists leads with Alpha org header
        leads_a = await client.get("/api/v1/leads", headers={"Authorization": f"Bearer {token_a}", "X-WefyLabs-Organization-Id": org_a})
        a_leads = leads_a.json().get("data", [])
        print(f"Alpha leads count: {len(a_leads)}")
        assert len(a_leads) > 0, "Alpha has no leads"
        alpha_lead_id = a_leads[0]["id"]

        # 4. Alpha attempts to pass Beta org header -> expect 403
        spoof_res = await client.get("/api/v1/leads", headers={"Authorization": f"Bearer {token_a}", "X-WefyLabs-Organization-Id": org_b})
        print(f"Alpha spoofing Beta header status: {spoof_res.status_code}")
        assert spoof_res.status_code == 403, f"Expected 403, got {spoof_res.status_code}: {spoof_res.text}"

        # 5. Beta lists leads with Beta org header
        leads_b = await client.get("/api/v1/leads", headers={"Authorization": f"Bearer {token_b}", "X-WefyLabs-Organization-Id": org_b})
        b_leads = leads_b.json().get("data", [])
        print(f"Beta leads count: {len(b_leads)}")
        beta_lead_ids = [l["id"] for l in b_leads]
        assert alpha_lead_id not in beta_lead_ids, "Tenant leak: Beta saw Alpha lead!"

        # 6. Beta tries to access Alpha lead directly
        direct_res = await client.get(f"/api/v1/leads/{alpha_lead_id}", headers={"Authorization": f"Bearer {token_b}", "X-WefyLabs-Organization-Id": org_b})
        print(f"Beta accessing Alpha lead directly: {direct_res.status_code}")
        assert direct_res.status_code in (403, 404), f"Direct access returned {direct_res.status_code}"

        # 7. Beta tries to mutate Alpha lead
        mutate_res = await client.patch(f"/api/v1/leads/{alpha_lead_id}/status", headers={"Authorization": f"Bearer {token_b}", "X-WefyLabs-Organization-Id": org_b}, json={"status": "lost"})
        print(f"Beta mutating Alpha lead status: {mutate_res.status_code}")
        assert mutate_res.status_code in (403, 404), f"Mutation returned {mutate_res.status_code}"

        print(">>> ALL TENANT ISOLATION API TESTS PASSED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    asyncio.run(test_isolation())
