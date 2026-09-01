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
    """Pure Domain Entity for real, feature-based conversion propensity intelligence."""
    lead_id: Optional[uuid.UUID]
    conversion_probability_pct: float
    deal_close_probability_pct: float
    churn_risk_pct: float
    estimated_lifetime_value: float
    best_followup_window: str # e.g. "Within 24 hours"
    confidence_interval: str # e.g. "80% - 90%"
    feature_attributions: List[FeatureAttributionEntity] = field(default_factory=list)
    model_version: str = "v1.0-propensity-heuristic"
    prediction_timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    feature_snapshot: Dict[str, Any] = field(default_factory=dict)

@dataclass
class RevenueForecastEntity:
    quarter: str
    projected_revenue: float
    confidence_lower_bound: float
    confidence_upper_bound: float
    pipeline_health_score: float
    deals_count: int = 0
    calculation_basis: str = "deal_pipeline_aggregation"
