import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from app.core.domain.leads.entities import LeadEntity, LeadScoreCategory, PipelineStageEnum, LeadStatus

class ILeadRepository(ABC):
    """Abstract Hexagonal Port for Lead Persistence."""

    @abstractmethod
    async def get_by_id(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> Optional[LeadEntity]:
        pass

    @abstractmethod
    async def get_by_phone(self, phone: str, broker_id: uuid.UUID) -> Optional[LeadEntity]:
        pass

    @abstractmethod
    async def save(self, lead: LeadEntity) -> LeadEntity:
        pass

    @abstractmethod
    async def update(self, lead: LeadEntity) -> LeadEntity:
        pass

    @abstractmethod
    async def delete(self, lead_id: uuid.UUID, broker_id: uuid.UUID) -> bool:
        pass

    @abstractmethod
    async def list_leads(
        self,
        broker_id: uuid.UUID,
        page: int = 1,
        limit: int = 20,
        score: Optional[LeadScoreCategory] = None,
        stage: Optional[PipelineStageEnum] = None,
        search: Optional[str] = None
    ) -> Tuple[List[LeadEntity], int]:
        pass
