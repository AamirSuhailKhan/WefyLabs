import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

@dataclass
class FeatureAttributionEntity:
    feature_name: str
    impact_score: float # positive or negative contribution
    description: str

@dataclass
class PredictiveIntelligenceEntity:
    """Pure Domain Entity for Salesforce Einstein-grade predictive intelligence."""
    lead_id: Optional[uuid.UUID]
    conversion_probability_pct: float
    deal_close_probability_pct: float
    churn_risk_pct: float
    estimated_lifetime_value: float
    best_followup_window: str # e.g. "Tomorrow 10:00 AM - 11:30 AM"
    confidence_interval: str # e.g. "88% - 94%"
    feature_attributions: List[FeatureAttributionEntity] = field(default_factory=list)

@dataclass
class RevenueForecastEntity:
    quarter: str
    projected_revenue: float
    confidence_lower_bound: float
    confidence_upper_bound: float
    pipeline_health_score: float
