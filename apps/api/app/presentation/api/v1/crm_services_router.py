"""
Enterprise CRM Services REST API Router
--------------------------------------
Versioned endpoints under /api/v1/crm/services exposing:
  - Lead CRUD with tenant isolation & event emission
  - Task management
  - Meeting booking
  - Contact management
  - Notification management
  - Audit log retrieval
  - RBAC role assignment

All endpoints are:
  - Tenant-scoped (organization_id from authenticated session)
  - RBAC-enforced via RBACPermissionEvaluator
  - Audit-logged via AuditLogService
  - Event-emitting via DomainEventBus
"""
import uuid
import hashlib
import secrets
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, and_
from sqlalchemy.orm import selectinload

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.models.lead import Lead
from app.models.crm_models import (
    Task, Meeting, Contact, Activity,
    Notification, ApiKey, CustomField,
    PipelineStage, LeadNote, LeadTag, LeadTagAssignment
)
from app.models.audit_log import AuditLog
from app.models.organization import RoleModel, PermissionModel, OrganizationMember
from app.services.rbac_service import RBACPermissionEvaluator
from app.services.audit_service import AuditLogService, NotificationService
from app.infrastructure.events.event_bus import event_bus, DomainEvent

router = APIRouter(prefix="/crm/services", tags=["CRM Services"])


# ─────────────────────── Schemas ───────────────────────

class PaginatedResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[Any]


