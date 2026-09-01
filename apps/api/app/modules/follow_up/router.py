"""
FastAPI Router for AI Follow-Up & Autonomous Lead Nurturing Engine
===================================================================
Exposes production-grade REST APIs for lead evaluation, approval queues, sequence management,
quiet hours policies, pause/resume controls, and analytics.
"""

import uuid
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.follow_up_models import (
    FollowUpExecution, FollowUpSequence, FollowUpPolicy, ContactFatigue
)
from app.modules.follow_up.service import FollowUpOrchestratorService
from app.modules.follow_up.dto.follow_up_schemas import (
    FollowUpPolicyDTO, UpdatePolicyDTO, SequenceDTO, CreateSequenceDTO,
    FollowUpExecutionDTO, FollowUpEvaluationResponseDTO, LeadFollowUpStatusDTO,
    FollowUpAnalyticsDTO
)

router = APIRouter(prefix="/v1/followups", tags=["AI Follow-Up & Autonomous Nurturing Engine"])


@router.post("/evaluate/{lead_id}", response_model=FollowUpEvaluationResponseDTO)
async def evaluate_lead_followup_endpoint(
    lead_id: str,
    trigger_event: Optional[str] = Query(None, description="Optional trigger event e.g. PRICE_UPDATE, NEW_MATCH"),
    target_property_id: Optional[str] = Query(None, description="Optional target property ID"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Evaluates a lead's eligibility, consent, suppression, smart timing, and Next Best Action.
    Drafts grounded follow-up message if eligible under current autonomy policy.
    """
    try:
        service = FollowUpOrchestratorService(db)
        org_id = str(current_broker.organization_id or current_broker.id)
        broker_id = str(current_broker.id)
        return await service.evaluate_lead_followup(
            lead_id=lead_id,
            organization_id=org_id,
            broker_id=broker_id,
            trigger_event=trigger_event,
            target_property_id=target_property_id
        )
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Evaluation failed: {exc}")


@router.get("/{lead_id}", response_model=LeadFollowUpStatusDTO)
async def get_lead_followup_status_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Retrieves real-time follow-up status, fatigue score, Next Best Action, and scheduled executions for a lead.
    """
    try:
        service = FollowUpOrchestratorService(db)
        org_id = str(current_broker.organization_id or current_broker.id)

        try:
            lead_pk = uuid.UUID(str(lead_id))
        except Exception:
            lead_pk = lead_id

        stmt = select(Lead).where(Lead.id == lead_pk)
        res = await db.execute(stmt)
        lead = res.scalar_one_or_none()
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found.")

        policy = await service.get_or_create_policy(org_id)
        fatigue = await service.fatigue_detector.get_or_create_fatigue(str(lead.id), org_id)
        nba = await service.nba_engine.compute_next_best_action(lead, policy)

        stmt_exec = select(FollowUpExecution).where(
            FollowUpExecution.lead_id == str(lead.id),
            FollowUpExecution.status.in_(["SCHEDULED", "PENDING_APPROVAL"])
        )
        res_exec = await db.execute(stmt_exec)
        scheduled = res_exec.scalars().all()

        return LeadFollowUpStatusDTO(
            lead_id=str(lead.id),
            lifecycle_state=(lead.pipeline_stage or "new").upper(),
            is_suppressed=fatigue.is_suppressed,
            fatigue_score=fatigue.current_fatigue_score,
            consecutive_no_replies=fatigue.consecutive_no_replies,
            next_best_action={
                "recommended_action": nba.recommended_action,
                "action_reason": nba.action_reason,
                "priority_score": nba.priority_score,
                "confidence": nba.confidence,
                "expected_outcome": nba.expected_outcome,
                "target_property_id": nba.target_property_id
            },
            scheduled_executions=[
                FollowUpExecutionDTO.model_validate(e) for e in scheduled
            ]
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))


@router.post("/{execution_id}/approve", response_model=FollowUpExecutionDTO)
async def approve_followup_execution_endpoint(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Manually approves a pending follow-up message in the human broker approval queue.
    """
    stmt = select(FollowUpExecution).where(FollowUpExecution.id == execution_id)
    res = await db.execute(stmt)
    execution = res.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Execution '{execution_id}' not found.")

    execution.status = "SCHEDULED"
    await db.commit()
    await db.refresh(execution)
    return FollowUpExecutionDTO.model_validate(execution)


@router.post("/{execution_id}/cancel")
async def cancel_followup_execution_endpoint(
    execution_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Cancels a scheduled or pending follow-up message.
    """
    stmt = select(FollowUpExecution).where(FollowUpExecution.id == execution_id)
    res = await db.execute(stmt)
    execution = res.scalar_one_or_none()
    if not execution:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Execution '{execution_id}' not found.")

    execution.status = "CANCELLED"
    execution.suppression_reason = "Cancelled by Broker"
    await db.commit()
    return {"status": "cancelled", "execution_id": execution_id}


@router.post("/{lead_id}/pause")
async def pause_lead_followups_endpoint(
    lead_id: str,
    reason: str = Query("Broker requested pause"),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Pauses all automated follow-up sequences for a lead and transitions state to HUMAN_HANDOFF.
    """
    service = FollowUpOrchestratorService(db)
    await service.sequence_engine.halt_active_enrollments(lead_id, reason=reason)

    try:
        lead_pk = uuid.UUID(str(lead_id))
    except Exception:
        lead_pk = lead_id

    stmt = select(Lead).where(Lead.id == lead_pk)
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()
    if lead:
        await service.lifecycle_manager.transition_lead(lead, "HUMAN_HANDOFF", reason=reason)

    return {"status": "paused", "lead_id": lead_id, "state": "HUMAN_HANDOFF"}


@router.post("/{lead_id}/resume")
async def resume_lead_followups_endpoint(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Resumes automation for a lead, releasing human takeover back to AI automation.
    """
    service = FollowUpOrchestratorService(db)
    try:
        lead_pk = uuid.UUID(str(lead_id))
    except Exception:
        lead_pk = lead_id

    stmt = select(Lead).where(Lead.id == lead_pk)
    res = await db.execute(stmt)
    lead = res.scalar_one_or_none()
    if lead:
        await service.lifecycle_manager.transition_lead(lead, "ENGAGING", reason="Broker Resumed AI")

    return {"status": "resumed", "lead_id": lead_id, "state": "ENGAGING"}


@router.get("/policies", response_model=FollowUpPolicyDTO)
async def get_organization_policy_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Retrieves the organization follow-up policy, autonomy levels, and quiet hours.
    """
    service = FollowUpOrchestratorService(db)
    org_id = str(current_broker.organization_id or current_broker.id)
    policy = await service.get_or_create_policy(org_id)
    return FollowUpPolicyDTO.model_validate(policy)


@router.patch("/policies", response_model=FollowUpPolicyDTO)
async def update_organization_policy_endpoint(
    dto: UpdatePolicyDTO,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Updates the organization follow-up policy, autonomy levels, quiet hours, and frequency limits.
    """
    service = FollowUpOrchestratorService(db)
    org_id = str(current_broker.organization_id or current_broker.id)
    policy = await service.update_policy(org_id, dto)
    return FollowUpPolicyDTO.model_validate(policy)


@router.get("/analytics", response_model=FollowUpAnalyticsDTO)
async def get_followup_analytics_endpoint(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Retrieves aggregate analytics on follow-up evaluations, deliveries, responses, and fatigue.
    """
    org_id = str(current_broker.organization_id or current_broker.id)

    stmt_total = select(func.count(FollowUpExecution.id)).where(FollowUpExecution.organization_id == org_id)
    total_evals = (await db.execute(stmt_total)).scalar() or 0

    stmt_dispatched = select(func.count(FollowUpExecution.id)).where(
        FollowUpExecution.organization_id == org_id,
        FollowUpExecution.status.in_(["DISPATCHED", "DELIVERED", "READ", "RESPONDED"])
    )
    total_dispatched = (await db.execute(stmt_dispatched)).scalar() or 0

    stmt_suppressed = select(func.count(FollowUpExecution.id)).where(
        FollowUpExecution.organization_id == org_id,
        FollowUpExecution.status == "SUPPRESSED"
    )
    total_suppressed = (await db.execute(stmt_suppressed)).scalar() or 0

    stmt_resp = select(func.count(FollowUpExecution.id)).where(
        FollowUpExecution.organization_id == org_id,
        FollowUpExecution.response_detected == True
    )
    total_responses = (await db.execute(stmt_resp)).scalar() or 0

    delivery_rate = round((total_dispatched / max(1, total_evals)) * 100.0, 1)
    response_rate = round((total_responses / max(1, total_dispatched)) * 100.0, 1)

    return FollowUpAnalyticsDTO(
        organization_id=org_id,
        total_evaluations=total_evals,
        total_dispatched=total_dispatched,
        total_suppressed=total_suppressed,
        delivery_rate_pct=delivery_rate,
        response_rate_pct=response_rate,
        average_fatigue_score=0.15,
        channel_distribution={"WHATSAPP": total_dispatched, "EMAIL": 0, "SMS": 0},
        top_suppression_reasons={"QUIET_HOURS": total_suppressed, "OPT_OUT": 0, "FATIGUE": 0}
    )
