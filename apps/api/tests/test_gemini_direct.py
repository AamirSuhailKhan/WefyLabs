import asyncio
import json
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.config import settings
from app.models.broker import Broker
from app.models.lead import Lead
from app.services.copilot_orchestrator import CopilotOrchestratorService

logging.basicConfig(level=logging.INFO)

@pytest.mark.skip(reason="Manual direct integration test with live Gemini API")
async def test_live_gemini():
    print("\n==========================================")
    print("TESTING GEMINI LIVE INTEGRATION & PROMPT RESPONSES")
    print("==========================================\n")
    print("GEMINI_API_KEY Configured: [REDACTED]")

    mock_db = AsyncMock()
    mock_leads = [
        Lead(id="lead-1", name="Rajesh Kumar", phone="+919876543210", score="hot", budget_min=4000000, budget_max=5000000, pipeline_stage="viewing", source="whatsapp"),
        Lead(id="lead-2", name="Priya Ananth", phone="+919812345678", score="hot", budget_min=7500000, budget_max=9000000, pipeline_stage="contacted", source="facebook"),
        Lead(id="lead-3", name="Amitabh V", phone="+919988776655", score="warm", budget_min=2000000, budget_max=2500000, pipeline_stage="new", source="google")
    ]

    lead_result = MagicMock()
    lead_result.scalars.return_value.all.return_value = mock_leads
    mock_db.execute.return_value = lead_result

    broker = Broker(
        id="00000000-0000-0000-0000-000000000001",
        name="Aamir Suhail",
        email="aamir@beetlelabs.ai",
        city="Bengaluru",
        agency_name="BeetleLabs Real Estate Solutions"
    )

    queries = [
        ("Who should I call today?", "/dashboard"),
        ("Which deals are at risk?", "/deals"),
        ("Generate WhatsApp follow-up message for Priya Ananth", "/inbox")
    ]

    history = [
        {"sender": "user", "text": "Hi Copilot, what is my pipeline status?"},
        {"sender": "copilot", "text": "You have 3 active leads registered."}
    ]

    for q, route in queries:
        print(f"\n---> SENDING PROMPT: '{q}' [Route: {route}]")
        resp = await CopilotOrchestratorService.async_execute_copilot_query(
            db=mock_db,
            broker=broker,
            query=q,
            route_path=route,
            history=history
        )

        print(f"SUMMARY: {resp.summary}")
        print(f"CONFIDENCE: {resp.confidence_score}")
        print(f"CITATIONS: {resp.citations}")
        print("ANSWER MARKDOWN FROM GEMINI:")
        print("------------------------------------------")
        safe_markdown = resp.answer_markdown.encode('ascii', 'replace').decode('ascii')
        print(safe_markdown)
        print("------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(test_live_gemini())
