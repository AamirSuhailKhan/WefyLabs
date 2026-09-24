"""
WefyLabs AI Workforce — API Controller
Part 10 Internal Workforce Endpoints
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.modules.ai_agent.workforce.registry import list_registered_agents
from app.modules.ai_agent.workforce.router import WorkforceRouter
from app.modules.ai_agent.workforce.orchestrator import WorkforceOrchestrator

router = APIRouter(prefix="/api/v1/workforce", tags=["AI Workforce"])
orchestrator = WorkforceOrchestrator()


class RouteTestRequestDTO(BaseModel):
    query: str
    is_internal_manager: bool = False


class RouteTestResponseDTO(BaseModel):
    selected_role: str
    confidence: float
    is_deterministic_fast_path: bool
    reason: str


class WorkforceExecuteRequestDTO(BaseModel):
    lead_id: str
    message: str
    session_id: Optional[str] = None
    supplementary_data: Optional[Dict[str, Any]] = None


@router.get("/agents", response_model=List[Dict[str, Any]])
async def get_workforce_agents(
    broker: Broker = Depends(get_current_broker),
):
    """Retrieve canonical metadata for all 8 workforce specialist agents."""
    return list_registered_agents()


@router.post("/route", response_model=RouteTestResponseDTO)
async def test_workforce_route(
    body: RouteTestRequestDTO,
    broker: Broker = Depends(get_current_broker),
):
    """Test routing decision for a given message."""
    decision = WorkforceRouter.route(
        query=body.query,
        is_internal_manager=body.is_internal_manager,
    )
    return RouteTestResponseDTO(
        selected_role=decision.selected_role.value,
        confidence=decision.confidence,
        is_deterministic_fast_path=decision.is_deterministic_fast_path,
        reason=decision.reason,
    )


@router.post("/execute")
async def execute_workforce_turn(
    body: WorkforceExecuteRequestDTO,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker),
):
    """
    Execute an authenticated conversational turn across the AI Workforce.
    Tenant context is strictly derived from authenticated broker JWT.
    """
    org_id = getattr(broker, "organization_id", None) or str(broker.id)
    is_manager = getattr(broker, "role", "broker") in ("admin", "manager")

    result = await orchestrator.execute_turn(
        db=db,
        organization_id=str(org_id),
        lead_id=body.lead_id,
        customer_message=body.message,
        session_id=body.session_id,
        is_internal_manager=is_manager,
        supplementary_data=body.supplementary_data,
    )
    return result
