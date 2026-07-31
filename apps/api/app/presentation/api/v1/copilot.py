from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.services.copilot_orchestrator import CopilotOrchestratorService

router = APIRouter(prefix="/v1/copilot", tags=["AI Copilot Operating System"])

class CopilotQueryRequest(BaseModel):
    query: str
    route_path: str = "/dashboard"
    active_entity_id: Optional[str] = None

@router.get("/suggested-actions")
async def get_copilot_suggested_actions(
    route_path: str = Query("/dashboard"),
    current_broker: Broker = Depends(get_current_broker)
):
    """Returns context-aware prompt action pills based on user route."""
    ctx_type = CopilotOrchestratorService.resolve_context_type(route_path)
    actions = CopilotOrchestratorService.get_suggested_actions(ctx_type)
    return {
        "route_path": route_path,
        "context_type": ctx_type.value,
        "suggested_actions": actions
    }

@router.post("/query")
async def execute_copilot_query_endpoint(
    req: CopilotQueryRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """Executes a context-aware AI Copilot query with tool calling & citations."""
    resp = CopilotOrchestratorService.execute_copilot_query(req.query, req.route_path)
    return {
        "query": resp.query,
        "context_type": resp.context_type.value,
        "summary": resp.summary,
        "answer_markdown": resp.answer_markdown,
        "confidence_score": resp.confidence_score,
        "citations": resp.citations,
        "suggested_followups": resp.suggested_followups,
        "executed_tools": [
            {"tool_name": t.tool_name, "arguments": t.arguments} for t in resp.executed_tools
        ]
    }
