"""
Part 21.5 — AI Sales Action & Follow-Up REST Router
===================================================
Production-grade REST endpoints for evaluating Next Best Actions,
approving/executing sales actions, managing follow-up states, and pause/resume controls.
"""
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.modules.sales_action.service import SalesActionDomainService
from app.modules.sales_action.dto import (
    SalesActionDecisionDTO,
    SalesActionExecutionResultDTO,
    FollowUpStateDTO,
    EvaluateSalesActionRequestDTO,
    ApproveSalesActionRequestDTO,
)

router = APIRouter(prefix="/leads/{lead_id}", tags=["Part 21.5 — AI Sales Action & Follow-Up Engine"])


@router.get("/sales-actions/next", response_model=SalesActionDecisionDTO)
async def get_next_sales_action_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Computes and returns the deterministic Next Best Action for the lead,
    including consent, quiet hours, and fatigue compliance checks.
    """
    try:
        service = SalesActionDomainService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        return await service.evaluate_next_sales_action(
            lead_id=lead_id,
            organization_id=org_id,
            broker=current_broker,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate next sales action: {e}",
        )


@router.get("/sales-actions", response_model=List[SalesActionDecisionDTO])
async def get_sales_actions_history_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Retrieves the active Next Best Action decision and recent proposals for the lead.
    """
    try:
        service = SalesActionDomainService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        return await service.get_lead_sales_actions(
            lead_id=lead_id,
            organization_id=org_id,
            broker=current_broker,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch sales actions: {e}",
        )


@router.post("/sales-actions/evaluate", response_model=SalesActionDecisionDTO)
async def evaluate_sales_action_endpoint(
    lead_id: str,
    payload: Optional[EvaluateSalesActionRequestDTO] = None,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Evaluates or re-evaluates the Next Best Action for a lead given optional trigger events.
    """
    try:
        service = SalesActionDomainService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        trigger = payload.trigger_event if payload else None
        target_prop = payload.target_property_id if payload else None
        return await service.evaluate_next_sales_action(
            lead_id=lead_id,
            organization_id=org_id,
            trigger_event=trigger,
            target_property_id=target_prop,
            broker=current_broker,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sales action evaluation failed: {e}",
        )


@router.post("/sales-actions/{action_id}/approve", response_model=SalesActionDecisionDTO)
async def approve_sales_action_endpoint(
    lead_id: str,
    action_id: str,
    payload: Optional[ApproveSalesActionRequestDTO] = None,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Authorizes a review-pending sales action for execution.
    """
    try:
        service = SalesActionDomainService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        custom_msg = payload.custom_message_body if payload else None
        return await service.approve_sales_action(
            action_id=action_id,
            lead_id=lead_id,
            organization_id=org_id,
            custom_message=custom_msg,
            broker=current_broker,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to approve sales action: {e}",
        )


@router.post("/sales-actions/{action_id}/execute", response_model=SalesActionExecutionResultDTO)
async def execute_sales_action_endpoint(
    lead_id: str,
    action_id: str,
    payload: Optional[ApproveSalesActionRequestDTO] = None,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Directly dispatches an approved sales action across configured communication channels.
    """
    try:
        service = SalesActionDomainService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        custom_msg = payload.custom_message_body if payload else None
        return await service.execute_sales_action(
            action_id=action_id,
            lead_id=lead_id,
            organization_id=org_id,
            custom_message=custom_msg,
            broker=current_broker,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute sales action: {e}",
        )


@router.post("/sales-actions/{action_id}/cancel", response_model=Dict[str, Any])
async def cancel_sales_action_endpoint(
    lead_id: str,
    action_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Cancels a scheduled or pending sales action.
    """
    try:
        service = SalesActionDomainService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        return await service.cancel_sales_action(
            action_id=action_id,
            lead_id=lead_id,
            organization_id=org_id,
            broker=current_broker,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel sales action: {e}",
        )


@router.get("/follow-up/state", response_model=FollowUpStateDTO)
async def get_follow_up_state_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Retrieves real-time follow-up state, fatigue score, and scheduled actions for a lead.
    """
    try:
        service = SalesActionDomainService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        return await service.get_follow_up_state(
            lead_id=lead_id,
            organization_id=org_id,
            broker=current_broker,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch follow-up state: {e}",
        )


@router.post("/follow-up/pause", response_model=FollowUpStateDTO)
async def pause_follow_up_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Pauses automated follow-up communications for a lead.
    """
    try:
        service = SalesActionDomainService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        return await service.pause_follow_up(
            lead_id=lead_id,
            organization_id=org_id,
            broker=current_broker,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause follow-up: {e}",
        )


@router.post("/follow-up/resume", response_model=FollowUpStateDTO)
async def resume_follow_up_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker),
):
    """
    Resumes automated follow-up communications and resets contact fatigue counters.
    """
    try:
        service = SalesActionDomainService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        return await service.resume_follow_up(
            lead_id=lead_id,
            organization_id=org_id,
            broker=current_broker,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume follow-up: {e}",
        )
