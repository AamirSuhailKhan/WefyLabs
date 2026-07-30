import uuid
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from app.core.domain.leads.entities import LeadEntity, LeadScoreCategory, PipelineStageEnum, LeadStatus, LeadScoreValueObject
from app.core.domain.leads.ports import ILeadRepository
from app.infrastructure.plugins.country_registry import CountryPluginRegistry

@dataclass
class CreateLeadCommand:
    broker_id: uuid.UUID
    phone: str
    name: Optional[str] = "New Lead"
    source: str = "manual"
    country_code: str = "IN"

@dataclass
class QualifyLeadCommand:
    lead_id: uuid.UUID
    broker_id: uuid.UUID
    score: LeadScoreCategory
    confidence: float
    reasoning: str
    extracted_data: Dict[str, Any]

class LeadUseCases:
    """Application CQRS Service Layer orchestrating Domain Entities & Adapters."""

    def __init__(self, repo: ILeadRepository):
        self._repo = repo

    async def create_lead(self, cmd: CreateLeadCommand) -> LeadEntity:
        existing = await self._repo.get_by_phone(cmd.phone, cmd.broker_id)
        if existing:
            return existing

        plugin = CountryPluginRegistry.get_plugin(cmd.country_code)
        lead = LeadEntity(
            id=uuid.uuid4(),
            broker_id=cmd.broker_id,
            phone=cmd.phone,
            name=cmd.name or "New Lead",
            source=cmd.source,
            score=LeadScoreCategory.PENDING,
            status=LeadStatus.PENDING,
            pipeline_stage=PipelineStageEnum.NEW
        )
        return await self._repo.save(lead)

    async def qualify_lead(self, cmd: QualifyLeadCommand) -> LeadEntity:
        lead = await self._repo.get_by_id(cmd.lead_id, cmd.broker_id)
        if not lead:
            raise ValueError(f"Lead {cmd.lead_id} not found")

        score_vo = LeadScoreValueObject(
            score=cmd.score,
            confidence=cmd.confidence,
            reasoning=cmd.reasoning,
            extracted_data=cmd.extracted_data
        )
        lead.mark_as_qualified(score_vo)
        return await self._repo.update(lead)

    async def update_stage(self, lead_id: uuid.UUID, broker_id: uuid.UUID, stage: PipelineStageEnum) -> LeadEntity:
        lead = await self._repo.get_by_id(lead_id, broker_id)
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        lead.advance_stage(stage)
        return await self._repo.update(lead)

    async def list_leads(
        self,
        broker_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        score: Optional[str] = None,
        stage: Optional[str] = None,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        score_cat = LeadScoreCategory(score.lower()) if score else None
        stage_enum = PipelineStageEnum(stage.lower()) if stage else None

        items, total = await self._repo.list_leads(
            broker_id=broker_id,
            page=page,
            limit=limit,
            score=score_cat,
            stage=stage_enum,
            search=search
        )

        return {
            "total": total,
            "page": page,
            "limit": limit,
            "items": [
                {
                    "id": str(l.id),
                    "broker_id": str(l.broker_id),
                    "phone": l.phone,
                    "name": l.name,
                    "source": l.source,
                    "score": l.score.value,
                    "score_confidence": l.score_confidence,
                    "budget_min": l.budget_min,
                    "budget_max": l.budget_max,
                    "property_type": l.property_type,
                    "transaction_type": l.transaction_type,
                    "preferred_locations": l.preferred_locations,
                    "timeline": l.timeline,
                    "loan_status": l.loan_status,
                    "status": l.status.value,
                    "pipeline_stage": l.pipeline_stage.value,
                    "created_at": l.created_at.isoformat() if l.created_at else None
                } for l in items
            ]
        }
