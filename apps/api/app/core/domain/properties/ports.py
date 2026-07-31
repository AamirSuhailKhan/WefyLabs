import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict, Any
from app.core.domain.properties.entities import PropertyListingEntity, PropertyStatus, PropertyType

class IPropertyRepository(ABC):
    """Abstract Hexagonal Port for Property Inventory Persistence."""

    @abstractmethod
    async def get_by_id(self, property_id: uuid.UUID) -> Optional[PropertyListingEntity]:
        pass

    @abstractmethod
    async def save(self, property_listing: PropertyListingEntity) -> PropertyListingEntity:
        pass

    @abstractmethod
    async def list_properties(
        self,
        broker_id: Optional[uuid.UUID] = None,
        city: Optional[str] = None,
        property_type: Optional[PropertyType] = None,
        status: Optional[PropertyStatus] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20
    ) -> Tuple[List[PropertyListingEntity], int]:
        pass
