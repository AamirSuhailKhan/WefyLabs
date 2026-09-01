"""
Part 21.8 — Autonomous Sales Loop REST API Router
==================================================
Production-grade REST endpoints for automation control, timeline,
explainability, dead-letter management, and broker approvals.

All endpoints enforce:
  - JWT broker authentication
  - organization_id from authenticated context ONLY (never from request body)
  - Tenant isolation at every data fetch
  - Audit logging of broker control actions
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_current_broker
from app.common.response import APIResponse, create_success_response

from app.modules.autonomous_loop.orchestrator import AutonomousSalesLoopService
from app.modules.autonomous_loop.audit_service import SalesLoopAuditService
from app.modules.autonomous_loop.dead_letter_service import DeadLetterService
from app.modules.autonomous_loop.state_machine import LeadStateMachine
from app.modules.autonomous_loop.dto import (
    SalesLoopEventDTO,
    AutomationStateDTO,
    BrokerControlDTO,
    DeadLetterDTO,
    ExplainabilityDTO,
    TimelineEntryDTO,
)
from app.modules.autonomous_loop.taxonomies import (
    SalesLoopEventType,
    LeadLifecycleState,
    ActorType,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/autonomous-loop",
    tags=["Part 21.8 — Autonomous Sales Loop"],
)


# ── Automation State ──────────────────────────────────────────────────────────

@router.get(
    "/leads/{lead_id}/state",
    summary="Get lead automation state",
    response_model=APIResponse,
)
async def get_automation_state(
    lead_id: str = Path(..., description="Lead UUID"),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """Returns the current automation state for a lead."""
    organization_id = str(broker.id)
    state_machine = LeadStateMachine(db)
    state = await state_machine.get_or_create_automation_state(lead_id, organization_id)

    dto = AutomationStateDTO(
        lead_id=state.lead_id,
        tenant_id=state.tenant_id,
        is_paused=state.is_paused,
        is_broker_takeover=state.is_broker_takeover,
        current_lifecycle_state=state.current_lifecycle_state,
        daily_action_count=state.daily_action_count,
        consecutive_failures=state.consecutive_failures,
        pending_action_type=state.pending_action_type,
        pending_since=state.pending_since,
        last_event_type=state.last_event_type,
        last_event_at=state.last_event_at,
    )
    return create_success_response(data=dto.model_dump(mode="json"))


# ── Autonomous Timeline ────────────────────────────────────────────────────────

@router.get(
    "/leads/{lead_id}/timeline",
    summary="Get autonomous sales timeline for a lead",
    response_model=APIResponse,
)
async def get_autonomous_timeline(
    lead_id: str = Path(..., description="Lead UUID"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """Returns the full autonomous sales timeline for broker review."""
    organization_id = str(broker.id)
    audit_svc = SalesLoopAuditService(db)
    timeline = await audit_svc.get_timeline(
        lead_id=lead_id,
        tenant_id=organization_id,
        limit=limit,
    )
    return create_success_response(data=[e.model_dump(mode="json") for e in timeline])


# ── Explainability ─────────────────────────────────────────────────────────────

@router.get(
    "/leads/{lead_id}/explain/{audit_id}",
    summary="Explain an autonomous decision",
    response_model=APIResponse,
)
async def explain_decision(
    lead_id: str = Path(..., description="Lead UUID"),
    audit_id: str = Path(..., description="Audit entry UUID"),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """Returns the structured explanation for a specific autonomous decision."""
    organization_id = str(broker.id)
    audit_svc = SalesLoopAuditService(db)
    explanation = await audit_svc.explain(
        audit_id=audit_id,
        lead_id=lead_id,
        tenant_id=organization_id,
    )
    if not explanation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audit entry {audit_id} not found for lead {lead_id}.",
        )
    return create_success_response(data=explanation.model_dump(mode="json"))


# ── Broker Controls ────────────────────────────────────────────────────────────

@router.post(
    "/leads/{lead_id}/pause",
    summary="Pause automation for a lead",
    response_model=APIResponse,
)
async def pause_automation(
    lead_id: str = Path(..., description="Lead UUID"),
    reason: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """Pauses autonomous outreach for a specific lead."""
    organization_id = str(broker.id)
    state_machine = LeadStateMachine(db)
    state = await state_machine.get_or_create_automation_state(lead_id, organization_id)

    state.is_paused = True
    state.paused_at = datetime.now(timezone.utc)
    state.paused_by = str(broker.id)
    state.pause_reason = reason[:500]
    state.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()

    logger.info(f"[AUTONOMOUS_LOOP_API] Automation paused: lead={lead_id} by={broker.id}")
    return create_success_response(data={"lead_id": lead_id, "is_paused": True, "reason": reason})


@router.post(
    "/leads/{lead_id}/resume",
    summary="Resume automation for a lead",
    response_model=APIResponse,
)
async def resume_automation(
    lead_id: str = Path(..., description="Lead UUID"),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """Resumes autonomous outreach for a specific lead."""
    organization_id = str(broker.id)
    state_machine = LeadStateMachine(db)
    state = await state_machine.get_or_create_automation_state(lead_id, organization_id)

    state.is_paused = False
    state.is_broker_takeover = False
    state.resumed_at = datetime.now(timezone.utc)
    state.resumed_by = str(broker.id)
    state.updated_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()

    logger.info(f"[AUTONOMOUS_LOOP_API] Automation resumed: lead={lead_id} by={broker.id}")
    return create_success_response(data={"lead_id": lead_id, "is_paused": False})


@router.post(
    "/leads/{lead_id}/handoff",
    summary="Force broker takeover for a lead",
    response_model=APIResponse,
)
async def force_broker_takeover(
    lead_id: str = Path(..., description="Lead UUID"),
    reason: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """Forces broker takeover, pausing all autonomous actions for this lead."""
    organization_id = str(broker.id)
    state_machine = LeadStateMachine(db)
    state = await state_machine.get_or_create_automation_state(lead_id, organization_id)

    state.is_paused = True
    state.is_broker_takeover = True
    state.paused_at = datetime.now(timezone.utc)
    state.paused_by = str(broker.id)
    state.pause_reason = f"[BROKER_TAKEOVER] {reason}"
    state.updated_at = datetime.now(timezone.utc)
    await db.flush()

    # Advance to HUMAN_HANDOFF state
    await state_machine.request_transition(
        lead_id=lead_id,
        tenant_id=organization_id,
        to_state=LeadLifecycleState.HUMAN_HANDOFF,
        actor=f"BROKER:{broker.id}",
        reason=reason,
    )
    await db.commit()

    logger.info(f"[AUTONOMOUS_LOOP_API] Broker takeover: lead={lead_id} by={broker.id}")
    return create_success_response(data={
        "lead_id": lead_id,
        "is_broker_takeover": True,
        "lifecycle_state": LeadLifecycleState.HUMAN_HANDOFF.value,
    })


@router.post(
    "/leads/{lead_id}/approve/{action_id}",
    summary="Approve a pending action",
    response_model=APIResponse,
)
async def approve_pending_action(
    lead_id: str = Path(..., description="Lead UUID"),
    action_id: str = Path(..., description="Pending action ID"),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """
    Approves a pending action that requires human approval.
    Emits SALES_ACTION_APPROVED event to the autonomous loop.
    """
    organization_id = str(broker.id)

    # Emit approval event to orchestrator
    svc = AutonomousSalesLoopService(db)
    event_dto = SalesLoopEventDTO(
        event_type=SalesLoopEventType.SALES_ACTION_APPROVED,
        tenant_id=organization_id,
        lead_id=lead_id,
        actor_type=ActorType.BROKER,
        actor_id=str(broker.id),
        payload={"action_id": action_id, "approved_by": str(broker.id)},
        source="broker_approval_api",
        idempotency_key=f"approve_{action_id}_{broker.id}",
    )
    result = await svc.process_event(event_dto)
    await db.commit()

    # Clear pending approval state
    state_machine = LeadStateMachine(db)
    state = await state_machine.get_or_create_automation_state(lead_id, organization_id)
    if state.pending_action_id == action_id:
        state.pending_action_id = None
        state.pending_action_type = None
        state.pending_since = None
        state.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return create_success_response(data={
        "lead_id": lead_id,
        "action_id": action_id,
        "approved": True,
        "processing_state": result.processing_state.value,
    })


@router.post(
    "/leads/{lead_id}/reject/{action_id}",
    summary="Reject a pending action",
    response_model=APIResponse,
)
async def reject_pending_action(
    lead_id: str = Path(..., description="Lead UUID"),
    action_id: str = Path(..., description="Pending action ID"),
    reason: Optional[str] = Body(None, embed=True),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """Rejects a pending action requiring human approval."""
    organization_id = str(broker.id)

    # Emit rejection event
    svc = AutonomousSalesLoopService(db)
    event_dto = SalesLoopEventDTO(
        event_type=SalesLoopEventType.SALES_ACTION_REJECTED,
        tenant_id=organization_id,
        lead_id=lead_id,
        actor_type=ActorType.BROKER,
        actor_id=str(broker.id),
        payload={
            "action_id": action_id,
            "rejected_by": str(broker.id),
            "reason": reason or "Broker rejected action.",
        },
        source="broker_rejection_api",
        idempotency_key=f"reject_{action_id}_{broker.id}",
    )
    await svc.process_event(event_dto)

    # Clear pending approval state
    state_machine = LeadStateMachine(db)
    state = await state_machine.get_or_create_automation_state(lead_id, organization_id)
    if state.pending_action_id == action_id:
        state.pending_action_id = None
        state.pending_action_type = None
        state.pending_since = None
        state.updated_at = datetime.now(timezone.utc)
    await db.commit()

    return create_success_response(data={
        "lead_id": lead_id,
        "action_id": action_id,
        "rejected": True,
        "reason": reason,
    })


# ── Event Ingestion ────────────────────────────────────────────────────────────

@router.post(
    "/events/ingest",
    summary="Ingest a sales loop event",
    response_model=APIResponse,
)
async def ingest_event(
    event_type: SalesLoopEventType = Body(...),
    lead_id: Optional[str] = Body(None),
    payload: dict = Body(default_factory=dict),
    idempotency_key: Optional[str] = Body(None),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """
    Manually ingests a domain event into the autonomous sales loop.
    organization_id is always from the authenticated broker — never from payload.
    """
    organization_id = str(broker.id)
    svc = AutonomousSalesLoopService(db)
    event_dto = SalesLoopEventDTO(
        event_type=event_type,
        tenant_id=organization_id,
        lead_id=lead_id,
        actor_type=ActorType.BROKER,
        actor_id=str(broker.id),
        payload=payload,
        source="broker_api",
        idempotency_key=idempotency_key or str(uuid.uuid4()),
    )
    result = await svc.process_event(event_dto)
    await db.commit()

    return create_success_response(data={
        "event_id": result.event_id,
        "processing_state": result.processing_state.value,
        "action_type": result.action_type,
        "decision_reason": result.decision_reason,
    })


# ── Dead-Letter Admin ──────────────────────────────────────────────────────────

@router.get(
    "/admin/dead-letters",
    summary="List unresolved dead-letter events (admin only)",
    response_model=APIResponse,
)
async def list_dead_letters(
    limit: int = Query(100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """Lists unresolved dead-letter events for the authenticated organization."""
    organization_id = str(broker.id)
    dl_svc = DeadLetterService(db)
    records = await dl_svc.list_unresolved(tenant_id=organization_id, limit=limit)
    return create_success_response(data=[r.model_dump(mode="json") for r in records])


@router.post(
    "/admin/dead-letters/{dead_letter_id}/resolve",
    summary="Resolve a dead-letter event (admin only)",
    response_model=APIResponse,
)
async def resolve_dead_letter(
    dead_letter_id: str = Path(..., description="Dead-letter UUID"),
    resolution_notes: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """Marks a dead-letter event as resolved by an admin broker."""
    organization_id = str(broker.id)
    dl_svc = DeadLetterService(db)
    resolved = await dl_svc.resolve(
        dead_letter_id=dead_letter_id,
        tenant_id=organization_id,
        resolved_by=str(broker.id),
        resolution_notes=resolution_notes,
    )
    await db.commit()

    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dead-letter {dead_letter_id} not found for your organization.",
        )
    return create_success_response(data={"dead_letter_id": dead_letter_id, "resolved": True})


# ── Tenant Emergency Automation Controls ─────────────────────────────────────

@router.post(
    "/emergency/pause",
    summary="Emergency pause all autonomous operations for the organization",
    response_model=APIResponse,
)
async def emergency_pause_tenant_automation(
    reason: str = Body("Emergency broker-triggered halt.", embed=True),
    broker=Depends(get_current_broker),
) -> APIResponse:
    """
    Emergency kill switch: Instantly pauses all autonomous outbound actions for this organization.
    """
    from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
    organization_id = str(broker.id)
    result = EmergencyAutomationPauseService.set_tenant_pause(
        tenant_id=organization_id,
        paused=True,
        paused_by=f"BROKER:{broker.id}",
        reason=reason,
    )
    return create_success_response(data=result)


@router.post(
    "/emergency/resume",
    summary="Resume autonomous operations for the organization",
    response_model=APIResponse,
)
async def emergency_resume_tenant_automation(
    broker=Depends(get_current_broker),
) -> APIResponse:
    """
    Resumes autonomous outbound actions for this organization after an emergency pause.
    """
    from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
    organization_id = str(broker.id)
    result = EmergencyAutomationPauseService.set_tenant_pause(
        tenant_id=organization_id,
        paused=False,
        paused_by=f"BROKER:{broker.id}",
        reason="Broker resumed normal operations.",
    )
    return create_success_response(data=result)


@router.get(
    "/emergency/status",
    summary="Get organization emergency automation pause status",
    response_model=APIResponse,
)
async def get_emergency_pause_status(
    broker=Depends(get_current_broker),
) -> APIResponse:
    """Returns current emergency automation pause status for this organization."""
    from app.modules.autonomous_loop.emergency_pause import EmergencyAutomationPauseService
    organization_id = str(broker.id)
    result = EmergencyAutomationPauseService.get_tenant_status(organization_id)
    return create_success_response(data=result)

