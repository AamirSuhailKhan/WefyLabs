import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, func, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.domain.leads.entities import LeadEntity, LeadScoreCategory, PipelineStageEnum, LeadStatus
from app.core.domain.leads.ports import ILeadRepository
from app.models.lead import Lead

class SQLAlchemyLeadRepository(ILeadRepository):
    """Hexagonal Adapter mapping Lead SQLAlchemy ORM Model to Pure Lead Domain Entity."""

    def __init__(self, db: AsyncSession):
        self._db = db

    def _to_entity(self, model: Lead) -> LeadEntity:
        return LeadEntity(
            id=model.id,
            broker_id=model.broker_id,
            phone=model.phone,
            name=model.name or "New Lead",
            source=model.source,
            score=LeadScoreCategory(model.score.lower()) if model.score else LeadScoreCategory.PENDING,
            score_confidence=model.score_confidence or 0.0,
            budget_min=model.budget_min,
            budget_max=model.budget_max,
            property_type=model.property_type,
            transaction_type=model.transaction_type,
            preferred_locations=model.preferred_locations or [],
            timeline=model.timeline,
            loan_status=model.loan_status,
            status=LeadStatus(model.status.lower()) if model.status else LeadStatus.PENDING,
            pipeline_stage=PipelineStageEnum(model.pipeline_stage.lower()) if model.pipeline_stage else PipelineStageEnum.NEW,
            notes=model.notes or [],
            last_message_at=model.last_message_at,
            qualified_at=model.qualified_at,
            deleted_at=model.deleted_at,
            created_at=model.created_at,
            updated_at=model.updated_at
        )

    async def get_by_id(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> Optional[LeadEntity]:
        stmt = select(Lead).where(
            Lead.id == lead_id,
            Lead.broker_id == broker_id,
            Lead.deleted_at.is_(None)
        )
        res = await self._db.execute(stmt)
        model = res.scalars().first()
        return self._to_entity(model) if model else None

    async def get_by_phone(self, phone: str, broker_id: uuid.UUID) -> Optional[LeadEntity]:
        stmt = select(Lead).where(
            Lead.phone == phone,
            Lead.broker_id == broker_id,
            Lead.deleted_at.is_(None)
        )
        res = await self._db.execute(stmt)
        model = res.scalars().first()
        return self._to_entity(model) if model else None

    async def save(self, lead: LeadEntity) -> LeadEntity:
        model = Lead(
            id=lead.id,
            broker_id=lead.broker_id,
            phone=lead.phone,
            name=lead.name,
            source=lead.source,
            score=lead.score.value,
            score_confidence=lead.score_confidence,
            budget_min=lead.budget_min,
            budget_max=lead.budget_max,
            property_type=lead.property_type,
            transaction_type=lead.transaction_type,
            preferred_locations=lead.preferred_locations,
            timeline=lead.timeline,
            loan_status=lead.loan_status,
            status=lead.status.value,
            pipeline_stage=lead.pipeline_stage.value,
            notes=lead.notes,
            created_at=lead.created_at,
            updated_at=lead.updated_at
        )
        self._db.add(model)
        await self._db.commit()
        await self._db.refresh(model)
        return self._to_entity(model)

    async def update(self, lead: LeadEntity) -> LeadEntity:
        stmt = select(Lead).where(Lead.id == lead.id, Lead.broker_id == lead.broker_id)
        res = await self._db.execute(stmt)
        model = res.scalars().first()
        if not model:
            raise ValueError(f"Lead {lead.id} not found")

        model.name = lead.name
        model.score = lead.score.value
        model.score_confidence = lead.score_confidence
        model.status = lead.status.value
        model.pipeline_stage = lead.pipeline_stage.value
        model.budget_min = lead.budget_min
        model.budget_max = lead.budget_max
        model.property_type = lead.property_type
        model.transaction_type = lead.transaction_type
        model.preferred_locations = lead.preferred_locations
        model.timeline = lead.timeline
        model.loan_status = lead.loan_status
        model.notes = lead.notes
        model.qualified_at = lead.qualified_at
        model.updated_at = datetime.now(timezone.utc)

        await self._db.commit()
        await self._db.refresh(model)
        return self._to_entity(model)

    async def delete(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> bool:
        stmt = select(Lead).where(Lead.id == lead_id, Lead.broker_id == broker_id)
        res = await self._db.execute(stmt)
        model = res.scalars().first()
        if not model:
            return False

        model.deleted_at = datetime.now(timezone.utc)
        await self._db.commit()
        return True

    async def list_leads(
        self,
        broker_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        score: Optional[LeadScoreCategory] = None,
        stage: Optional[PipelineStageEnum] = None,
        search: Optional[str] = None
    ) -> Tuple[List[LeadEntity], int]:
        stmt = select(Lead).where(Lead.broker_id == broker_id, Lead.deleted_at.is_(None))
        if score:
            stmt = stmt.where(Lead.score == score.value)
        if stage:
            stmt = stmt.where(Lead.pipeline_stage == stage.value)
        if search:
            search_pattern = f"%{search}%"
            stmt = stmt.where(or_(Lead.name.ilike(search_pattern), Lead.phone.ilike(search_pattern)))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        count_res = await self._db.execute(count_stmt)
        total = count_res.scalar_one_or_none() or 0

        offset = (page - 1) * limit
        stmt = stmt.order_by(desc(Lead.created_at)).offset(offset).limit(limit)
        res = await self._db.execute(stmt)
        models = res.scalars().all()

        return [self._to_entity(m) for m in models], total
