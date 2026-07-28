from typing import List, Optional
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.models import Broker, Lead, PipelineStage, LeadNote, LeadTag, LeadTagAssignment, Task
from app.routers.auth import get_current_broker

router = APIRouter(prefix="/crm", tags=["CRM Lite"])

# Standard Default Pipeline Stages
DEFAULT_STAGES = [
    {"name": "New", "order_index": 0, "color": "#6B7280", "is_default": "true"},
    {"name": "Contacted", "order_index": 1, "color": "#3B82F6", "is_default": "true"},
    {"name": "Viewing Scheduled", "order_index": 2, "color": "#EAB308", "is_default": "true"},
    {"name": "Negotiating", "order_index": 3, "color": "#F97316", "is_default": "true"},
    {"name": "Closed Won", "order_index": 4, "color": "#22C55E", "is_default": "true"},
    {"name": "Closed Lost", "order_index": 5, "color": "#EF4444", "is_default": "true"},
]

def ensure_default_stages(db: Session, broker_id: str):
    existing = db.query(PipelineStage).filter(PipelineStage.broker_id == broker_id).all()
    if not existing:
        for stage_def in DEFAULT_STAGES:
            stage = PipelineStage(
                broker_id=broker_id,
                name=stage_def["name"],
                order_index=stage_def["order_index"],
                color=stage_def["color"],
                is_default=stage_def["is_default"]
            )
            db.add(stage)
        db.commit()
        existing = db.query(PipelineStage).filter(PipelineStage.broker_id == broker_id).order_by(PipelineStage.order_index).all()
    return existing

# --- Pydantic Schemas ---
class StageResponse(BaseModel):
    id: str
    broker_id: str
    name: str
    order_index: int
    color: str
    is_default: str
    created_at: datetime

    class Config:
        from_attributes = True

class StageUpdate(BaseModel):
    stage_name: str

class NoteCreate(BaseModel):
    content: str

class NoteResponse(BaseModel):
    id: str
    lead_id: str
    broker_id: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True

class TagCreate(BaseModel):
    name: str
    color: Optional[str] = "#6B7280"

class TagResponse(BaseModel):
    id: str
    broker_id: str
    name: str
    color: str
    created_at: datetime

    class Config:
        from_attributes = True

class TaskCreate(BaseModel):
    lead_id: Optional[str] = None
    title: str
    due_at: datetime

class TaskStatusUpdate(BaseModel):
    status: str # pending | completed | cancelled

class TaskResponse(BaseModel):
    id: str
    broker_id: str
    lead_id: Optional[str] = None
    title: str
    due_at: datetime
    status: str
    reminder_sent: str
    created_at: datetime

    class Config:
        from_attributes = True


# --- Endpoints: Pipeline Stages ---
@router.get("/stages", response_model=List[StageResponse])
def get_pipeline_stages(
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    stages = ensure_default_stages(db, broker.id)
    return stages

@router.patch("/leads/{lead_id}/stage")
def update_lead_stage(
    lead_id: str,
    payload: StageUpdate,
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.broker_id == broker.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    lead.stage_name = payload.stage_name
    # Update stage_id if matching stage exists
    stage = db.query(PipelineStage).filter(PipelineStage.broker_id == broker.id, PipelineStage.name == payload.stage_name).first()
    if stage:
        lead.stage_id = stage.id
    
    db.commit()
    db.refresh(lead)
    return {"message": "Stage updated successfully", "stage_name": lead.stage_name}


# --- Endpoints: Notes ---
@router.get("/leads/{lead_id}/notes", response_model=List[NoteResponse])
def get_lead_notes(
    lead_id: str,
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    notes = db.query(LeadNote).filter(LeadNote.lead_id == lead_id, LeadNote.broker_id == broker.id).order_by(LeadNote.created_at.desc()).all()
    return notes

@router.post("/leads/{lead_id}/notes", response_model=NoteResponse)
def create_lead_note(
    lead_id: str,
    payload: NoteCreate,
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.broker_id == broker.id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    
    note = LeadNote(
        lead_id=lead_id,
        broker_id=broker.id,
        content=payload.content
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note

@router.delete("/notes/{note_id}")
def delete_lead_note(
    note_id: str,
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    note = db.query(LeadNote).filter(LeadNote.id == note_id, LeadNote.broker_id == broker.id).first()
    if not note:
        raise HTTPException(status_code=404, detail="Note not found")
    
    db.delete(note)
    db.commit()
    return {"message": "Note deleted successfully"}


# --- Endpoints: Tags ---
@router.get("/tags", response_model=List[TagResponse])
def get_tags(
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    tags = db.query(LeadTag).filter(LeadTag.broker_id == broker.id).order_by(LeadTag.name).all()
    return tags

@router.post("/tags", response_model=TagResponse)
def create_tag(
    payload: TagCreate,
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    existing = db.query(LeadTag).filter(LeadTag.broker_id == broker.id, LeadTag.name == payload.name).first()
    if existing:
        return existing
    
    tag = LeadTag(
        broker_id=broker.id,
        name=payload.name,
        color=payload.color or "#6B7280"
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag

@router.post("/leads/{lead_id}/tags/{tag_id}")
def assign_tag_to_lead(
    lead_id: str,
    tag_id: str,
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.broker_id == broker.id).first()
    tag = db.query(LeadTag).filter(LeadTag.id == tag_id, LeadTag.broker_id == broker.id).first()
    if not lead or not tag:
        raise HTTPException(status_code=404, detail="Lead or Tag not found")
    
    assignment = db.query(LeadTagAssignment).filter(LeadTagAssignment.lead_id == lead_id, LeadTagAssignment.tag_id == tag_id).first()
    if not assignment:
        assignment = LeadTagAssignment(lead_id=lead_id, tag_id=tag_id)
        db.add(assignment)
        db.commit()
    return {"message": "Tag assigned to lead"}

@router.delete("/leads/{lead_id}/tags/{tag_id}")
def remove_tag_from_lead(
    lead_id: str,
    tag_id: str,
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    assignment = db.query(LeadTagAssignment).filter(LeadTagAssignment.lead_id == lead_id, LeadTagAssignment.tag_id == tag_id).first()
    if assignment:
        db.delete(assignment)
        db.commit()
    return {"message": "Tag removed from lead"}


# --- Endpoints: Tasks / Reminders ---
@router.get("/tasks", response_model=List[TaskResponse])
def get_tasks(
    lead_id: Optional[str] = None,
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    query = db.query(Task).filter(Task.broker_id == broker.id)
    if lead_id:
        query = query.filter(Task.lead_id == lead_id)
    tasks = query.order_by(Task.due_at.asc()).all()
    return tasks

@router.post("/tasks", response_model=TaskResponse)
def create_task(
    payload: TaskCreate,
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    task = Task(
        broker_id=broker.id,
        lead_id=payload.lead_id,
        title=payload.title,
        due_at=payload.due_at,
        status="pending"
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task

@router.patch("/tasks/{task_id}", response_model=TaskResponse)
def update_task_status(
    task_id: str,
    payload: TaskStatusUpdate,
    broker: Broker = Depends(get_current_broker),
    db: Session = Depends(get_db)
):
    task = db.query(Task).filter(Task.id == task_id, Task.broker_id == broker.id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    task.status = payload.status
    db.commit()
    db.refresh(task)
    return task
