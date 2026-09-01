import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.dependencies import get_db
from app.models.broker import Broker
from app.models.lead import Lead
from app.modules.auth.service import create_access_token

@pytest.mark.asyncio
async def test_customer_success_endpoints(db_session: AsyncSession, test_broker: Broker, test_lead: Lead):
    async def override_get_db():
        yield db_session
    app.dependency_overrides[get_db] = override_get_db

    token = create_access_token({"sub": test_broker.email, "email": test_broker.email})
    headers = {"Authorization": f"Bearer {token}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Get Customer Health Score & Retention Recommendations
        res_health = await ac.get("/api/v1/customer-success/health", headers=headers)
        assert res_health.status_code == 200
        data_health = res_health.json()
        assert "health_score" in data_health
        assert "churn_risk_pct" in data_health
        assert "onboarding_completed_pct" in data_health
        assert len(data_health["retention_recommendations"]) >= 1

        # 2. Submit CSAT / NPS Sentiment Feedback
        fb_payload = {
            "nps_score": 10,
            "csat_score": 5,
            "feedback_notes": "BeetleLabs automated WhatsApp qualification is incredible!"
        }
        res_fb = await ac.post("/api/v1/customer-success/feedback", json=fb_payload, headers=headers)
        assert res_fb.status_code == 200
        assert res_fb.json()["status"] == "success"

        # 3. Create Support Console Ticket
        ticket_payload = {
            "subject": "Question about custom domain setup",
            "description": "How do I configure my agency custom domain?",
            "priority": "high"
        }
        res_ticket = await ac.post("/api/v1/customer-success/support/tickets", json=ticket_payload, headers=headers)
        assert res_ticket.status_code == 201
        data_ticket = res_ticket.json()
        assert data_ticket["subject"] == "Question about custom domain setup"
        assert data_ticket["status"] == "open"

        # 4. List Support Console Tickets
        res_list = await ac.get("/api/v1/customer-success/support/tickets", headers=headers)
        assert res_list.status_code == 200
        tickets = res_list.json()
        assert len(tickets) >= 1
        assert tickets[0]["subject"] == "Question about custom domain setup"

    app.dependency_overrides.clear()
