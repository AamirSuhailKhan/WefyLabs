"""WefyLabs Native CRM Core — REST API Controller
=================================================
Mounts versioned endpoints under /api/v1/crm for:
  - Customer 360 & Timeline
  - Lead Operator Table, Stage Transitions & Bulk Operations
  - Sales Pipeline Kanban
  - Opportunities / Deals Workspace
  - Tasks, Activities & Notes
  - Universal Multi-Tenant CRM Search
  - Operational Metrics Dashboard
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, desc

from app.database import get_db
from app.dependencies import get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import Task, Activity, LeadNote
from app.models.transaction_models import DealTransaction, DealMilestone
from app.models.calendar_models import SchedulingMeeting
from app.models.revenue_autopilot_models import RevenueOpportunity

from app.modules.crm.dto.crm_schemas import (
    Customer360Response, CustomerTimelineEventDTO,
    LeadCRMListItem, LeadCRMFilterParams, LeadStageTransitionRequest,
    LeadAssignRequest, BulkLeadOperationRequest, BulkOperationResult,
    PipelineKanbanResponse, OpportunitySummaryDTO, OpportunityDetailResponse,
    OpportunityCreateRequest, OpportunityStageUpdateRequest,
    CRMTaskCreateRequest, CRMTaskUpdateRequest, CRMTaskResponse,
    CRMActivityCreateRequest, CRMActivityResponse,
    CRMNoteCreateRequest, CRMNoteResponse,
    CRMSearchResponse, CRMDashboardMetricsResponse
)
from app.modules.crm.services.customer_360_service import Customer360Service
from app.modules.crm.services.crm_lead_service import CRMLeadService
from app.modules.crm.services.crm_pipeline_service import CRMPipelineService
from app.modules.crm.services.crm_timeline_service import CRMTimelineService
from app.modules.crm.services.crm_search_service import CRMSearchService

router = APIRouter(prefix="/crm", tags=["Native CRM Core & Customer 360"])


# ─────────────────────────────────────────────────────────────────────────────
# 1. Customer 360 & Directory
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/customers", response_model=List[LeadCRMListItem])
async def list_customers(
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """List customer records with search and pagination scoped strictly to authenticated tenant."""
    lead_service = CRMLeadService(db)
    params = LeadCRMFilterParams(search=search, limit=limit, offset=offset)
    org_id = str(broker.organization_id or broker.id)
    items, _ = await lead_service.list_leads(broker.id, org_id, params)
    return items


@router.get("/customers/{customer_id}", response_model=Customer360Response)
async def get_customer_360(
    customer_id: str,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Fetch the canonical 360-degree customer workspace."""
    service = Customer360Service(db)
    org_id = str(broker.organization_id or broker.id)
    try:
        return await service.get_customer_360(customer_id, broker.id, org_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/customers/{customer_id}/timeline", response_model=List[CustomerTimelineEventDTO])
async def get_customer_timeline(
    customer_id: str,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Fetch unified activity and event timeline with complete provenance."""
    timeline_service = CRMTimelineService(db)
    org_id = str(broker.organization_id or broker.id)
    return await timeline_service.get_unified_timeline(customer_id, org_id, limit)


# ─────────────────────────────────────────────────────────────────────────────
# 2. Lead CRM (Operator Table, Transitions, Assignment, Bulk)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/leads", response_model=Dict[str, Any])
async def list_crm_leads(
    stage: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    score: Optional[str] = None,
    source: Optional[str] = None,
    property_type: Optional[str] = None,
    budget_min: Optional[int] = None,
    budget_max: Optional[int] = None,
    search: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc"),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """High-performance operator table with rich multi-faceted filtering and sorting."""
    lead_service = CRMLeadService(db)
    params = LeadCRMFilterParams(
        stage=stage,
        status=status_filter,
        score=score,
        source=source,
        property_type=property_type,
        budget_min=budget_min,
        budget_max=budget_max,
        search=search,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        sort_order=sort_order
    )
    org_id = str(broker.organization_id or broker.id)
    items, total = await lead_service.list_leads(broker.id, org_id, params)
    return {
        "items": [item.model_dump() for item in items],
        "total": total,
        "limit": limit,
        "offset": offset
    }


@router.get("/leads/{lead_id}", response_model=Customer360Response)
async def get_crm_lead_detail(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Detailed CRM lead view with full commercial context."""
    service = Customer360Service(db)
    org_id = str(broker.organization_id or broker.id)
    try:
        return await service.get_customer_360(lead_id, broker.id, org_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/leads/{lead_id}/stage")
async def transition_lead_stage(
    lead_id: str,
    payload: LeadStageTransitionRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Execute controlled stage transition with audit logging and Revenue Intelligence event emission."""
    lead_service = CRMLeadService(db)
    org_id = str(broker.organization_id or broker.id)
    try:
        lead = await lead_service.transition_stage(
            lead_id=lead_id,
            new_stage=payload.new_stage,
            reason=payload.reason,
            broker_id=broker.id,
            organization_id=org_id
        )
        return {
            "status": "success",
            "lead_id": str(lead.id),
            "pipeline_stage": lead.pipeline_stage,
            "status_code": lead.status
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/leads/{lead_id}/assign")
async def reassign_lead(
    lead_id: str,
    payload: LeadAssignRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Reassign lead ownership to another broker, tracking history and emitting events."""
    lead_service = CRMLeadService(db)
    org_id = str(broker.organization_id or broker.id)
    try:
        lead = await lead_service.reassign_lead(
            lead_id=lead_id,
            target_broker_id=payload.target_broker_id,
            reason=payload.reason,
            current_broker_id=broker.id,
            organization_id=org_id
        )
        return {
            "status": "success",
            "lead_id": str(lead.id),
            "assigned_broker_id": str(lead.broker_id)
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/bulk/leads", response_model=BulkOperationResult)
async def execute_bulk_leads_operation(
    payload: BulkLeadOperationRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Execute safe bounded bulk operations across targeted leads."""
    lead_service = CRMLeadService(db)
    org_id = str(broker.organization_id or broker.id)
    return await lead_service.execute_bulk_operation(payload, broker.id, org_id)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Sales Pipeline (Kanban)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/pipeline", response_model=PipelineKanbanResponse)
async def get_sales_pipeline(
    assigned_to: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Retrieve full Kanban sales pipeline columns, cards, and stage totals."""
    service = CRMPipelineService(db)
    org_id = str(broker.organization_id or broker.id)
    return await service.get_pipeline_kanban(broker.id, org_id, assigned_to)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Opportunities / Deals Workspace
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/opportunities", response_model=List[OpportunitySummaryDTO])
async def list_opportunities(
    stage: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """List commercial deals and opportunities owned by the authenticated broker."""
    stmt = select(DealTransaction).where(DealTransaction.broker_id == broker.id)
    if stage:
        stmt = stmt.where(DealTransaction.current_stage == stage.lower())
    res = await db.execute(stmt)
    deals = res.scalars().all()

    items: List[OpportunitySummaryDTO] = []
    for d in deals:
        lead_stmt = select(Lead).where(Lead.id == d.lead_id)
        lead_res = await db.execute(lead_stmt)
        lead = lead_res.scalars().first()

        items.append(
            OpportunitySummaryDTO(
                id=str(d.id),
                lead_id=str(d.lead_id),
                lead_name=lead.name if lead else None,
                lead_phone=lead.phone if lead else "",
                property_id=str(d.property_id) if d.property_id else None,
                deal_name=d.deal_name,
                agreed_price=float(d.agreed_price),
                currency=d.currency,
                current_stage=d.current_stage,
                commission_percentage=float(d.commission_percentage),
                estimated_commission_amount=float(d.estimated_commission_amount),
                risk_level=d.risk_level,
                closing_probability_pct=float(d.closing_probability_pct),
                is_stalled=False,
                days_in_stage=0,
                created_at=d.created_at,
                updated_at=d.updated_at
            )
        )
    return items


@router.post("/opportunities", response_model=OpportunitySummaryDTO, status_code=status.HTTP_201_CREATED)
async def create_opportunity(
    payload: OpportunityCreateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Create a new commercial deal linked to a lead and property."""
    lead_uuid = uuid.UUID(payload.lead_id)
    prop_uuid = uuid.UUID(payload.property_id)

    # Verify lead exists & belongs to broker
    lead_res = await db.execute(
        select(Lead).where(Lead.id == lead_uuid, Lead.broker_id == broker.id, Lead.deleted_at.is_(None))
    )
    lead = lead_res.scalars().first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found or unauthorized")

    comm_amount = (payload.agreed_price * payload.commission_percentage) / 100.0

    deal = DealTransaction(
        broker_id=broker.id,
        lead_id=lead_uuid,
        property_id=prop_uuid,
        deal_name=payload.deal_name,
        agreed_price=payload.agreed_price,
        currency=payload.currency,
        current_stage=payload.current_stage.lower(),
        commission_percentage=payload.commission_percentage,
        estimated_commission_amount=comm_amount
    )
    db.add(deal)
    await db.commit()
    await db.refresh(deal)

    return OpportunitySummaryDTO(
        id=str(deal.id),
        lead_id=str(deal.lead_id),
        lead_name=lead.name,
        lead_phone=lead.phone,
        property_id=str(deal.property_id),
        deal_name=deal.deal_name,
        agreed_price=float(deal.agreed_price),
        currency=deal.currency,
        current_stage=deal.current_stage,
        commission_percentage=float(deal.commission_percentage),
        estimated_commission_amount=float(deal.estimated_commission_amount),
        risk_level=deal.risk_level,
        closing_probability_pct=float(deal.closing_probability_pct),
        is_stalled=False,
        days_in_stage=0,
        created_at=deal.created_at,
        updated_at=deal.updated_at
    )


@router.patch("/opportunities/{opportunity_id}/stage")
async def update_opportunity_stage(
    opportunity_id: str,
    payload: OpportunityStageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Progress or update an opportunity's deal stage."""
    deal_uuid = uuid.UUID(opportunity_id)
    stmt = select(DealTransaction).where(DealTransaction.id == deal_uuid, DealTransaction.broker_id == broker.id)
    res = await db.execute(stmt)
    deal = res.scalars().first()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Opportunity not found")

    deal.current_stage = payload.current_stage.lower()
    await db.commit()
    await db.refresh(deal)
    return {"status": "success", "id": str(deal.id), "current_stage": deal.current_stage}


# ─────────────────────────────────────────────────────────────────────────────
# 5. Tasks Management
# ─────────────────────────────────────────────────────────────────────────────

def _is_task_overdue(status: str, due_at: Optional[datetime], now: datetime) -> bool:
    if status == "completed" or not due_at:
        return False
    tz_due = due_at.replace(tzinfo=timezone.utc) if due_at.tzinfo is None else due_at
    return tz_due < now


@router.get("/tasks", response_model=List[CRMTaskResponse])
async def list_crm_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority: Optional[str] = None,
    lead_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """List CRM tasks for the current broker with overdue evaluation."""
    stmt = select(Task).where(Task.broker_id == broker.id)
    if status_filter:
        stmt = stmt.where(Task.status == status_filter.lower())
    if priority:
        stmt = stmt.where(Task.priority == priority.lower())
    if lead_id:
        stmt = stmt.where(Task.lead_id == uuid.UUID(lead_id))

    stmt = stmt.order_by(Task.due_at.asc().nullslast(), Task.created_at.desc())
    res = await db.execute(stmt)
    tasks = res.scalars().all()

    now = datetime.now(timezone.utc)
    return [
        CRMTaskResponse(
            id=str(t.id),
            organization_id=t.organization_id,
            broker_id=str(t.broker_id),
            lead_id=str(t.lead_id) if t.lead_id else None,
            assigned_broker_id=str(t.assigned_broker_id) if t.assigned_broker_id else None,
            title=t.title,
            description=t.description,
            due_at=t.due_at,
            status=t.status,
            priority=t.priority,
            is_overdue=_is_task_overdue(t.status, t.due_at, now),
            completed_at=t.completed_at,
            created_at=t.created_at,
            updated_at=t.updated_at
        )
        for t in tasks
    ]


@router.post("/tasks", response_model=CRMTaskResponse, status_code=status.HTTP_201_CREATED)
async def create_crm_task(
    payload: CRMTaskCreateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Create a new CRM task."""
    org_id = str(broker.organization_id or broker.id)
    lead_uuid = uuid.UUID(payload.lead_id) if payload.lead_id else None
    assigned_uuid = uuid.UUID(payload.assigned_broker_id) if payload.assigned_broker_id else broker.id

    task = Task(
        broker_id=broker.id,
        organization_id=org_id,
        lead_id=lead_uuid,
        assigned_broker_id=assigned_uuid,
        title=payload.title,
        description=payload.description,
        due_at=payload.due_at,
        status=payload.status,
        priority=payload.priority
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    now = datetime.now(timezone.utc)
    return CRMTaskResponse(
        id=str(task.id),
        organization_id=task.organization_id,
        broker_id=str(task.broker_id),
        lead_id=str(task.lead_id) if task.lead_id else None,
        assigned_broker_id=str(task.assigned_broker_id) if task.assigned_broker_id else None,
        title=task.title,
        description=task.description,
        due_at=task.due_at,
        status=task.status,
        priority=task.priority,
        is_overdue=_is_task_overdue(task.status, task.due_at, now),
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@router.patch("/tasks/{task_id}", response_model=CRMTaskResponse)
async def update_crm_task(
    task_id: str,
    payload: CRMTaskUpdateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Update task status, priority, due date, or complete a task."""
    stmt = select(Task).where(Task.id == task_id, Task.broker_id == broker.id)
    res = await db.execute(stmt)
    task = res.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if payload.title is not None:
        task.title = payload.title
    if payload.description is not None:
        task.description = payload.description
    if payload.due_at is not None:
        task.due_at = payload.due_at
    if payload.priority is not None:
        task.priority = payload.priority
    if payload.status is not None:
        task.status = payload.status
        if payload.status == "completed" and not task.completed_at:
            task.completed_at = datetime.now(timezone.utc)
        elif payload.status != "completed":
            task.completed_at = None

    await db.commit()
    await db.refresh(task)

    now = datetime.now(timezone.utc)
    return CRMTaskResponse(
        id=str(task.id),
        organization_id=task.organization_id,
        broker_id=str(task.broker_id),
        lead_id=str(task.lead_id) if task.lead_id else None,
        assigned_broker_id=str(task.assigned_broker_id) if task.assigned_broker_id else None,
        title=task.title,
        description=task.description,
        due_at=task.due_at,
        status=task.status,
        priority=task.priority,
        is_overdue=_is_task_overdue(task.status, task.due_at, now),
        completed_at=task.completed_at,
        created_at=task.created_at,
        updated_at=task.updated_at
    )


@router.delete("/tasks/{task_id}")
async def delete_crm_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Delete a task owned by the current broker."""
    stmt = select(Task).where(Task.id == task_id, Task.broker_id == broker.id)
    res = await db.execute(stmt)
    task = res.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    await db.delete(task)
    await db.commit()
    return {"status": "success", "message": "Task deleted"}


# ─────────────────────────────────────────────────────────────────────────────
# 6. Activities & Notes
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/activities", response_model=List[CRMActivityResponse])
async def list_crm_activities(
    lead_id: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """List chronological activity records."""
    org_id = str(broker.organization_id or broker.id)
    stmt = select(Activity).where(
        or_(Activity.actor_id == broker.id, Activity.organization_id == org_id)
    )
    if lead_id:
        stmt = stmt.where(Activity.lead_id == uuid.UUID(lead_id))

    stmt = stmt.order_by(Activity.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    activities = res.scalars().all()

    return [
        CRMActivityResponse(
            id=str(a.id),
            organization_id=a.organization_id,
            lead_id=str(a.lead_id) if a.lead_id else None,
            actor_id=str(a.actor_id) if a.actor_id else None,
            actor_type="HUMAN" if a.actor_id else "SYSTEM",
            activity_type=a.activity_type,
            title=a.title,
            description=a.description,
            activity_data=a.activity_data or {},
            created_at=a.created_at
        )
        for a in activities
    ]


@router.post("/activities", response_model=CRMActivityResponse, status_code=status.HTTP_201_CREATED)
async def log_crm_activity(
    payload: CRMActivityCreateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Log an interaction activity (call, email, note, site visit, meeting)."""
    org_id = str(broker.organization_id or broker.id)
    lead_uuid = uuid.UUID(payload.lead_id) if payload.lead_id else None

    activity = Activity(
        organization_id=org_id,
        actor_id=broker.id,
        lead_id=lead_uuid,
        activity_type=payload.activity_type,
        title=payload.title,
        description=payload.description,
        activity_data=payload.activity_data
    )
    db.add(activity)
    await db.commit()
    await db.refresh(activity)

    return CRMActivityResponse(
        id=str(activity.id),
        organization_id=activity.organization_id,
        lead_id=str(activity.lead_id) if activity.lead_id else None,
        actor_id=str(activity.actor_id) if activity.actor_id else None,
        actor_type=payload.actor_type,
        activity_type=activity.activity_type,
        title=activity.title,
        description=activity.description,
        activity_data=activity.activity_data or {},
        created_at=activity.created_at
    )


@router.get("/notes", response_model=List[CRMNoteResponse])
async def list_crm_notes(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """List notes for a specific lead."""
    lead_uuid = uuid.UUID(lead_id)
    stmt = select(LeadNote).where(
        LeadNote.lead_id == lead_uuid,
        LeadNote.broker_id == broker.id
    ).order_by(LeadNote.created_at.desc())
    res = await db.execute(stmt)
    notes = res.scalars().all()

    return [
        CRMNoteResponse(
            id=str(n.id),
            lead_id=str(n.lead_id),
            broker_id=str(n.broker_id),
            content=n.content,
            visibility="ORGANIZATION",
            is_ai_generated=False,
            created_at=n.created_at
        )
        for n in notes
    ]


@router.post("/notes", response_model=CRMNoteResponse, status_code=status.HTTP_201_CREATED)
async def create_crm_note(
    payload: CRMNoteCreateRequest,
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Create a rich text internal note attached to a lead."""
    lead_uuid = uuid.UUID(payload.lead_id)
    lead_res = await db.execute(
        select(Lead).where(Lead.id == lead_uuid, Lead.broker_id == broker.id, Lead.deleted_at.is_(None))
    )
    lead = lead_res.scalars().first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    note = LeadNote(
        lead_id=lead_uuid,
        broker_id=broker.id,
        content=payload.content.strip()
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)

    return CRMNoteResponse(
        id=str(note.id),
        lead_id=str(note.lead_id),
        broker_id=str(note.broker_id),
        content=note.content,
        visibility=payload.visibility,
        is_ai_generated=payload.is_ai_generated,
        created_at=note.created_at
    )


# ─────────────────────────────────────────────────────────────────────────────
# 7. Universal Search
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/search", response_model=CRMSearchResponse)
async def universal_crm_search(
    q: str = Query(..., min_length=1, description="Search term for names, phone, email, properties, tasks"),
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Search universally across Customers, Leads, Opportunities, Properties, and Tasks."""
    search_service = CRMSearchService(db)
    org_id = str(broker.organization_id or broker.id)
    return await search_service.search(q, broker.id, org_id, limit)


# ─────────────────────────────────────────────────────────────────────────────
# 8. CRM Operations Dashboard Metrics
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=CRMDashboardMetricsResponse)
async def get_crm_dashboard_metrics(
    db: AsyncSession = Depends(get_db),
    broker: Broker = Depends(get_current_broker)
):
    """Provides operational metrics: My Work, Today's Appointments, Pipeline, Revenue, SLA Risks."""
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999999)

    def _ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

    # Leads counts
    leads_res = await db.execute(
        select(Lead).where(Lead.broker_id == broker.id, Lead.deleted_at.is_(None))
    )
    all_leads = leads_res.scalars().all()
    my_open_leads = sum(1 for l in all_leads if l.status not in ("converted", "lost"))
    new_today = sum(1 for l in all_leads if _ensure_utc(l.created_at) and _ensure_utc(l.created_at) >= today_start)

    # Deals & Pipeline valuation
    deals_res = await db.execute(
        select(DealTransaction).where(DealTransaction.broker_id == broker.id)
    )
    all_deals = deals_res.scalars().all()
    active_opps = sum(1 for d in all_deals if d.current_stage not in ("won", "lost"))
    pipe_val = sum(d.agreed_price for d in all_deals if d.current_stage not in ("won", "lost"))
    recorded_rev = sum(d.agreed_price for d in all_deals if d.current_stage == "won")

    # Tasks counts
    tasks_res = await db.execute(
        select(Task).where(Task.broker_id == broker.id)
    )
    all_tasks = tasks_res.scalars().all()
    overdue_tasks = sum(1 for t in all_tasks if t.status != "completed" and _ensure_utc(t.due_at) and _ensure_utc(t.due_at) < now)

    # Appointments counts
    mtg_res = await db.execute(
        select(SchedulingMeeting).where(SchedulingMeeting.broker_id == broker.id)
    )
    all_mtgs = mtg_res.scalars().all()
    todays_appts = sum(1 for m in all_mtgs if _ensure_utc(m.start_utc) and today_start <= _ensure_utc(m.start_utc) <= today_end)
    upcoming_site_visits = sum(
        1 for m in all_mtgs
        if m.meeting_type in ("PROPERTY_VIEWING", "SITE_VISIT") and _ensure_utc(m.start_utc) and _ensure_utc(m.start_utc) >= now and m.status == "CONFIRMED"
    )

    # Revenue Opportunities count
    rev_op_res = await db.execute(
        select(func.count(RevenueOpportunity.id)).where(
            RevenueOpportunity.broker_id == broker.id,
            RevenueOpportunity.status == "OPEN"
        )
    )
    rev_op_count = rev_op_res.scalar() or 0

    return CRMDashboardMetricsResponse(
        my_open_leads=my_open_leads,
        new_leads_today=new_today,
        sla_risks_count=0,
        todays_appointments_count=todays_appts,
        upcoming_site_visits_count=upcoming_site_visits,
        active_opportunities_count=active_opps,
        pipeline_total_value=pipe_val,
        pipeline_currency="AED",
        recorded_revenue_total=recorded_rev,
        overdue_tasks_count=overdue_tasks,
        revenue_opportunities_count=rev_op_count
    )
