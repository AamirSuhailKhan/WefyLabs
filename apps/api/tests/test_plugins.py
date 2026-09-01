import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.modules.auth.service import create_access_token
from app.core.plugins.plugin_runtime import PluginRuntimeEngine, PluginStatus

@pytest.mark.asyncio
async def test_plugin_runtime_isolation_and_lifecycle(db_session: AsyncSession, test_broker: Broker):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Install Plugin Manifest
        inst_payload = {
            "plugin_id": "dubai-rera-checker",
            "name": "Dubai RERA Verification Plugin",
            "version": "1.0.0",
            "author": "Apex PropTech",
            "description": "Verifies DLD / RERA license validity for Dubai listings.",
            "permissions": ["crm:read", "properties:read"]
        }
        res_inst = await ac.post("/api/v1/plugins/install", json=inst_payload, headers=headers)
        assert res_inst.status_code == 201
        data_inst = res_inst.json()
        assert data_inst["manifest"]["name"] == "Dubai RERA Verification Plugin"
        assert data_inst["status"] == "enabled"

        # 2. List Installed Plugins
        res_list = await ac.get("/api/v1/plugins")
        assert res_list.status_code == 200
        plugins = res_list.json()
        assert len(plugins) >= 1
        ids = [p["manifest"]["plugin_id"] for p in plugins]
        assert "dubai-rera-checker" in ids

        # 3. Disable & Re-Enable Plugin
        res_dis = await ac.post("/api/v1/plugins/dubai-rera-checker/disable", headers=headers)
        assert res_dis.status_code == 200
        assert res_dis.json()["status"] == "disabled"

        res_en = await ac.post("/api/v1/plugins/dubai-rera-checker/enable", headers=headers)
        assert res_en.status_code == 200
        assert res_en.json()["status"] == "enabled"

        # 4. Execute Plugin in Sandboxed Catch-Block
        exec_payload = {
            "action_name": "verify_rera_license",
            "payload": {"permit_number": "DLD-109283"}
        }
        res_exec = await ac.post("/api/v1/plugins/dubai-rera-checker/execute", json=exec_payload, headers=headers)
        assert res_exec.status_code == 200
        data_exec = res_exec.json()
        assert data_exec["success"] is True
        assert data_exec["output"]["status"] == "completed"

    app.dependency_overrides.clear()
