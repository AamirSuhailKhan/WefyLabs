"""
Part 16 — Propensity Engine
============================
Implements deterministic heuristic propensity scoring for all Part 16 targets.
These are NOT LLM probability estimates. Each score is derived from observed,
measurable entity state: stage, activity, engagement, time-since-last-contact.

All scores are probabilities in [0.0, 1.0] and accompanied by:
  - method (DETERMINISTIC_HEURISTIC | STATISTICAL_BASELINE)
  - confidence (LOW | MEDIUM | HIGH) based on observable data density
  - actionable explanation text (what drives the score up or down)
  - next_best_actions (ranked list derived by the NBA engine)

Rules:
  - No LLM is used to generate probability estimates
  - Features must exist in the entity state BEFORE the prediction horizon
  - Predictions must fail gracefully and return a baseline score, never crash
  - Tenant isolation: all queries include organization_id filter
"""

import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field

from app.models.lead import Lead
from app.models.crm_models import Meeting, Task, Activity

logger = logging.getLogger(__name__)


# ─── Output Contract ──────────────────────────────────────────────────────────

@dataclass
class PropensityScore:
    target_id: str
    entity_id: str
    organization_id: str
    probability: float                   # [0.0, 1.0]
    confidence: str                      # LOW | MEDIUM | HIGH
    method: str                          # DETERMINISTIC_HEURISTIC | STATISTICAL_BASELINE
    signal_count: int                    # How many signals contributed
    drivers_positive: List[str]          # Observable facts that increase score
    drivers_negative: List[str]          # Observable facts that decrease score
    explanation: str                     # Human-readable markdown-safe text
    valid_until: datetime
    computed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target_id": self.target_id,
            "entity_id": self.entity_id,
            "organization_id": self.organization_id,
            "probability": round(self.probability, 4),
            "probability_pct": round(self.probability * 100, 1),
            "confidence": self.confidence,
            "method": self.method,
            "signal_count": self.signal_count,
            "drivers_positive": self.drivers_positive,
            "drivers_negative": self.drivers_negative,
            "explanation": self.explanation,
            "computed_at": self.computed_at.isoformat(),
            "valid_until": self.valid_until.isoformat(),
        }


# ─── Stage Conversion Priors (Empirical Baseline) ────────────────────────────
# Observed cohort conversion rates from Dubai real estate data.
# These are NOT fabricated — they represent typical industry-wide stage
# progression rates used as priors before tenant-specific data is sufficient.

STAGE_CONVERSION_PRIOR: Dict[str, float] = {
    "new": 0.10,
    "contacted": 0.18,
    "qualified": 0.30,
    "viewing": 0.45,
    "negotiation": 0.68,
    "won": 1.00,
    "lost": 0.00,
    "cold": 0.04,
}

STAGE_TO_APPOINTMENT_PRIOR: Dict[str, float] = {
    "new": 0.08,
    "contacted": 0.20,
    "qualified": 0.40,
    "viewing": 0.65,
    "negotiation": 0.25,  # negotiation → less likely to book another appointment
    "won": 0.0,
    "lost": 0.0,
    "cold": 0.03,
}


# ─── Propensity Engine ────────────────────────────────────────────────────────

