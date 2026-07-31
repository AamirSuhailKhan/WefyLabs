import uuid
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from app.core.domain.analytics.entities import PredictiveIntelligenceEntity, RevenueForecastEntity

class IPredictiveIntelligenceEngine(ABC):
    """Abstract Port for Predictive ML Engine."""

    @abstractmethod
    async def predict_lead_outcomes(self, lead_id: uuid.UUID) -> PredictiveIntelligenceEntity:
        pass

    @abstractmethod
    async def forecast_revenue(self, broker_id: uuid.UUID) -> RevenueForecastEntity:
        pass
