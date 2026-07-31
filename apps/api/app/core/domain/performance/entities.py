import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

@dataclass
class CoachingRecommendationEntity:
    title: str
    category: str # velocity | follow_up | negotiation
    recommendation: str
    impact_level: str # high | medium

@dataclass
class LeaderboardRankEntity:
    rank: int
    broker_name: str
    office_name: str
    revenue_closed: float
    deals_count: int
    avatar_url: Optional[str] = None

@dataclass
class BrokerPerformanceEntity:
    """Pure Domain Entity for Broker Performance & Quota Attainment."""
    broker_id: uuid.UUID
    broker_name: str
    period: str # "Q3 2026"
    revenue_closed: float
    commission_earned: float
    monthly_quota_target: float
    quota_attainment_pct: float
    deals_closed_count: int
    conversion_rate_pct: float
    avg_response_time_mins: float
    avg_deal_size: float
    office_rank: int
    regional_rank: int
    coaching_recommendations: List[CoachingRecommendationEntity] = field(default_factory=list)
