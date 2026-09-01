import uuid
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel

from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.services.workflow_execution_engine import WorkflowExecutionEngine
from app.services.workflow_ai_generator import WorkflowAIGeneratorService

router = APIRouter(prefix="/workflows", tags=["No-Code Visual Workflow Builder"])

class AIGenerateWorkflowRequest(BaseModel):
    prompt: str

@router.get("")
async def list_workflows_endpoint(
    is_active: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    current_broker: Broker = Depends(get_current_broker)
):
    """Lists visual workflow definitions and active triggers."""
    return {
        "total": 2,
        "page": page,
        "limit": limit,
        "items": [
            {
                "id": "70707070-7070-7070-7070-707070707070",
                "name": "High Budget Lead Auto-Assignment & Brochure Dispatch",
                "description": "Triggers when a new lead arrives on WhatsApp with budget > $1M.",
                "is_active": True,
                "trigger_type": "whatsapp_received",
                "nodes_count": 4,
                "last_executed_at": "2026-07-30T15:45:00Z"
            },
            {
                "id": "80808080-8080-8080-8080-808080808080",
                "name": "Stalled Deal Escalate to Manager",
                "description": "Triggers when a deal remains in 'Booking' stage for over 5 days.",
                "is_active": True,
                "trigger_type": "deal_moved",
                "nodes_count": 3,
                "last_executed_at": "2026-07-29T18:20:00Z"
            }
        ]
    }

@router.post("/ai/generate")
async def generate_workflow_ai_endpoint(
    req: AIGenerateWorkflowRequest,
    current_broker: Broker = Depends(get_current_broker)
):
    """Generates visual node graph workflow JSON from natural language prompt."""
    res = WorkflowAIGeneratorService.generate_workflow_from_prompt(req.prompt)
    return res

@router.post("/{workflow_id}/execute")
async def execute_workflow_endpoint(
    workflow_id: uuid.UUID,
    payload: Dict[str, Any] = {},
    current_broker: Broker = Depends(get_current_broker)
):
    """Executes workflow run over DAG node graph."""
    res = WorkflowExecutionEngine.execute_workflow_dag(str(workflow_id), payload)
    return res
