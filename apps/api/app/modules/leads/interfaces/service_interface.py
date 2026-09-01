from abc import ABC, abstractmethod
from typing import List, Optional
import uuid
from app.infrastructure.events.event_bus import ActorContext
from app.modules.leads.dto.lead_dto import (
    LeadCreateDTO, LeadUpdateDTO, LeadResponseDTO,
    LeadSearchDTO, LeadPaginatedResponseDTO, LeadQualifyDTO, LeadBulkDTO
)

class ILeadService(ABC):
    """Business Logic service interface for Lead management."""

    @abstractmethod
    async def create_lead(self, dto: LeadCreateDTO, broker_id: uuid.UUID, actor: ActorContext) -> LeadResponseDTO:
        pass

    @abstractmethod
    async def get_lead(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> LeadResponseDTO:
        pass

    @abstractmethod
    async def search_leads(self, search_dto: LeadSearchDTO, broker_id: uuid.UUID) -> LeadPaginatedResponseDTO:
        pass

    @abstractmethod
    async def update_lead(self, lead_id: uuid.UUID, dto: LeadUpdateDTO, broker_id: uuid.UUID, actor: ActorContext) -> LeadResponseDTO:
        pass

    @abstractmethod
    async def qualify_lead(self, lead_id: uuid.UUID, qualify_dto: LeadQualifyDTO, broker_id: uuid.UUID, actor: ActorContext) -> LeadResponseDTO:
        pass

    @abstractmethod
    async def bulk_operation(self, bulk_dto: LeadBulkDTO, broker_id: uuid.UUID, actor: ActorContext) -> int:
        pass

    @abstractmethod
    async def archive_lead(self, lead_id: uuid.UUID, broker_id: uuid.UUID, actor: ActorContext) -> bool:
        pass
