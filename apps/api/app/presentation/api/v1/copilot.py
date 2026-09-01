from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from pydantic import BaseModel

from sqlalchemy.ext.asyncio import AsyncSession
from app.dependencies import get_db, get_current_broker, get_optional_broker
from app.models.broker import Broker
from app.services.copilot_orchestrator import CopilotOrchestratorService

router = APIRouter(prefix="/copilot", tags=["AI Copilot Operating System"])

class CopilotQueryRequest(BaseModel):
    query: str
    route_path: str = "/dashboard"
    active_entity_id: Optional[str] = None
    history: Optional[List[dict]] = None

class CopilotActionRequest(BaseModel):
    action_type: str
    target_id: Optional[str] = None
    payload: Optional[dict] = None

@router.get("/suggested-actions")
async def get_copilot_suggested_actions(
    route_path: str = Query("/dashboard"),
    current_broker: Optional[Broker] = Depends(get_optional_broker)
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
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Executes a context-aware AI Copilot query with tool calling & citations."""
    try:
        resp = await CopilotOrchestratorService.async_execute_copilot_query(
            db=db,
            broker=current_broker,
            query=req.query,
            route_path=req.route_path,
            history=req.history,
            active_entity_id=req.active_entity_id
        )
        return {
            "query": resp.query,
            "context_type": resp.context_type.value,
            "summary": resp.summary,
            "reasoning": resp.reasoning,
            "answer_markdown": resp.answer_markdown,
            "rich_cards": resp.rich_cards,
            "action_buttons": resp.action_buttons,
            "confidence_score": resp.confidence_score,
            "citations": resp.citations,
            "suggested_followups": resp.suggested_followups,
            "executed_tools": [
                {"tool_name": t.tool_name, "arguments": t.arguments} for t in resp.executed_tools
            ]
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Copilot Execution Error: {str(e)}")

@router.post("/actions/execute")
async def execute_copilot_action_endpoint(
    req: CopilotActionRequest,
    current_broker: Broker = Depends(get_current_broker),
    db: AsyncSession = Depends(get_db)
):
    """Executes a real CRM action triggered via 1-click Copilot action buttons."""
    res = await CopilotOrchestratorService.async_execute_crm_action(
        db=db,
        broker=current_broker,
        action_type=req.action_type,
        target_id=req.target_id,
        payload=req.payload or {}
    )
    return res
