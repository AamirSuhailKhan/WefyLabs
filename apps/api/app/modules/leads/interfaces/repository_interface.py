from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
import uuid
from app.models.lead import Lead
from app.modules.leads.dto.lead_dto import LeadCreateDTO, LeadUpdateDTO, LeadSearchDTO

class ILeadRepository(ABC):
    """Persistence-only repository interface for Leads."""
    
    @abstractmethod
    async def get_by_id(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> Optional[Lead]:
        pass

    @abstractmethod
    async def find_by_phone(self, phone: str, broker_id: uuid.UUID) -> Optional[Lead]:
        pass

    @abstractmethod
    async def search(self, search_dto: LeadSearchDTO, broker_id: uuid.UUID) -> Tuple[List[Lead], int]:
        pass

    @abstractmethod
    async def create(self, lead_data: LeadCreateDTO, broker_id: uuid.UUID) -> Lead:
        pass

    @abstractmethod
    async def update(self, lead_id: uuid.UUID, broker_id: uuid.UUID, update_data: LeadUpdateDTO) -> Optional[Lead]:
        pass

    @abstractmethod
    async def bulk_update_stage(self, lead_ids: List[uuid.UUID], broker_id: uuid.UUID, new_stage: str) -> int:
        pass

    @abstractmethod
    async def soft_delete(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> bool:
        pass
