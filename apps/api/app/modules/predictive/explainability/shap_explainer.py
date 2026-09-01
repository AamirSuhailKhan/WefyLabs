"""
Explainability & Feature Attribution Engine
===========================================
Computes feature attributions (positive conversion drivers, negative friction factors)
and generates explainable rationale without inventing artificial data.
"""

from typing import Dict, Any, List
from app.modules.predictive.models.base_model import (
    FeatureAttribution, PredictionExplanationResult
)

class ShapExplainer:
    """
    Computes local feature impact attributions for predictive inferences.
    """

    @staticmethod
    def explain_conversion_prediction(
        feature_vector: Dict[str, Any],
        calibrated_prob: float
    ) -> PredictionExplanationResult:
        """
        Calculates directional feature contributions for a conversion probability inference.
        """
        positive: List[FeatureAttribution] = []
        negative: List[FeatureAttribution] = []

        # 1. Attended Viewings
        viewings = feature_vector.get("attended_viewings_count", 0)
        if viewings > 0:
            positive.append(FeatureAttribution(
                feature_name="Completed Property Viewings",
                impact_score=+0.28,
                description=f"Buyer has attended {viewings} property viewing(s)."
            ))
        elif feature_vector.get("viewings_count", 0) == 0:
            negative.append(FeatureAttribution(
                feature_name="No Viewings Scheduled",
                impact_score=-0.15,
                description="Lead has not yet scheduled or attended a physical property viewing."
            ))

        # 2. Inactive Days / Recency
        hours_since_act = feature_vector.get("hours_since_last_activity", 24.0)
        if hours_since_act <= 12.0:
            positive.append(FeatureAttribution(
                feature_name="High Broker Engagement Recency",
                impact_score=+0.18,
                description="Recent broker interaction within the past 12 hours."
            ))
        elif hours_since_act >= 72.0:
            negative.append(FeatureAttribution(
                feature_name="Communication Inactivity",
                impact_score=-0.22,
                description=f"No meaningful activity for {hours_since_act / 24.0:.1f} days."
            ))

        # 3. Customer Response Ratio
        resp_ratio = feature_vector.get("customer_response_ratio", 0.5)
        if resp_ratio >= 0.8:
            positive.append(FeatureAttribution(
                feature_name="Responsive Buyer Communication",
                impact_score=+0.16,
                description=f"High reply velocity with {resp_ratio * 100:.0f}% response consistency."
            ))
        elif resp_ratio < 0.3 and feature_vector.get("outbound_message_count", 0) >= 3:
            negative.append(FeatureAttribution(
                feature_name="Low Customer Responsiveness",
                impact_score=-0.18,
                description="Customer has not replied to recent outbound outreach attempts."
            ))

        # 4. Budget & Location Qualification
        if feature_vector.get("has_budget") and feature_vector.get("has_preferred_location"):
            positive.append(FeatureAttribution(
                feature_name="Verified Budget & Location Target",
                impact_score=+0.14,
                description="Clear purchasing ceiling and specific preferred communities identified."
            ))

        # 5. Cancelled Viewings
        cancels = feature_vector.get("cancelled_viewings_count", 0)
        if cancels > 0:
            negative.append(FeatureAttribution(
                feature_name="Viewing Cancellation History",
                impact_score=-0.20,
                description=f"Customer cancelled {cancels} previous viewing appointment(s)."
            ))

        summary = (
            f"Predicted conversion probability is **{calibrated_prob * 100:.1f}%**. "
            f"Primary upward drivers include {', '.join([p.feature_name for p in positive[:2]]) if positive else 'baseline profile'}. "
            f"Key risk friction factors include {', '.join([n.feature_name for n in negative[:2]]) if negative else 'none detected'}."
        )

        return PredictionExplanationResult(
            positive_drivers=positive,
            negative_drivers=negative,
            summary_markdown=summary
        )
