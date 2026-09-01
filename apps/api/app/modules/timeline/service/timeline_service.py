import math
import logging
from typing import Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.infrastructure_models import TimelineEvent
from app.modules.timeline.dto.timeline_dto import (
    TimelineCreateDTO, TimelineSearchDTO, TimelineResponseDTO, TimelinePaginatedDTO
)

logger = logging.getLogger(__name__)


class TimelineService:
    """
    Unified Activity Timeline Service.
    Writes are immutable. Reads are cursor-paginated, newest-first.
    Any module (AI, WhatsApp, Workflow) can append events via this service.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def append(self, dto: TimelineCreateDTO) -> TimelineResponseDTO:
        """Appends an immutable timeline event for a CRM resource."""
        event = TimelineEvent(
            organization_id=dto.organization_id,
            resource_type=dto.resource_type,
            resource_id=dto.resource_id,
            event_type=dto.event_type,
            title=dto.title,
            body=dto.body,
            channel=dto.channel,
            actor_id=dto.actor_id,
            actor_type=dto.actor_type,
            metadata=dto.metadata or {},
            correlation_id=dto.correlation_id,
        )
        self.db.add(event)
        await self.db.commit()
        logger.info(f"[TIMELINE] {dto.event_type} on {dto.resource_type}/{dto.resource_id}")
        return TimelineResponseDTO.model_validate(event)

    async def get_timeline(
        self,
        resource_type: str,
        resource_id: str,
        organization_id: str,
        search_dto: TimelineSearchDTO,
    ) -> TimelinePaginatedDTO:
        """Fetch newest-first timeline for a CRM object with filtering."""
        conditions = [
            TimelineEvent.resource_type == resource_type,
            TimelineEvent.resource_id == resource_id,
            TimelineEvent.organization_id == organization_id,
        ]
        if search_dto.event_type:
            conditions.append(TimelineEvent.event_type == search_dto.event_type)
        if search_dto.channel:
            conditions.append(TimelineEvent.channel == search_dto.channel)
        if search_dto.actor_type:
            conditions.append(TimelineEvent.actor_type == search_dto.actor_type)

        base = select(TimelineEvent).where(and_(*conditions))

        count_stmt = select(func.count()).select_from(base.subquery())
        total = (await self.db.execute(count_stmt)).scalar_one()

        offset = (search_dto.page - 1) * search_dto.limit
        stmt = base.order_by(TimelineEvent.created_at.desc()).offset(offset).limit(search_dto.limit)
        results = await self.db.execute(stmt)
        items = list(results.scalars().all())

        pages = math.ceil(total / search_dto.limit) if total > 0 else 0
        return TimelinePaginatedDTO(
            items=[TimelineResponseDTO.model_validate(i) for i in items],
            total=total,
            page=search_dto.page,
            pages=pages,
            limit=search_dto.limit,
            has_next=search_dto.page < pages,
            has_prev=search_dto.page > 1,
        )
