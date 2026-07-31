import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple, Dict, Any
from app.core.domain.transactions.entities import DealTransactionEntity, TransactionStage

class ITransactionRepository(ABC):
    """Abstract Hexagonal Port for Transaction Lifecycle Persistence."""

    @abstractmethod
    async def get_by_id(self, deal_id: uuid.UUID) -> Optional[DealTransactionEntity]:
        pass

    @abstractmethod
    async def save(self, deal: DealTransactionEntity) -> DealTransactionEntity:
        pass

    @abstractmethod
    async def list_deals(
        self,
        broker_id: Optional[uuid.UUID] = None,
        stage: Optional[TransactionStage] = None,
        page: int = 1,
        limit: int = 20
    ) -> Tuple[List[DealTransactionEntity], int]:
        pass
