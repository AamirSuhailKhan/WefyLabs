import uuid
import math
from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.lead import Lead
from app.modules.leads.interfaces.repository_interface import ILeadRepository
from app.modules.leads.dto.lead_dto import LeadCreateDTO, LeadUpdateDTO, LeadSearchDTO

class LeadRepository(ILeadRepository):
    """SQLAlchemy Async persistence layer for Leads."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> Optional[Lead]:
        stmt = (
            select(Lead)
            .where(
                Lead.id == lead_id,
                Lead.broker_id == broker_id,
                Lead.deleted_at.is_(None)
            )
            .options(
                selectinload(Lead.conversations),
                selectinload(Lead.scores),
                selectinload(Lead.follow_ups)
            )
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def find_by_phone(self, phone: str, broker_id: uuid.UUID) -> Optional[Lead]:
        stmt = select(Lead).where(
            Lead.phone == phone,
            Lead.broker_id == broker_id,
            Lead.deleted_at.is_(None)
        )
        result = await self.db.execute(stmt)
        return result.scalars().first()

    async def search(self, search_dto: LeadSearchDTO, broker_id: uuid.UUID) -> Tuple[List[Lead], int]:
        page = max(1, search_dto.page)
        limit = min(100, max(1, search_dto.limit))

        query = select(Lead).where(
            Lead.broker_id == broker_id,
            Lead.deleted_at.is_(None)
        )

        if search_dto.score:
            query = query.where(Lead.score == search_dto.score)
        if search_dto.stage:
            query = query.where(Lead.pipeline_stage == search_dto.stage)
        if search_dto.source:
            query = query.where(Lead.source == search_dto.source)
        if search_dto.status:
            query = query.where(Lead.status == search_dto.status)
        if search_dto.query:
            pattern = f"%{search_dto.query.strip()}%"
            query = query.where(
                or_(
                    Lead.name.ilike(pattern),
                    Lead.phone.ilike(pattern)
                )
            )

        # Count total matching rows
        count_stmt = select(func.count()).select_from(query.subquery())
        total_res = await self.db.execute(count_stmt)
        total = total_res.scalar_one()

        # Sorting
        sort_col = getattr(Lead, search_dto.sort_by, Lead.created_at)
        if search_dto.sort_order.lower() == "asc":
            query = query.order_by(sort_col.asc())
        else:
            query = query.order_by(sort_col.desc())

        # Pagination
        offset = (page - 1) * limit
        query = query.offset(offset).limit(limit).options(
            selectinload(Lead.conversations),
            selectinload(Lead.scores),
            selectinload(Lead.follow_ups)
        )

        results = await self.db.execute(query)
        items = list(results.scalars().all())
        return items, total

    async def create(self, lead_data: LeadCreateDTO, broker_id: uuid.UUID) -> Lead:
        initial_notes = []
        if lead_data.notes:
            if isinstance(lead_data.notes, str):
                initial_notes.append({
                    "id": str(uuid.uuid4()),
                    "content": lead_data.notes,
                    "color_tag": "blue",
                    "created_at": datetime.now(timezone.utc).isoformat()
                })
            elif isinstance(lead_data.notes, list):
                initial_notes = lead_data.notes

        lead = Lead(
            broker_id=broker_id,
            phone=lead_data.phone,
            name=lead_data.name,
            source=lead_data.source or "manual",
            score="pending",
            score_confidence=0.0,
            budget_min=lead_data.budget_min,
            budget_max=lead_data.budget_max,
            property_type=lead_data.property_type,
            transaction_type=lead_data.transaction_type,
            preferred_locations=lead_data.preferred_locations or [],
            timeline=lead_data.timeline,
            loan_status=lead_data.loan_status,
            status="pending",
            pipeline_stage="new",
            notes=initial_notes
        )
        self.db.add(lead)
        await self.db.flush()
        return lead

    async def update(self, lead_id: uuid.UUID, broker_id: uuid.UUID, update_data: LeadUpdateDTO) -> Optional[Lead]:
        lead = await self.get_by_id(lead_id, broker_id)
        if not lead:
            return None

        data_dict = update_data.model_dump(exclude_unset=True)
        for key, val in data_dict.items():
            if val is not None and hasattr(lead, key):
                setattr(lead, key, val)

        lead.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return lead

    async def bulk_update_stage(self, lead_ids: List[uuid.UUID], broker_id: uuid.UUID, new_stage: str) -> int:
        stmt = select(Lead).where(
            Lead.id.in_(lead_ids),
            Lead.broker_id == broker_id,
            Lead.deleted_at.is_(None)
        )
        results = await self.db.execute(stmt)
        leads = list(results.scalars().all())
        updated_count = 0
        for lead in leads:
            lead.pipeline_stage = new_stage
            lead.updated_at = datetime.now(timezone.utc)
            updated_count += 1

        await self.db.flush()
        return updated_count

    async def soft_delete(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> bool:
        lead = await self.get_by_id(lead_id, broker_id)
        if not lead:
            return False
        lead.deleted_at = datetime.now(timezone.utc)
        await self.db.flush()
        return True
