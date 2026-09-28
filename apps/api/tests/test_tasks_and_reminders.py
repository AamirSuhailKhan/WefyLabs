"""
Task and Follow-Up Reminder Management Test Suite
=================================================
Tests:
- Unauthenticated access to tasks returns 401.
- Broker can create tasks with priority, due date, description.
- Invalid task creation (empty title, invalid priority) returns 422.
- Tasks are listed for the authenticated broker with lead information.
- Broker isolation: Broker A cannot view, update, complete, or delete Broker B's tasks.
- Task status completion sets completed_at timestamp.
- Task status can be reverted/updated to pending.
- Task deletion removes record from database.
- Direct /api/v1/tasks and /api/v1/crm/services/tasks aliases work identically.
"""
import pytest
import uuid
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db, check_auth_rate_limit
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task

@pytest.fixture(autouse=True)
def override_rate_limit():
    app.dependency_overrides[check_auth_rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(check_auth_rate_limit, None)


async def create_test_broker(ac: AsyncClient, email: str, name: str) -> tuple[str, str]:
    """Helper to register and onboard a test broker, returning (broker_id, access_token)."""
    fix_res = await ac.post("/api/v1/auth/test/identity", json={"email": email, "name": name})
    token = fix_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Onboard
    phone = f"+9198{uuid.uuid4().int % 100000000:08d}"
    await ac.post("/api/v1/auth/onboard", json={
        "name": name,
        "phone": phone,
        "whatsapp_number": phone,
        "agency_name": f"{name} Realty",
        "city": "Bengaluru"
    }, headers=headers)
    
    me_res = await ac.get("/api/v1/auth/me", headers=headers)
    broker_id = me_res.json()["id"]
    return broker_id, token


@pytest.mark.asyncio
async def test_unauthenticated_tasks_access_denied(db_session: AsyncSession):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res_get = await ac.get("/api/v1/tasks")
        assert res_get.status_code == 401

        res_post = await ac.post("/api/v1/tasks", json={"title": "Unauthorized Task"})
        assert res_post.status_code == 401

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_task_lifecycle_end_to_end(db_session: AsyncSession):
    """Verifies Create -> List -> Update -> Complete -> Delete workflow."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        _, token = await create_test_broker(ac, "taskbroker1@example.com", "Task Broker One")
        headers = {"Authorization": f"Bearer {token}"}

        # 1. Create a lead first
        lead_payload = {
            "name": "Rajesh Kumar",
            "phone": "+919876543210",
            "pipeline_stage": "viewing",
            "score": "hot"
        }
        res_lead = await ac.post("/api/v1/crm/services/leads", json=lead_payload, headers=headers)
        assert res_lead.status_code == 201
        lead_id = res_lead.json()["id"]

        # 2. Create Task linked to lead
        due_iso = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        task_payload = {
            "title": "Call Rajesh Kumar — 2BHK Koramangala options",
            "description": "Discuss premium inventory in Koramangala 4th Block",
            "due_at": due_iso,
            "priority": "high",
            "lead_id": lead_id
        }
        res_task = await ac.post("/api/v1/crm/services/tasks", json=task_payload, headers=headers)
        assert res_task.status_code == 201
        task_data = res_task.json()
        task_id = task_data["id"]
        assert task_data["title"] == "Call Rajesh Kumar — 2BHK Koramangala options"
        assert task_data["status"] == "pending"
        assert task_data["priority"] == "high"
        assert task_data["lead_id"] == lead_id
        assert task_data["lead"]["name"] == "Rajesh Kumar"

        # 3. List tasks
        res_list = await ac.get("/api/v1/crm/services/tasks", headers=headers)
        assert res_list.status_code == 200
        tasks = res_list.json()
        assert len(tasks) >= 1
        assert any(t["id"] == task_id for t in tasks)

        # 4. Update task details
        res_update = await ac.patch(f"/api/v1/crm/services/tasks/{task_id}", json={
            "title": "Call Rajesh Kumar — Updated to 3BHK",
            "priority": "urgent"
        }, headers=headers)
        assert res_update.status_code == 200
        updated_data = res_update.json()
        assert updated_data["title"] == "Call Rajesh Kumar — Updated to 3BHK"
        assert updated_data["priority"] == "urgent"

        # 5. Mark task completed via complete endpoint
        res_complete = await ac.patch(f"/api/v1/crm/services/tasks/{task_id}/complete", headers=headers)
        assert res_complete.status_code == 200
        complete_data = res_complete.json()
        assert complete_data["status"] == "completed"
        assert complete_data["completed_at"] is not None

        # 6. Revert task status to pending
        res_revert = await ac.patch(f"/api/v1/crm/services/tasks/{task_id}", json={
            "status": "pending"
        }, headers=headers)
        assert res_revert.status_code == 200
        assert res_revert.json()["status"] == "pending"

        # 7. Delete task
        res_delete = await ac.delete(f"/api/v1/crm/services/tasks/{task_id}", headers=headers)
        assert res_delete.status_code == 200
        assert res_delete.json()["status"] == "success"

        # Verify task is deleted
        res_list_after = await ac.get("/api/v1/crm/services/tasks", headers=headers)
        assert not any(t["id"] == task_id for t in res_list_after.json())

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_broker_isolation_for_tasks(db_session: AsyncSession):
    """Ensures Broker A cannot see, update, complete, or delete Broker B's tasks."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        _, token_a = await create_test_broker(ac, "broker_a@example.com", "Broker Alpha")
        _, token_b = await create_test_broker(ac, "broker_b@example.com", "Broker Beta")

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # Broker A creates a task
        res_create = await ac.post("/api/v1/tasks", json={
            "title": "Broker A Private Task",
            "priority": "normal"
        }, headers=headers_a)
        assert res_create.status_code == 201
        task_a_id = res_create.json()["id"]

        # Broker B lists tasks -> must NOT see Broker A's task
        res_b_list = await ac.get("/api/v1/tasks", headers=headers_b)
        assert res_b_list.status_code == 200
        assert not any(t["id"] == task_a_id for t in res_b_list.json())

        # Broker B attempts to update Broker A's task -> 404
        res_b_update = await ac.patch(f"/api/v1/tasks/{task_a_id}", json={
            "title": "Hacked Title"
        }, headers=headers_b)
        assert res_b_update.status_code == 404

        # Broker B attempts to complete Broker A's task -> 404
        res_b_complete = await ac.patch(f"/api/v1/tasks/{task_a_id}/complete", headers=headers_b)
        assert res_b_complete.status_code == 404

        # Broker B attempts to delete Broker A's task -> 404
        res_b_delete = await ac.delete(f"/api/v1/tasks/{task_a_id}", headers=headers_b)
        assert res_b_delete.status_code == 404

    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_task_validation_rejections(db_session: AsyncSession):
    """Tests that empty titles and invalid priorities are rejected with 422."""
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        _, token = await create_test_broker(ac, "validationbroker@example.com", "Validation Broker")
        headers = {"Authorization": f"Bearer {token}"}

        # Empty title
        res_empty = await ac.post("/api/v1/tasks", json={"title": ""}, headers=headers)
        assert res_empty.status_code == 422

        # Invalid priority
        res_invalid_priority = await ac.post("/api/v1/tasks", json={
            "title": "Valid Title",
            "priority": "super_mega_urgent"
        }, headers=headers)
        assert res_invalid_priority.status_code == 422

    app.dependency_overrides.clear()
