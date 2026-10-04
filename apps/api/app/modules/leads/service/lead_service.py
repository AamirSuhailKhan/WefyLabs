import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.events.event_bus import event_bus, DomainEvent, StandardDomainEvents, ActorContext
from app.modules.leads.interfaces.service_interface import ILeadService
from app.modules.leads.repository.lead_repository import LeadRepository
from app.modules.leads.mapper.lead_mapper import LeadMapper
from app.modules.leads.dto.lead_dto import (
    LeadCreateDTO, LeadUpdateDTO, LeadResponseDTO,
    LeadSearchDTO, LeadPaginatedResponseDTO, LeadQualifyDTO, LeadBulkDTO
)

logger = logging.getLogger(__name__)

class LeadService(ILeadService):
    """
    Enterprise Lead Domain Service. Encapsulates business validation,
    transaction orchestration, and domain event emissions.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = LeadRepository(db)

    async def create_lead(
        self,
        dto: LeadCreateDTO,
        broker_id: uuid.UUID,
        actor: ActorContext
    ) -> LeadResponseDTO:
        # Check duplicate by phone
        existing = await self.repo.find_by_phone(dto.phone, broker_id)
        if existing:
            logger.warning(f"[LEAD SERVICE] Lead with phone {dto.phone} already exists (ID: {existing.id})")

        lead = await self.repo.create(dto, broker_id)
        await self.db.commit()

        response_dto = LeadMapper.to_response_dto(lead)

        # Emit Domain Event
        event = DomainEvent(
            event_type=StandardDomainEvents.LEAD_CREATED,
            organization_id=str(lead.organization_id or broker_id),
            actor=actor,
            payload={
                "lead_id": str(lead.id),
                "organization_id": str(lead.organization_id or broker_id),
                "name": lead.name,
                "phone": lead.phone,
                "source": lead.source
            }
        )
        await event_bus.publish(event)

        return response_dto

    async def get_lead(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> LeadResponseDTO:
        lead = await self.repo.get_by_id(lead_id, broker_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Lead not found."
            )
        return LeadMapper.to_response_dto(lead)

    async def search_leads(
        self,
        search_dto: LeadSearchDTO,
        broker_id: uuid.UUID
    ) -> LeadPaginatedResponseDTO:
        items, total = await self.repo.search(search_dto, broker_id)
        return LeadMapper.to_paginated_dto(items, total, search_dto.page, search_dto.limit)

    async def update_lead(
        self,
        lead_id: uuid.UUID,
        dto: LeadUpdateDTO,
        broker_id: uuid.UUID,
        actor: ActorContext
    ) -> LeadResponseDTO:
        existing = await self.repo.get_by_id(lead_id, broker_id)
        if not existing:
            raise HTTPException(status_code=404, detail="Lead not found.")

        old_stage = existing.pipeline_stage
        updated_lead = await self.repo.update(lead_id, broker_id, dto)
        await self.db.commit()

        response_dto = LeadMapper.to_response_dto(updated_lead)

        # Emit StageChanged if pipeline_stage changed
        if dto.pipeline_stage and dto.pipeline_stage != old_stage:
            await event_bus.publish(
                DomainEvent(
                    event_type=StandardDomainEvents.STAGE_CHANGED,
                    organization_id=str(broker_id),
                    actor=actor,
                    payload={
                        "lead_id": str(lead_id),
                        "old_stage": old_stage,
                        "new_stage": dto.pipeline_stage
                    }
                )
            )

        # Emit LeadUpdated
        await event_bus.publish(
            DomainEvent(
                event_type=StandardDomainEvents.LEAD_UPDATED,
                organization_id=str(broker_id),
                actor=actor,
                payload={"lead_id": str(lead_id), "updated_fields": list(dto.model_dump(exclude_unset=True).keys())}
            )
        )

        return response_dto

    async def qualify_lead(
        self,
        lead_id: uuid.UUID,
        qualify_dto: LeadQualifyDTO,
        broker_id: uuid.UUID,
        actor: ActorContext
    ) -> LeadResponseDTO:
        lead = await self.repo.get_by_id(lead_id, broker_id)
        if not lead:
            raise HTTPException(status_code=404, detail="Lead not found.")

        update_dto = LeadUpdateDTO(
            score=qualify_dto.score,
            status="qualified"
        )
        updated_lead = await self.repo.update(lead_id, broker_id, update_dto)
        updated_lead.qualified_at = datetime.now(timezone.utc)
        await self.db.commit()

        response = LeadMapper.to_response_dto(updated_lead)

        await event_bus.publish(
            DomainEvent(
                event_type=StandardDomainEvents.LEAD_QUALIFIED,
                organization_id=str(broker_id),
                actor=actor,
                payload={
                    "lead_id": str(lead_id),
                    "score": qualify_dto.score,
                    "confidence": qualify_dto.score_confidence
                }
            )
        )

        return response

    async def bulk_operation(
        self,
        bulk_dto: LeadBulkDTO,
        broker_id: uuid.UUID,
        actor: ActorContext
    ) -> int:
        if bulk_dto.action == "update_stage":
            count = await self.repo.bulk_update_stage(bulk_dto.lead_ids, broker_id, bulk_dto.target_value)
            await self.db.commit()
            return count
        raise HTTPException(status_code=400, detail=f"Unsupported bulk action: {bulk_dto.action}")

    async def archive_lead(
        self,
        lead_id: uuid.UUID,
        broker_id: uuid.UUID,
        actor: ActorContext
    ) -> bool:
        success = await self.repo.soft_delete(lead_id, broker_id)
        if not success:
            raise HTTPException(status_code=404, detail="Lead not found.")
        await self.db.commit()
        return True
