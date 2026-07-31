import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.core.domain.performance.entities import BrokerPerformanceEntity, LeaderboardRankEntity

class IBrokerPerformanceEngine(ABC):
    """Abstract Port for Broker Performance Analytics Storage & Calculation."""

    @abstractmethod
    async def get_broker_performance(self, broker_id: uuid.UUID) -> BrokerPerformanceEntity:
        pass

    @abstractmethod
    async def get_regional_leaderboard(self, region_code: str = "AE") -> List[LeaderboardRankEntity]:
        pass
