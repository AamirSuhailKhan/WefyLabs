import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db, get_current_broker
from app.models.broker import Broker
from app.infrastructure.persistence.sqlalchemy_lead_repository import SQLAlchemyLeadRepository
from app.core.application.leads.use_cases import LeadUseCases, CreateLeadCommand, QualifyLeadCommand
from app.core.domain.leads.entities import PipelineStageEnum, LeadScoreCategory

router = APIRouter(prefix="/clean-leads", tags=["Clean Architecture Leads V1"])

def get_lead_use_cases(db: AsyncSession = Depends(get_db)) -> LeadUseCases:
    repo = SQLAlchemyLeadRepository(db)
    return LeadUseCases(repo)

@router.get("")
async def list_leads_endpoint(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    score: Optional[str] = Query(None),
    stage: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    use_cases: LeadUseCases = Depends(get_lead_use_cases),
    current_broker: Broker = Depends(get_current_broker)
):
    return await use_cases.list_leads(
        broker_id=current_broker.id,
        page=page,
        limit=limit,
        score=score,
        stage=stage,
        search=search
    )

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_lead_endpoint(
    phone: str,
    name: Optional[str] = "New Lead",
    source: str = "manual",
    country_code: str = "IN",
    use_cases: LeadUseCases = Depends(get_lead_use_cases),
    current_broker: Broker = Depends(get_current_broker)
):
    cmd = CreateLeadCommand(
        broker_id=current_broker.id,
        phone=phone,
        name=name,
        source=source,
        country_code=country_code
    )
    lead = await use_cases.create_lead(cmd)
    return {"status": "success", "lead_id": str(lead.id), "phone": lead.phone}

@router.patch("/{lead_id}/stage")
async def update_stage_endpoint(
    lead_id: uuid.UUID,
    stage: str,
    use_cases: LeadUseCases = Depends(get_lead_use_cases),
    current_broker: Broker = Depends(get_current_broker)
):
    stage_enum = PipelineStageEnum(stage.lower())
    lead = await use_cases.update_stage(lead_id, current_broker.id, stage_enum)
    return {"status": "success", "lead_id": str(lead.id), "pipeline_stage": lead.pipeline_stage.value}
