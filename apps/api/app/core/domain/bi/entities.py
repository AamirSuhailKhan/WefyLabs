import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

@dataclass
class AnomalyAlertEntity:
    id: str
    severity: str # critical | warning | info
    metric_name: str
    anomaly_description: str
    root_cause_explanation: str
    recommended_action: str

@dataclass
class NaturalLanguageQueryEntity:
    query: str
    chart_type: str # line | bar | funnel | heatmap
    explanation_markdown: str
    data_points: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class ExecutiveAnalyticsEntity:
    """Pure Domain Entity for C-Suite Tableau-grade BI metrics."""
    revenue_ytd: float
    pipeline_total_value: float
    avg_customer_acquisition_cost: float
    marketing_campaign_roi_pct: float
    conversion_rate_overall_pct: float
    anomalies: List[AnomalyAlertEntity] = field(default_factory=list)