class LeadCreateRequest(BaseModel):
    phone: str = Field(..., min_length=7, max_length=20)
    name: Optional[str] = Field(None, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    source: Optional[str] = Field("manual", pattern="^(manual|whatsapp_forward|facebook|google)$")
    budget_min: Optional[int] = Field(None, ge=0)
    budget_max: Optional[int] = Field(None, ge=0)
    property_type: Optional[str] = None
    preferred_locations: Optional[List[str]] = Field(default_factory=list)


class LeadResponse(BaseModel):
    id: Any
    phone: Optional[str] = None
    name: Optional[str] = None
    email: Optional[str] = None
    source: Optional[str] = None
    score: Optional[str] = None
    status: Optional[str] = None
    pipeline_stage: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    created_at: Optional[datetime] = None
    class Config:
        from_attributes = True


class TaskCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    priority: Optional[str] = Field("normal", pattern="^(low|normal|high|urgent)$")
    lead_id: Optional[str] = None


class TaskUpdateRequest(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    status: Optional[str] = Field(None, pattern="^(pending|in_progress|completed|cancelled)$")
    priority: Optional[str] = Field(None, pattern="^(low|normal|high|urgent)$")
    lead_id: Optional[str] = None


class TaskResponse(BaseModel):
    id: Any
    broker_id: Optional[Any] = None
    lead_id: Optional[Any] = None
    title: str
    description: Optional[str] = None
    status: str
    priority: str
    due_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    lead: Optional[LeadResponse] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    class Config:
        from_attributes = True


class MeetingCreateRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    meeting_type: str = Field("site_visit", pattern="^(site_visit|call|video_call|office_meeting)$")
    scheduled_at: datetime
    duration_minutes: int = Field(60, ge=15, le=480)
    location: Optional[str] = None
    notes: Optional[str] = None
    lead_id: Optional[str] = None
    meeting_url: Optional[str] = None


class MeetingResponse(BaseModel):
    id: str
    title: str
    meeting_type: str
    scheduled_at: datetime
    duration_minutes: int
    location: Optional[str]
    status: str
    created_at: datetime
    class Config:
        from_attributes = True


class ContactCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    email: Optional[str] = Field(None, max_length=255)
    phone: Optional[str] = Field(None, max_length=20)
    contact_type: str = Field("vendor", pattern="^(vendor|consultant|developer|legal|other)$")
    company: Optional[str] = None
    position: Optional[str] = None
    notes: Optional[str] = None


class ContactResponse(BaseModel):
    id: str
    name: str
    email: Optional[str]
    phone: Optional[str]
    contact_type: str
    company: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True


class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    scopes: List[str] = Field(default_factory=lambda: ["leads:read"])
    expires_in_days: Optional[int] = Field(None, ge=1, le=365)


class ApiKeyCreatedResponse(BaseModel):
    id: str
    name: str
    key: str          # Only returned once — the raw key
    key_prefix: str
    scopes: List[str]
    expires_at: Optional[datetime]


class NotificationResponse(BaseModel):
    id: str
    category: str
    title: str
    body: Optional[str]
    action_url: Optional[str]
    is_read: bool
    created_at: datetime
    class Config:
        from_attributes = True


class AuditLogResponse(BaseModel):
    id: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    ip_address: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True


class StageResponse(BaseModel):
    id: Any
    broker_id: Any
    name: str
    order_index: int
    color: str
    is_default: str
    created_at: datetime
    class Config:
        from_attributes = True


class StageUpdateRequest(BaseModel):
    stage_name: str = Field(..., min_length=1, max_length=50)


class TagCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=50)
    color: Optional[str] = Field("#3B82F6", max_length=7)


class TagResponse(BaseModel):
    id: Any
    broker_id: Any
    name: str
    color: str
    created_at: datetime
    class Config:
        from_attributes = True


class TagAssignRequest(BaseModel):
    tag_id: str


class NoteCreateRequest(BaseModel):
    content: str = Field(..., min_length=1)
    color_tag: Optional[str] = "blue"


class NoteResponse(BaseModel):
    id: Any
    lead_id: Any
    broker_id: Any
    content: str
    created_at: datetime
    class Config:
        from_attributes = True


# ─────────────────────── Lead Endpoints ───────────────────────

@router.post("/leads", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
async def create_lead(
    req: LeadCreateRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Create a new CRM lead with tenant isolation, RBAC check, audit log, and domain event."""
    await RBACPermissionEvaluator.enforce_permission(db, current_broker, "leads:create")

    lead = Lead(
        broker_id=current_broker.id,
        phone=req.phone,
        name=req.name,
        source=req.source or "manual",
        budget_min=req.budget_min,
        budget_max=req.budget_max,
        preferred_locations=req.preferred_locations or []
    )
    db.add(lead)
    await db.flush()

    await AuditLogService.record(
        db=db,
        action="lead.create",
        resource_type="lead",
        actor_id=current_broker.id,
        resource_id=str(lead.id),
        changes={"name": req.name, "phone": req.phone},
        ip_address=request.client.host if request.client else None
    )

    await event_bus.publish(DomainEvent(
        event_type="LeadCreated",
        organization_id=str(getattr(current_broker, "organization_id", "global")),
        user_id=str(current_broker.id),
        payload={"lead_id": str(lead.id), "name": req.name, "phone": req.phone}
    ))

    await db.commit()
    await db.refresh(lead)
    return lead


@router.get("/leads", response_model=List[LeadResponse])
async def list_leads(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    score: Optional[str] = Query(None),
    pipeline_stage: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """List leads for the authenticated broker with optional filtering and pagination."""
    await RBACPermissionEvaluator.enforce_permission(db, current_broker, "leads:read")

    stmt = select(Lead).where(Lead.broker_id == current_broker.id, Lead.deleted_at.is_(None))
    if score:
        stmt = stmt.where(Lead.score == score)
    if pipeline_stage:
        stmt = stmt.where(Lead.pipeline_stage == pipeline_stage)
    stmt = stmt.order_by(Lead.created_at.desc()).limit(limit).offset(offset)

    res = await db.execute(stmt)
    return list(res.scalars().all())


# ─────────────────────── Task Endpoints ───────────────────────

def _to_uuid(val: Any) -> Optional[uuid.UUID]:
    if val is None:
        return None
    if isinstance(val, uuid.UUID):
        return val
    try:
        return uuid.UUID(str(val))
    except (ValueError, TypeError):
        return None


@router.post("/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    req: TaskCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Create a follow-up task with event emission."""
    await RBACPermissionEvaluator.enforce_permission(db, current_broker, "leads:create")

    broker_uuid = _to_uuid(current_broker.id)
    lead_uuid = _to_uuid(req.lead_id) if req.lead_id else None

    task = Task(
        broker_id=broker_uuid,
        lead_id=lead_uuid,
        title=req.title.strip(),
        description=req.description.strip() if req.description else None,
        due_at=req.due_at,
        priority=req.priority or "normal",
        status="pending"
    )
    db.add(task)
    await db.flush()

    await event_bus.publish(DomainEvent(
        event_type="TaskCreated",
        user_id=str(current_broker.id),
        payload={"task_id": str(task.id), "title": req.title, "due_at": str(req.due_at)}
    ))

    await db.commit()
    
    stmt = select(Task).options(selectinload(Task.lead)).where(Task.id == task.id)
    res = await db.execute(stmt)
    result_task = res.scalars().first()
    if result_task and result_task.lead_id and not result_task.lead:
        lead_res = await db.execute(select(Lead).where(Lead.id == result_task.lead_id))
        result_task.lead = lead_res.scalars().first()
    return result_task


@router.get("/tasks", response_model=List[TaskResponse])
async def list_tasks(
    status_filter: Optional[str] = Query(None, alias="status"),
    lead_id: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """List tasks for the authenticated broker."""
    await RBACPermissionEvaluator.enforce_permission(db, current_broker, "leads:read")
    broker_uuid = _to_uuid(current_broker.id)
    stmt = select(Task).options(selectinload(Task.lead)).where(Task.broker_id == broker_uuid)
    if status_filter:
        stmt = stmt.where(Task.status == status_filter)
    if lead_id:
        l_uuid = _to_uuid(lead_id)
        if l_uuid:
            stmt = stmt.where(Task.lead_id == l_uuid)
    stmt = stmt.order_by(Task.due_at.asc().nulls_last(), Task.created_at.desc()).limit(limit).offset(offset)
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: str,
    req: TaskUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Update task details, due date, priority, or status."""
    await RBACPermissionEvaluator.enforce_permission(db, current_broker, "leads:update")
    broker_uuid = _to_uuid(current_broker.id)
    stmt = select(Task).options(selectinload(Task.lead)).where(Task.id == task_id, Task.broker_id == broker_uuid)
    res = await db.execute(stmt)
    task = res.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    if req.title is not None:
        task.title = req.title.strip()
    if req.description is not None:
        task.description = req.description.strip() if req.description else None
    if req.due_at is not None:
        task.due_at = req.due_at
    if req.priority is not None:
        task.priority = req.priority
    if req.lead_id is not None:
        task.lead_id = _to_uuid(req.lead_id) if req.lead_id else None
    if req.status is not None:
        task.status = req.status
        if req.status == "completed":
            task.completed_at = datetime.now(timezone.utc)
        elif req.status == "pending":
            task.completed_at = None

    await db.commit()
    
    stmt_reload = select(Task).options(selectinload(Task.lead)).where(Task.id == task_id)
    res_reload = await db.execute(stmt_reload)
    return res_reload.scalars().first()


@router.patch("/tasks/{task_id}/complete", response_model=TaskResponse)
async def complete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Mark a task as completed and emit TaskCompleted event."""
    await RBACPermissionEvaluator.enforce_permission(db, current_broker, "leads:update")
    broker_uuid = _to_uuid(current_broker.id)
    stmt = select(Task).options(selectinload(Task.lead)).where(Task.id == task_id, Task.broker_id == broker_uuid)
    res = await db.execute(stmt)
    task = res.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = "completed"
    task.completed_at = datetime.now(timezone.utc)
    await db.flush()

    await event_bus.publish(DomainEvent(
        event_type="TaskCompleted",
        user_id=str(current_broker.id),
        payload={"task_id": task_id, "title": task.title}
    ))

    await db.commit()
    
    stmt_reload = select(Task).options(selectinload(Task.lead)).where(Task.id == task_id)
    res_reload = await db.execute(stmt_reload)
    return res_reload.scalars().first()


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Delete a task owned by the authenticated broker."""
    await RBACPermissionEvaluator.enforce_permission(db, current_broker, "leads:delete")
    broker_uuid = _to_uuid(current_broker.id)
    stmt = select(Task).where(Task.id == task_id, Task.broker_id == broker_uuid)
    res = await db.execute(stmt)
    task = res.scalars().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    await db.delete(task)
    await db.commit()
    return {"status": "success", "id": task_id, "message": "Task deleted successfully"}


# ─────────────────────── Meeting Endpoints ───────────────────────

@router.post("/meetings", response_model=MeetingResponse, status_code=status.HTTP_201_CREATED)
async def book_meeting(
    req: MeetingCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Book a client meeting / site visit with MeetingBooked event emission."""
    meeting = Meeting(
        broker_id=str(current_broker.id),
        lead_id=req.lead_id,
        title=req.title,
        meeting_type=req.meeting_type,
        scheduled_at=req.scheduled_at,
        duration_minutes=req.duration_minutes,
        location=req.location,
        notes=req.notes,
        meeting_url=req.meeting_url
    )
    db.add(meeting)
    await db.flush()

    await event_bus.publish(DomainEvent(
        event_type="MeetingBooked",
        user_id=str(current_broker.id),
        payload={"meeting_id": str(meeting.id), "title": req.title, "scheduled_at": str(req.scheduled_at)}
    ))

    await db.commit()
    await db.refresh(meeting)
    return meeting


@router.get("/meetings", response_model=List[MeetingResponse])
async def list_meetings(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    stmt = select(Meeting).where(Meeting.broker_id == str(current_broker.id)).order_by(Meeting.scheduled_at.desc()).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())


# ─────────────────────── Contact Endpoints ───────────────────────

@router.post("/contacts", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_contact(
    req: ContactCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Create a vendor/consultant contact in the CRM."""
    contact = Contact(
        broker_id=str(current_broker.id),
        name=req.name,
        email=req.email,
        phone=req.phone,
        contact_type=req.contact_type,
        company=req.company,
        position=req.position,
        notes=req.notes
    )
    db.add(contact)
    await db.commit()
    await db.refresh(contact)
    return contact


@router.get("/contacts", response_model=List[ContactResponse])
async def list_contacts(
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    stmt = select(Contact).where(
        Contact.broker_id == str(current_broker.id),
        Contact.deleted_at.is_(None)
    ).order_by(Contact.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())


# ─────────────────────── Notification Endpoints ───────────────────────

@router.get("/notifications", response_model=List[NotificationResponse])
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """List broker notifications with optional unread filter."""
    stmt = select(Notification).where(Notification.broker_id == str(current_broker.id))
    if unread_only:
        stmt = stmt.where(Notification.is_read == False)
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.patch("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Mark a notification as read."""
    await NotificationService.mark_read(db, notification_id, str(current_broker.id))
    await db.commit()
    return {"status": "ok"}


# ─────────────────────── API Key Endpoints ───────────────────────

@router.post("/api-keys", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    req: ApiKeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """
    Generate a new machine-to-machine API Key.
    The raw key is returned ONCE — it is stored as a SHA-256 hash only.
    """
    await RBACPermissionEvaluator.enforce_permission(db, current_broker, "organization:manage")

    raw_key = f"bl_{secrets.token_urlsafe(32)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:10]
    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_in_days)

    api_key = ApiKey(
        organization_id=str(getattr(current_broker, "organization_id", "org-default")),
        broker_id=str(current_broker.id),
        name=req.name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        scopes=req.scopes,
        expires_at=expires_at
    )
    db.add(api_key)
    await db.commit()
    await db.refresh(api_key)

    return ApiKeyCreatedResponse(
        id=str(api_key.id),
        name=api_key.name,
        key=raw_key,
        key_prefix=key_prefix,
        scopes=req.scopes,
        expires_at=expires_at
    )


# ─────────────────────── Audit Log Endpoints ───────────────────────

@router.get("/audit-logs", response_model=List[AuditLogResponse])
async def list_audit_logs(
    resource_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """List audit logs for the current broker's organization (admin/owner only)."""
    await RBACPermissionEvaluator.enforce_permission(db, current_broker, "audit:view")

    stmt = select(AuditLog).where(AuditLog.actor_id == current_broker.id)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    stmt = stmt.order_by(AuditLog.created_at.desc()).limit(limit).offset(offset)

    res = await db.execute(stmt)
    return list(res.scalars().all())


# ─────────────────────── Pipeline Stages Endpoints ───────────────────────

DEFAULT_STAGES = [
    {"name": "New", "order_index": 0, "color": "#0D9488", "is_default": "true"},
    {"name": "Contacted", "order_index": 1, "color": "#3B82F6", "is_default": "true"},
    {"name": "Viewing Scheduled", "order_index": 2, "color": "#F59E0B", "is_default": "true"},
    {"name": "Negotiating", "order_index": 3, "color": "#EF4444", "is_default": "true"},
    {"name": "Closed Won", "order_index": 4, "color": "#10B981", "is_default": "true"},
    {"name": "Closed Lost", "order_index": 5, "color": "#6B7280", "is_default": "true"},
]

@router.get("/stages", response_model=List[StageResponse])
async def get_pipeline_stages(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Retrieve or initialize default pipeline stages for the broker."""
    broker_uuid = _to_uuid(current_broker.id)
    stmt = select(PipelineStage).where(PipelineStage.broker_id == broker_uuid).order_by(PipelineStage.order_index)
    res = await db.execute(stmt)
    stages = list(res.scalars().all())

    if not stages:
        for s_def in DEFAULT_STAGES:
            stage = PipelineStage(
                broker_id=broker_uuid,
                name=s_def["name"],
                order_index=s_def["order_index"],
                color=s_def["color"],
                is_default=s_def["is_default"]
            )
            db.add(stage)
        await db.commit()
        stmt2 = select(PipelineStage).where(PipelineStage.broker_id == broker_uuid).order_by(PipelineStage.order_index)
        res2 = await db.execute(stmt2)
        stages = list(res2.scalars().all())

    return stages


@router.patch("/leads/{lead_id}/stage")
async def update_lead_stage_endpoint(
    lead_id: str,
    req: StageUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Update pipeline stage for a lead with broker ownership enforcement."""
    broker_uuid = _to_uuid(current_broker.id)
    lead_uuid = _to_uuid(lead_id)
    if not lead_uuid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    stmt = select(Lead).where(Lead.id == lead_uuid, Lead.broker_id == broker_uuid)
    res = await db.execute(stmt)
    lead = res.scalars().first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    lead.pipeline_stage = req.stage_name
    normalized_stage = req.stage_name.lower().replace(" ", "_")
    if "closed_won" in normalized_stage or "closed won" in req.stage_name.lower():
        lead.status = "converted"
    elif "closed_lost" in normalized_stage or "closed lost" in req.stage_name.lower():
        lead.status = "lost"

    await db.commit()
    return {"message": "Stage updated successfully", "stage_name": lead.pipeline_stage, "status": lead.status}


# ─────────────────────── Tags Endpoints ───────────────────────

@router.get("/tags", response_model=List[TagResponse])
async def list_tags(
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """List lead taxonomy tags for the authenticated broker."""
    broker_uuid = _to_uuid(current_broker.id)
    stmt = select(LeadTag).where(LeadTag.broker_id == broker_uuid).order_by(LeadTag.name)
    res = await db.execute(stmt)
    tags = list(res.scalars().all())

    if not tags:
        # Seed initial standard tags if none exist
        default_tags = [
            {"name": "High Priority", "color": "#EF4444"},
            {"name": "Verified Buyer", "color": "#10B981"},
            {"name": "NRI Investor", "color": "#3B82F6"},
        ]
        for dt in default_tags:
            tag = LeadTag(broker_id=broker_uuid, name=dt["name"], color=dt["color"])
            db.add(tag)
        await db.commit()
        stmt2 = select(LeadTag).where(LeadTag.broker_id == broker_uuid).order_by(LeadTag.name)
        res2 = await db.execute(stmt2)
        tags = list(res2.scalars().all())

    return tags


@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
async def create_tag(
    req: TagCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Create a new tag or return existing."""
    broker_uuid = _to_uuid(current_broker.id)
    stmt = select(LeadTag).where(LeadTag.broker_id == broker_uuid, LeadTag.name == req.name.strip())
    res = await db.execute(stmt)
    existing = res.scalars().first()
    if existing:
        return existing

    tag = LeadTag(
        broker_id=broker_uuid,
        name=req.name.strip(),
        color=req.color or "#3B82F6"
    )
    db.add(tag)
    await db.commit()
    await db.refresh(tag)
    return tag


@router.post("/leads/{lead_id}/tags/{tag_id}")
async def assign_tag_to_lead(
    lead_id: str,
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Assign a tag to a lead."""
    broker_uuid = _to_uuid(current_broker.id)
    lead_uuid = _to_uuid(lead_id)
    if not lead_uuid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    lead_res = await db.execute(select(Lead).where(Lead.id == lead_uuid, Lead.broker_id == broker_uuid))
    lead = lead_res.scalars().first()
    tag_res = await db.execute(select(LeadTag).where(LeadTag.id == tag_id, LeadTag.broker_id == broker_uuid))
    tag = tag_res.scalars().first()

    if not lead or not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead or Tag not found")

    assign_res = await db.execute(
        select(LeadTagAssignment).where(LeadTagAssignment.lead_id == lead_uuid, LeadTagAssignment.tag_id == tag_id)
    )
    assignment = assign_res.scalars().first()
    if not assignment:
        assignment = LeadTagAssignment(lead_id=lead_uuid, tag_id=tag_id)
        db.add(assignment)
        await db.commit()

    return {"status": "success", "message": "Tag assigned to lead"}


@router.post("/leads/{lead_id}/tags")
async def assign_tag_to_lead_body(
    lead_id: str,
    req: TagAssignRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Assign a tag to a lead using request body."""
    return await assign_tag_to_lead(lead_id, req.tag_id, db, current_broker)


@router.delete("/leads/{lead_id}/tags/{tag_id}")
async def remove_tag_from_lead(
    lead_id: str,
    tag_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Remove tag assignment from a lead."""
    broker_uuid = _to_uuid(current_broker.id)
    lead_uuid = _to_uuid(lead_id)
    if not lead_uuid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    lead_res = await db.execute(select(Lead).where(Lead.id == lead_uuid, Lead.broker_id == broker_uuid))
    lead = lead_res.scalars().first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    assign_res = await db.execute(
        select(LeadTagAssignment).where(LeadTagAssignment.lead_id == lead_uuid, LeadTagAssignment.tag_id == tag_id)
    )
    assignment = assign_res.scalars().first()
    if assignment:
        await db.delete(assignment)
        await db.commit()

    return {"status": "success", "message": "Tag removed from lead"}


# ─────────────────────── Notes Endpoints ───────────────────────

@router.get("/leads/{lead_id}/notes", response_model=List[NoteResponse])
async def list_lead_notes(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """List notes for a lead."""
    broker_uuid = _to_uuid(current_broker.id)
    lead_uuid = _to_uuid(lead_id)
    if not lead_uuid:
        return []

    stmt = select(LeadNote).where(
        LeadNote.lead_id == lead_uuid,
        LeadNote.broker_id == broker_uuid
    ).order_by(LeadNote.created_at.desc())
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.post("/leads/{lead_id}/notes", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
async def create_lead_note(
    lead_id: str,
    req: NoteCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Add a rich text note to a lead."""
    broker_uuid = _to_uuid(current_broker.id)
    lead_uuid = _to_uuid(lead_id)
    if not lead_uuid:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    lead_res = await db.execute(select(Lead).where(Lead.id == lead_uuid, Lead.broker_id == broker_uuid))
    lead = lead_res.scalars().first()
    if not lead:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    note = LeadNote(
        lead_id=lead_uuid,
        broker_id=broker_uuid,
        content=req.content.strip()
    )
    db.add(note)
    await db.commit()
    await db.refresh(note)
    return note


@router.delete("/notes/{note_id}")
async def delete_lead_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    current_broker: Broker = Depends(get_current_broker)
):
    """Delete a note owned by the authenticated broker."""
    broker_uuid = _to_uuid(current_broker.id)
    stmt = select(LeadNote).where(LeadNote.id == note_id, LeadNote.broker_id == broker_uuid)
    res = await db.execute(stmt)
    note = res.scalars().first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")

    await db.delete(note)
    await db.commit()
    return {"status": "success", "message": "Note deleted successfully"}


# ─────────────────────── Direct Aliases Routers ───────────────────────
tasks_router = APIRouter(prefix="/tasks", tags=["Tasks"])
tasks_router.add_api_route("", create_task, methods=["POST"], response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
tasks_router.add_api_route("", list_tasks, methods=["GET"], response_model=List[TaskResponse])
tasks_router.add_api_route("/{task_id}", update_task, methods=["PATCH"], response_model=TaskResponse)
tasks_router.add_api_route("/{task_id}/complete", complete_task, methods=["PATCH"], response_model=TaskResponse)
tasks_router.add_api_route("/{task_id}", delete_task, methods=["DELETE"])

tags_router = APIRouter(prefix="/tags", tags=["Tags"])
tags_router.add_api_route("", list_tags, methods=["GET"], response_model=List[TagResponse])
tags_router.add_api_route("", create_tag, methods=["POST"], response_model=TagResponse, status_code=status.HTTP_201_CREATED)

notes_router = APIRouter(prefix="/notes", tags=["Notes"])
notes_router.add_api_route("/{note_id}", delete_lead_note, methods=["DELETE"])

stages_router = APIRouter(prefix="/stages", tags=["Stages"])
stages_router.add_api_route("", get_pipeline_stages, methods=["GET"], response_model=List[StageResponse])
