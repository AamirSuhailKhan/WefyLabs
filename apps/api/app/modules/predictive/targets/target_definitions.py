"""
Part 16 — Prediction Target Definition Contracts
=================================================
Every predictive target must explicitly declare:
  - target_id / name
  - definition / outcome (positive / negative / unknown)
  - lookahead window
  - eligibility & exclusion criteria
  - anchor timestamp
  - method (DETERMINISTIC_HEURISTIC | STATISTICAL_BASELINE | LLM_ESTIMATE | VALIDATED_ML | UNAVAILABLE)
  - version
  - minimum sample requirements

NO model is trained or promoted without passing the data sufficiency gate.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Dict, Any


class PredictionMethod(str, Enum):
    DETERMINISTIC_HEURISTIC = "DETERMINISTIC_HEURISTIC"
    STATISTICAL_BASELINE = "STATISTICAL_BASELINE"
    LLM_ESTIMATE = "LLM_ESTIMATE"
    VALIDATED_ML = "VALIDATED_ML"
    UNAVAILABLE = "UNAVAILABLE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class ModelStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SHADOW = "SHADOW"
    BASELINE = "BASELINE"
    UNAVAILABLE = "UNAVAILABLE"
    STALE = "STALE"
    ERROR = "ERROR"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class TargetDefinition:
    target_id: str
    name: str
    definition: str
    positive_outcome: str
    negative_outcome: str
    unknown_outcome: str
    lookahead_window_days: int
    anchor_event: str          # e.g. "lead_created_at"
    eligibility_criteria: str
    exclusion_criteria: str
    min_eligible_rows: int     # minimum rows for any model
    min_positive_labels: int   # minimum positives for ML training
    method: PredictionMethod
    version: str
    status: ModelStatus
    reason: str                # Why this method / status

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "name": self.name,
            "definition": self.definition,
            "positive_outcome": self.positive_outcome,
            "negative_outcome": self.negative_outcome,
            "unknown_outcome": self.unknown_outcome,
            "lookahead_window_days": self.lookahead_window_days,
            "anchor_event": self.anchor_event,
            "eligibility_criteria": self.eligibility_criteria,
            "exclusion_criteria": self.exclusion_criteria,
            "min_eligible_rows": self.min_eligible_rows,
            "min_positive_labels": self.min_positive_labels,
            "method": self.method.value,
            "version": self.version,
            "status": self.status.value,
            "reason": self.reason,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CANONICAL TARGET DEFINITIONS — PART 16 v1
# ─────────────────────────────────────────────────────────────────────────────

LEAD_RESPONSE_PROPENSITY_V1 = TargetDefinition(
    target_id="LEAD_RESPONSE_PROPENSITY_V1",
    name="Lead Response Propensity",
    definition="Probability an active lead will produce an observable inbound message or call answer "
               "within 48 hours of the next permitted outbound contact.",
    positive_outcome="Inbound conversation event OR answered call within 48h of outbound",
    negative_outcome="No inbound response within 48h AND 48h window has expired",
    unknown_outcome="Outbound not yet sent OR 48h window not expired",
    lookahead_window_days=2,
    anchor_event="outbound_communication_sent_at",
    eligibility_criteria="Active lead (not lost/archived), last outbound < 7 days ago",
    exclusion_criteria="Opted-out leads, DNC list, no prior outbound contact",
    min_eligible_rows=200,
    min_positive_labels=50,
    method=PredictionMethod.DETERMINISTIC_HEURISTIC,
    version="v1",
    status=ModelStatus.BASELINE,
    reason="Data foundation implemented. Baseline uses historical response-rate by lead source and stage. "
           "ML upgrade requires >= 200 eligible rows with >= 50 positive labels.",
)

APPOINTMENT_PROPENSITY_V1 = TargetDefinition(
    target_id="APPOINTMENT_PROPENSITY_V1",
    name="Appointment Propensity",
    definition="Probability a qualified or engaged lead will have an appointment booked within 14 days.",
    positive_outcome="scheduling_meeting created AND status=scheduled/confirmed within 14d",
    negative_outcome="No meeting created within 14d AND window expired",
    unknown_outcome="Window not expired",
    lookahead_window_days=14,
    anchor_event="lead_qualified_at OR last_engagement_at",
    eligibility_criteria="Lead stage >= QUALIFIED or has >= 2 inbound messages",
    exclusion_criteria="Lead lost/archived, already has confirmed appointment",
    min_eligible_rows=100,
    min_positive_labels=30,
    method=PredictionMethod.DETERMINISTIC_HEURISTIC,
    version="v1",
    status=ModelStatus.BASELINE,
    reason="Baseline: observed appointment booking rate by stage and engagement tier. "
           "ML requires >= 100 eligible rows with >= 30 positives.",
)

SITE_VISIT_PROPENSITY_V1 = TargetDefinition(
    target_id="SITE_VISIT_PROPENSITY_V1",
    name="Site Visit (Viewing) Propensity",
    definition="Probability a booked appointment progresses to a completed site visit within the window.",
    positive_outcome="Meeting status = 'completed' (attended) within scheduled window",
    negative_outcome="Meeting status = 'cancelled' or 'no_show'",
    unknown_outcome="Meeting in future or status unknown",
    lookahead_window_days=7,
    anchor_event="meeting_scheduled_at",
    eligibility_criteria="Appointment status = scheduled/confirmed",
    exclusion_criteria="Already completed/cancelled meetings",
    min_eligible_rows=50,
    min_positive_labels=20,
    method=PredictionMethod.DETERMINISTIC_HEURISTIC,
    version="v1",
    status=ModelStatus.BASELINE,
    reason="Baseline: observed attendance rate by lead score and appointment count. "
           "Too few site visits in test data for ML training.",
)

OPPORTUNITY_STALL_RISK_V1 = TargetDefinition(
    target_id="OPPORTUNITY_STALL_RISK_V1",
    name="Opportunity Stall Risk",
    definition="Probability an active opportunity becomes stalled (no progression or activity) within 14 days.",
    positive_outcome="Opportunity has no stage change AND no activity within 14d",
    negative_outcome="Opportunity progresses to next stage or is closed within 14d",
    unknown_outcome="14d window not expired",
    lookahead_window_days=14,
    anchor_event="opportunity_created_at",
    eligibility_criteria="Active revenue opportunity, not closed, stage >= OPPORTUNITY",
    exclusion_criteria="Closed/won/lost opportunities, archived leads",
    min_eligible_rows=50,
    min_positive_labels=15,
    method=PredictionMethod.DETERMINISTIC_HEURISTIC,
    version="v1",
    status=ModelStatus.BASELINE,
    reason="Baseline uses stage age and activity gap heuristics. "
           "ML upgrade requires >= 50 rows with matured 14d windows.",
)

BOOKING_PROPENSITY_V1 = TargetDefinition(
    target_id="BOOKING_PROPENSITY_V1",
    name="Booking Propensity",
    definition="Probability an active opportunity results in a booking within 30 days.",
    positive_outcome="DealTransaction/booking created within 30d of opportunity",
    negative_outcome="Opportunity closed_lost OR 30d window expired without booking",
    unknown_outcome="30d window not yet expired",
    lookahead_window_days=30,
    anchor_event="opportunity_created_at",
    eligibility_criteria="Active revenue opportunity with identified property",
    exclusion_criteria="Already booked, lost, or archived",
    min_eligible_rows=100,
    min_positive_labels=20,
    method=PredictionMethod.DETERMINISTIC_HEURISTIC,
    version="v1",
    status=ModelStatus.BASELINE,
    reason="High-value target. Requires >= 100 eligible rows with >= 20 bookings. "
           "Current DETERMINISTIC_HEURISTIC uses stage conversion rates.",
)

LEAD_COLD_RISK_V1 = TargetDefinition(
    target_id="LEAD_COLD_RISK_V1",
    name="Lead Cold/Churn Risk",
    definition="Probability an active lead becomes cold (no meaningful activity for 14+ days) within 7 days.",
    positive_outcome="Lead shows no inbound response AND no outbound within 14d",
    negative_outcome="Lead shows activity within 14d",
    unknown_outcome="7d window not expired",
    lookahead_window_days=7,
    anchor_event="last_activity_at",
    eligibility_criteria="Active lead not yet archived, last activity < 21 days ago",
    exclusion_criteria="Already cold/lost/archived leads",
    min_eligible_rows=200,
    min_positive_labels=50,
    method=PredictionMethod.DETERMINISTIC_HEURISTIC,
    version="v1",
    status=ModelStatus.BASELINE,
    reason="Baseline: inactivity heuristic by hours_since_last_activity and response ratio. "
           "Observable activity is the ground truth; no mental-state claims.",
)

PROPERTY_CONVERSION_PROPENSITY_V1 = TargetDefinition(
    target_id="PROPERTY_CONVERSION_PROPENSITY_V1",
    name="Property Conversion Propensity",
    definition="Historical observed rate at which a qualified property interaction progresses to appointment/booking.",
    positive_outcome="Property interaction leads to booked appointment within 30d",
    negative_outcome="No appointment within 30d",
    unknown_outcome="Window not expired or interaction unclear",
    lookahead_window_days=30,
    anchor_event="property_interaction_at",
    eligibility_criteria="Qualified property match or recommendation interaction",
    exclusion_criteria="Unqualified leads, properties with < 5 interactions",
    min_eligible_rows=50,
    min_positive_labels=10,
    method=PredictionMethod.STATISTICAL_BASELINE,
    version="v1",
    status=ModelStatus.BASELINE,
    reason="Statistical baseline: historical progression rate per property. "
           "Separate from Match Score (which measures fit, not conversion likelihood).",
)

SOURCE_QUALITY_V1 = TargetDefinition(
    target_id="SOURCE_QUALITY_V1",
    name="Source Quality Prediction",
    definition="Expected downstream conversion rate for a lead source/campaign based on historical cohort outcomes.",
    positive_outcome="Lead from source reaches OPPORTUNITY stage within 90d",
    negative_outcome="Lead lost within 90d without reaching OPPORTUNITY",
    unknown_outcome="Less than 90d of history for source",
    lookahead_window_days=90,
    anchor_event="lead_created_at",
    eligibility_criteria="Source with >= 20 leads and >= 90d of history",
    exclusion_criteria="Sources with < 20 leads (insufficient data — show UNAVAILABLE)",
    min_eligible_rows=20,
    min_positive_labels=5,
    method=PredictionMethod.STATISTICAL_BASELINE,
    version="v1",
    status=ModelStatus.BASELINE,
    reason="Statistical baseline per source using observed cohort conversion rates. "
           "Small sources shown as UNAVAILABLE to prevent overfitting.",
)

NEXT_BEST_ACTION_V1 = TargetDefinition(
    target_id="NEXT_BEST_ACTION_V1",
    name="Next Best Action Ranking",
    definition="Ranks eligible actions for a lead/opportunity based on observed historical outcome patterns "
               "and current entity state, respecting business rules and policy.",
    positive_outcome="Selected action associated with progression to next stage within lookahead",
    negative_outcome="No progression observed after action",
    unknown_outcome="Insufficient outcome data for this action type",
    lookahead_window_days=14,
    anchor_event="action_recommended_at",
    eligibility_criteria="Lead or opportunity with deterministic eligible actions",
    exclusion_criteria="Actions requiring unavailable channels, opted-out leads, unauthorized roles",
    min_eligible_rows=100,
    min_positive_labels=20,
    method=PredictionMethod.DETERMINISTIC_HEURISTIC,
    version="v1",
    status=ModelStatus.BASELINE,
    reason="Business rules filter first. Heuristic ranking based on stage, engagement, and action history. "
           "ML upgrade requires >= 100 completed action-outcome pairs.",
)

REVENUE_FORECAST_V1 = TargetDefinition(
    target_id="REVENUE_FORECAST_V1",
    name="Revenue Forecast",
    definition="Pipeline-weighted expected revenue forecast over defined horizons (7d, 30d, 90d).",
    positive_outcome="Opportunity converted to booking within forecast horizon",
    negative_outcome="Opportunity closed lost within horizon",
    unknown_outcome="Horizon not expired or opportunity still active",
    lookahead_window_days=30,
    anchor_event="forecast_generated_at",
    eligibility_criteria="Active pipeline opportunities with defined value",
    exclusion_criteria="No authoritative opportunity value, zero-value pipeline",
    min_eligible_rows=10,
    min_positive_labels=3,
    method=PredictionMethod.STATISTICAL_BASELINE,
    version="v1",
    status=ModelStatus.BASELINE,
    reason="Statistical baseline: stage-weighted pipeline value. "
           "Existing RevenueForecastService provides the foundation. "
           "No time-series ML without >= 12 months of booking history.",
)

# ─── Registry ─────────────────────────────────────────────────────────────────

ALL_TARGET_DEFINITIONS = {
    "LEAD_RESPONSE_PROPENSITY_V1": LEAD_RESPONSE_PROPENSITY_V1,
    "APPOINTMENT_PROPENSITY_V1": APPOINTMENT_PROPENSITY_V1,
    "SITE_VISIT_PROPENSITY_V1": SITE_VISIT_PROPENSITY_V1,
    "OPPORTUNITY_STALL_RISK_V1": OPPORTUNITY_STALL_RISK_V1,
    "BOOKING_PROPENSITY_V1": BOOKING_PROPENSITY_V1,
    "LEAD_COLD_RISK_V1": LEAD_COLD_RISK_V1,
    "PROPERTY_CONVERSION_PROPENSITY_V1": PROPERTY_CONVERSION_PROPENSITY_V1,
    "SOURCE_QUALITY_V1": SOURCE_QUALITY_V1,
    "NEXT_BEST_ACTION_V1": NEXT_BEST_ACTION_V1,
    "REVENUE_FORECAST_V1": REVENUE_FORECAST_V1,
}


def get_target(target_id: str) -> TargetDefinition:
    t = ALL_TARGET_DEFINITIONS.get(target_id)
    if not t:
        raise KeyError(f"Unknown prediction target: {target_id}")
    return t
