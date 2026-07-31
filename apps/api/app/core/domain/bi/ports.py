import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.core.domain.bi.entities import ExecutiveAnalyticsEntity, NaturalLanguageQueryEntity

class IAnalyticsEngine(ABC):
    """Abstract Port for Tableau-Grade OLAP BI Metrics Engine."""

    @abstractmethod
    async def get_executive_summary(self) -> ExecutiveAnalyticsEntity:
        pass

    @abstractmethod
    async def process_natural_language_query(self, query: str) -> NaturalLanguageQueryEntity:
        pass
