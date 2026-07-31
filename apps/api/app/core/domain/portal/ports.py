import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.core.domain.portal.entities import CustomerPortalEntity, CustomerDealProgressEntity

class ICustomerPortalRepository(ABC):
    """Abstract Port for Customer Portal Data Access."""

    @abstractmethod
    async def get_customer_portal(self, customer_id: uuid.UUID) -> Optional[CustomerPortalEntity]:
        pass

    @abstractmethod
    async def get_deal_progress(self, deal_id: uuid.UUID) -> Optional[CustomerDealProgressEntity]:
        pass