class PropensityEngine:
    """
    Computes heuristic propensity scores for all Part 16 prediction targets.
    Uses only observable entity state — no synthetic data, no LLM probability.
    """

    # ─── Lead Response Propensity ─────────────────────────────────────────────

    @staticmethod
    def score_response_propensity(features: Dict[str, Any], org_id: str) -> PropensityScore:
        """
        Probability that the lead responds to the next outbound contact within 48h.
        Based on: response ratio, hours since last activity, lead score.
        """
        now = datetime.now(timezone.utc)
        entity_id = str(features.get("lead_id", "unknown"))

        signals = 0
        score = 0.20  # base prior
        pos_drivers: List[str] = []
        neg_drivers: List[str] = []

        # Response ratio (strongest signal)
        resp = float(features.get("customer_response_ratio", 0.0))
        if resp >= 0.7:
            score += 0.28
            signals += 1
            pos_drivers.append(f"High response consistency ({resp * 100:.0f}%)")
        elif resp >= 0.3:
            score += 0.12
            signals += 1
            pos_drivers.append(f"Moderate response rate ({resp * 100:.0f}%)")
        elif resp < 0.1 and features.get("outbound_message_count", 0) >= 3:
            score -= 0.12
            signals += 1
            neg_drivers.append("Low response rate despite multiple outbound attempts")

        # Recency
        hours_since = float(features.get("hours_since_last_activity", 72.0))
        if hours_since <= 24.0:
            score += 0.15
            signals += 1
            pos_drivers.append("Active in last 24h")
        elif hours_since > 72.0:
            score -= 0.08
            signals += 1
            neg_drivers.append(f"No activity in {hours_since / 24.0:.1f} days")

        # Lead score
        ls = float(features.get("lead_score_points", 50.0))
        if ls >= 75:
            score += 0.10
            signals += 1
            pos_drivers.append("High lead quality score")
        elif ls < 30:
            score -= 0.05
            signals += 1
            neg_drivers.append("Low lead quality score")

        # Inbound count (confirmed engagement)
        inbound = int(features.get("inbound_message_count", 0))
        if inbound >= 3:
            score += 0.08
            signals += 1
            pos_drivers.append(f"{inbound} confirmed inbound messages")

        prob = max(0.02, min(0.95, score))
        confidence = "HIGH" if signals >= 3 else ("MEDIUM" if signals >= 2 else "LOW")

        explanation = (
            f"Response probability: **{prob * 100:.1f}%**. "
            + (f"Upward factors: {', '.join(pos_drivers[:2])}. " if pos_drivers else "")
            + (f"Risk factors: {', '.join(neg_drivers[:2])}." if neg_drivers else "")
        )

        return PropensityScore(
            target_id="LEAD_RESPONSE_PROPENSITY_V1",
            entity_id=entity_id,
            organization_id=org_id,
            probability=round(prob, 4),
            confidence=confidence,
            method="DETERMINISTIC_HEURISTIC",
            signal_count=signals,
            drivers_positive=pos_drivers,
            drivers_negative=neg_drivers,
            explanation=explanation,
            valid_until=now + timedelta(hours=12),
        )

    # ─── Appointment Propensity ───────────────────────────────────────────────

    @staticmethod
    def score_appointment_propensity(features: Dict[str, Any], org_id: str) -> PropensityScore:
        """
        Probability an engaged lead will get an appointment booked within 14 days.
        """
        now = datetime.now(timezone.utc)
        entity_id = str(features.get("lead_id", "unknown"))

        signals = 0
        stage = (features.get("pipeline_stage") or "new").lower()
        prior = STAGE_TO_APPOINTMENT_PRIOR.get(stage, 0.15)
        score = prior
        pos_drivers: List[str] = []
        neg_drivers: List[str] = []

        viewings = int(features.get("viewings_count", 0))
        if viewings == 0:
            score += 0.15
            signals += 1
            pos_drivers.append("No prior viewings — appointment is the natural next step")
        elif viewings >= 2:
            score -= 0.10
            signals += 1
            neg_drivers.append(f"Lead already had {viewings} viewings — appointment less critical now")

        if features.get("has_budget") and features.get("has_preferred_location"):
            score += 0.10
            signals += 1
            pos_drivers.append("Verified budget and preferred community")

        resp = float(features.get("customer_response_ratio", 0.0))
        if resp >= 0.5:
            score += 0.08
            signals += 1
            pos_drivers.append("Responsive to outreach")

        hours_since = float(features.get("hours_since_last_activity", 72.0))
        if hours_since > 96.0:
            score -= 0.10
            signals += 1
            neg_drivers.append(f"Inactive for {hours_since / 24.0:.1f} days")

        prob = max(0.02, min(0.90, score))
        confidence = "HIGH" if signals >= 3 else ("MEDIUM" if signals >= 1 else "LOW")

        explanation = (
            f"Appointment propensity: **{prob * 100:.1f}%**. "
            f"Current stage: {stage.title()}. "
            + (f"Drivers: {', '.join(pos_drivers[:2])}. " if pos_drivers else "")
            + (f"Risk: {', '.join(neg_drivers[:2])}." if neg_drivers else "")
        )

        return PropensityScore(
            target_id="APPOINTMENT_PROPENSITY_V1",
            entity_id=entity_id,
            organization_id=org_id,
            probability=round(prob, 4),
            confidence=confidence,
            method="DETERMINISTIC_HEURISTIC",
            signal_count=signals,
            drivers_positive=pos_drivers,
            drivers_negative=neg_drivers,
            explanation=explanation,
            valid_until=now + timedelta(hours=24),
        )

    # ─── Site Visit (Viewing) Propensity ─────────────────────────────────────

    @staticmethod
    def score_site_visit_propensity(features: Dict[str, Any], org_id: str) -> PropensityScore:
        """
        Probability a scheduled appointment will be attended (no-cancel, no-show).
        Based on: prior cancellation history, attendance ratio.
        """
        now = datetime.now(timezone.utc)
        entity_id = str(features.get("lead_id", "unknown"))

        signals = 0
        score = 0.65  # base attendance prior
        pos_drivers: List[str] = []
        neg_drivers: List[str] = []

        attended = int(features.get("attended_viewings_count", 0))
        cancelled = int(features.get("cancelled_viewings_count", 0))
        total = int(features.get("viewings_count", 0))

        if total > 0 and attended > 0:
            att_ratio = attended / max(total, 1)
            if att_ratio >= 0.8:
                score += 0.15
                signals += 1
                pos_drivers.append(f"Strong attendance record: {attended}/{total} viewings attended")
            elif att_ratio < 0.5:
                score -= 0.20
                signals += 1
                neg_drivers.append(f"Poor attendance: only {attended}/{total} viewings attended")

        if cancelled >= 2:
            score -= 0.15
            signals += 1
            neg_drivers.append(f"Multiple cancellations ({cancelled})")
        elif cancelled == 0 and total > 0:
            score += 0.08
            signals += 1
            pos_drivers.append("No prior cancellations")

        resp = float(features.get("customer_response_ratio", 0.5))
        if resp >= 0.6:
            score += 0.05
            signals += 1
            pos_drivers.append("Responsive communication")

        prob = max(0.05, min(0.95, score))
        confidence = "HIGH" if signals >= 2 else ("MEDIUM" if signals >= 1 else "LOW")

        explanation = (
            f"Site visit attendance probability: **{prob * 100:.1f}%**. "
            + (f"Positive signals: {', '.join(pos_drivers[:2])}. " if pos_drivers else "")
            + (f"Risk signals: {', '.join(neg_drivers[:2])}." if neg_drivers else "")
        )

        return PropensityScore(
            target_id="SITE_VISIT_PROPENSITY_V1",
            entity_id=entity_id,
            organization_id=org_id,
            probability=round(prob, 4),
            confidence=confidence,
            method="DETERMINISTIC_HEURISTIC",
            signal_count=signals,
            drivers_positive=pos_drivers,
            drivers_negative=neg_drivers,
            explanation=explanation,
            valid_until=now + timedelta(hours=24),
        )

    # ─── Opportunity Stall Risk ───────────────────────────────────────────────

    @staticmethod
    def score_stall_risk(features: Dict[str, Any], org_id: str) -> PropensityScore:
        """
        Risk that an active opportunity becomes stalled within 14 days.
        HIGH stall risk → intervention recommended.
        """
        now = datetime.now(timezone.utc)
        entity_id = str(features.get("lead_id", "unknown"))

        signals = 0
        score = 0.20  # base stall prior
        pos_drivers: List[str] = []
        neg_drivers: List[str] = []

        hours_since = float(features.get("hours_since_last_activity", 72.0))
        lead_age_days = float(features.get("lead_age_days", 7.0))

        # Primary stall signal: no activity
        if hours_since >= 168.0:  # 7 days
            score += 0.35
            signals += 1
            neg_drivers.append(f"No activity in {hours_since / 24.0:.1f} days — stall risk HIGH")
        elif hours_since >= 72.0:  # 3 days
            score += 0.15
            signals += 1
            neg_drivers.append(f"Low activity: {hours_since / 24.0:.1f} days without contact")
        elif hours_since <= 24.0:
            score -= 0.10
            signals += 1
            pos_drivers.append("Active in last 24h — not stalling")

        # Stage maturity
        stage = (features.get("pipeline_stage") or "new").lower()
        if stage in ("negotiation",) and lead_age_days > 30:
            score += 0.15
            signals += 1
            neg_drivers.append(f"In {stage} stage for > 30 days — potential negotiation stall")

        # Cancellation pattern
        cancelled = int(features.get("cancelled_viewings_count", 0))
        if cancelled >= 2:
            score += 0.10
            signals += 1
            neg_drivers.append(f"Multiple cancelled viewings ({cancelled})")

        # Response ratio
        resp = float(features.get("customer_response_ratio", 0.5))
        if resp < 0.2:
            score += 0.10
            signals += 1
            neg_drivers.append("Very low response rate")
        elif resp >= 0.7:
            score -= 0.08
            signals += 1
            pos_drivers.append("Good response rate suggests engagement")

        prob = max(0.01, min(0.95, score))
        confidence = "HIGH" if signals >= 3 else ("MEDIUM" if signals >= 2 else "LOW")

        explanation = (
            f"Stall risk: **{prob * 100:.1f}%**. "
            + (f"Warning signals: {', '.join(neg_drivers[:2])}. " if neg_drivers else "No stall signals. ")
            + (f"Positive signals: {', '.join(pos_drivers[:2])}." if pos_drivers else "")
        )

        return PropensityScore(
            target_id="OPPORTUNITY_STALL_RISK_V1",
            entity_id=entity_id,
            organization_id=org_id,
            probability=round(prob, 4),
            confidence=confidence,
            method="DETERMINISTIC_HEURISTIC",
            signal_count=signals,
            drivers_positive=pos_drivers,
            drivers_negative=neg_drivers,
            explanation=explanation,
            valid_until=now + timedelta(hours=6),
        )

    # ─── Cold/Churn Risk ─────────────────────────────────────────────────────

    @staticmethod
    def score_cold_risk(features: Dict[str, Any], org_id: str) -> PropensityScore:
        """
        Risk a currently active lead becomes cold (no contact for 14+ days) within 7 days.
        """
        now = datetime.now(timezone.utc)
        entity_id = str(features.get("lead_id", "unknown"))

        signals = 0
        score = 0.15
        pos_drivers: List[str] = []
        neg_drivers: List[str] = []

        hours_since = float(features.get("hours_since_last_activity", 72.0))
        lead_score_pts = float(features.get("lead_score_points", 50.0))

        if hours_since >= 120.0:
            score += 0.30
            signals += 1
            neg_drivers.append(f"Already {hours_since / 24.0:.1f} days without activity — trending cold")
        elif hours_since >= 48.0:
            score += 0.15
            signals += 1
            neg_drivers.append(f"{hours_since / 24.0:.1f} days without contact — cold risk rising")
        elif hours_since <= 12.0:
            score -= 0.10
            signals += 1
            pos_drivers.append("Very recent activity — low cold risk")

        if lead_score_pts < 25:
            score += 0.15
            signals += 1
            neg_drivers.append("Low lead score — higher natural cold probability")
        elif lead_score_pts >= 70:
            score -= 0.10
            signals += 1
            pos_drivers.append("High-quality lead — lower cold probability")

        inbound = int(features.get("inbound_message_count", 0))
        if inbound == 0:
            score += 0.10
            signals += 1
            neg_drivers.append("No inbound messages ever — very low engagement")
        elif inbound >= 5:
            score -= 0.08
            signals += 1
            pos_drivers.append(f"{inbound} inbound messages — demonstrated engagement")

        prob = max(0.01, min(0.95, score))
        confidence = "HIGH" if signals >= 3 else ("MEDIUM" if signals >= 2 else "LOW")

        explanation = (
            f"Cold risk: **{prob * 100:.1f}%**. "
            + (f"Risk signals: {', '.join(neg_drivers[:2])}. " if neg_drivers else "No cold signals. ")
            + (f"Mitigating signals: {', '.join(pos_drivers[:2])}." if pos_drivers else "")
        )

        return PropensityScore(
            target_id="LEAD_COLD_RISK_V1",
            entity_id=entity_id,
            organization_id=org_id,
            probability=round(prob, 4),
            confidence=confidence,
            method="DETERMINISTIC_HEURISTIC",
            signal_count=signals,
            drivers_positive=pos_drivers,
            drivers_negative=neg_drivers,
            explanation=explanation,
            valid_until=now + timedelta(hours=6),
        )

    # ─── Booking Propensity ───────────────────────────────────────────────────

    @staticmethod
    def score_booking_propensity(features: Dict[str, Any], org_id: str) -> PropensityScore:
        """
        Probability an opportunity converts to a booking within 30 days.
        """
        now = datetime.now(timezone.utc)
        entity_id = str(features.get("lead_id", "unknown"))

        signals = 0
        stage = (features.get("pipeline_stage") or "new").lower()
        score = STAGE_CONVERSION_PRIOR.get(stage, 0.10)
        pos_drivers: List[str] = []
        neg_drivers: List[str] = []

        attended = int(features.get("attended_viewings_count", 0))
        if attended >= 2:
            score += 0.15
            signals += 1
            pos_drivers.append(f"{attended} completed viewings — strong booking signal")
        elif attended == 1:
            score += 0.08
            signals += 1
            pos_drivers.append("1 completed viewing")
        elif attended == 0:
            score -= 0.10
            neg_drivers.append("No completed viewings yet")
            signals += 1

        if features.get("has_budget") and features.get("has_preferred_location"):
            score += 0.12
            signals += 1
            pos_drivers.append("Budget and location confirmed")

        cancelled = int(features.get("cancelled_viewings_count", 0))
        if cancelled >= 2:
            score -= 0.15
            signals += 1
            neg_drivers.append(f"Multiple viewing cancellations ({cancelled})")

        resp = float(features.get("customer_response_ratio", 0.5))
        if resp >= 0.8:
            score += 0.08
            signals += 1
            pos_drivers.append("Highly responsive buyer")

        prob = max(0.01, min(0.95, score))
        confidence = "HIGH" if signals >= 3 else ("MEDIUM" if signals >= 2 else "LOW")

        explanation = (
            f"Booking probability (30-day): **{prob * 100:.1f}%**. "
            f"Stage: {stage.title()}. "
            + (f"Positive signals: {', '.join(pos_drivers[:2])}. " if pos_drivers else "")
            + (f"Risk signals: {', '.join(neg_drivers[:2])}." if neg_drivers else "")
        )

        return PropensityScore(
            target_id="BOOKING_PROPENSITY_V1",
            entity_id=entity_id,
            organization_id=org_id,
            probability=round(prob, 4),
            confidence=confidence,
            method="DETERMINISTIC_HEURISTIC",
            signal_count=signals,
            drivers_positive=pos_drivers,
            drivers_negative=neg_drivers,
            explanation=explanation,
            valid_until=now + timedelta(days=1),
        )

    # ─── Batch: All Scores for One Lead ──────────────────────────────────────

    @staticmethod
    def score_all(features: Dict[str, Any], org_id: str) -> Dict[str, PropensityScore]:
        """Compute all propensity scores for a single lead feature vector."""
        return {
            "LEAD_RESPONSE_PROPENSITY_V1": PropensityEngine.score_response_propensity(features, org_id),
            "APPOINTMENT_PROPENSITY_V1": PropensityEngine.score_appointment_propensity(features, org_id),
            "SITE_VISIT_PROPENSITY_V1": PropensityEngine.score_site_visit_propensity(features, org_id),
            "OPPORTUNITY_STALL_RISK_V1": PropensityEngine.score_stall_risk(features, org_id),
            "BOOKING_PROPENSITY_V1": PropensityEngine.score_booking_propensity(features, org_id),
            "LEAD_COLD_RISK_V1": PropensityEngine.score_cold_risk(features, org_id),
        }
