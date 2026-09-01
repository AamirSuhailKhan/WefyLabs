"""
Conversion Predictor — Conversion & Probability Engine
======================================================
Predicts milestone probabilities (closing, meeting, viewing, response, churn, referral)
and risk scores based on feature vector inputs.
"""
from typing import Dict, Any, Tuple


class ConversionPredictor:
    """
    Computes probabilities (0.0 - 1.0) for milestone events and risk score.
    """

    def predict(self, lead_score: float, features: Dict[str, Any]) -> Dict[str, Any]:
        base_prob = min(0.95, max(0.05, lead_score / 100.0))

        # Response probability (higher for recent active leads)
        response_prob = base_prob * 0.9
        if features.get("has_phone") and features.get("has_email"):
            response_prob = min(0.98, response_prob + 0.15)

        # Meeting & Viewing probability
        viewing_prob = min(0.98, base_prob * 1.1) if features.get("has_viewing_booked") else base_prob * 0.6
        meeting_prob = min(0.98, base_prob * 1.05) if features.get("meeting_count", 0) > 0 else base_prob * 0.5

        # Closing probability
        closing_prob = round(base_prob * 0.85, 4)
        if features.get("is_cash_buyer") or features.get("has_mortgage_preapproval"):
            closing_prob = min(0.95, round(closing_prob + 0.20, 4))

        # Churn probability (inverse of engagement)
        lead_age = float(features.get("lead_age_days") or 0.0)
        activity = int(features.get("activity_count") or 0)
        churn_prob = 0.1
        if lead_age > 21 and activity == 0:
            churn_prob = 0.75
        elif lead_age > 14 and activity <= 1:
            churn_prob = 0.45

        # Risk score (0 - 100)
        risk_score = round(churn_prob * 100.0, 1)

        # Predicted timeline
        timeline_pred = features.get("timeline") or "3_months"
        if features.get("is_immediate"):
            timeline_pred = "immediate"

        return {
            "conversion_probability": round(base_prob, 4),
            "closing_probability": closing_prob,
            "response_probability": round(response_prob, 4),
            "meeting_probability": round(meeting_prob, 4),
            "viewing_probability": round(viewing_prob, 4),
            "churn_probability": round(churn_prob, 4),
            "referral_probability": round(min(0.50, base_prob * 0.3), 4),
            "buying_timeline_predicted": timeline_pred,
            "investment_potential_tier": "ultra_high" if features.get("is_luxury") else ("high" if features.get("is_high_value") else "medium"),
            "risk_score": risk_score,
        }
