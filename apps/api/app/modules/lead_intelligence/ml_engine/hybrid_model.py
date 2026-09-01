"""
Rule Plus ML Hybrid Model — Default Production Model
====================================================
Combines rule adjustments with statistical feature weights to compute the final lead score (0-100).
Calculates feature-level SHAP/weight contributions for Explainable AI.
"""
from typing import Dict, Any
from .base_model import BaseMLModel


class RulePlusMLHybridModel(BaseMLModel):
    version = "v1.0.0-hybrid"
    model_name = "hybrid_rule_ml"

    # Default statistical feature weights
    FEATURE_WEIGHTS: Dict[str, float] = {
        "quality_score": 0.25,
        "field_completion_rate": 15.0,
        "has_phone": 10.0,
        "has_email": 5.0,
        "activity_count": 3.0,
        "meeting_count": 8.0,
    }

    def predict(self, features: Dict[str, Any], rule_adjustment: float = 0.0) -> Dict[str, Any]:
        base_score = float(features.get("quality_score") or 50.0) * 0.4
        contributions = {}

        # Add feature weight contributions
        for feat_name, weight in self.FEATURE_WEIGHTS.items():
            val = features.get(feat_name)
            if isinstance(val, bool) and val:
                base_score += weight
                contributions[feat_name] = weight
            elif isinstance(val, (int, float)) and val > 0:
                added = min(20.0, float(val) * weight)
                base_score += added
                contributions[feat_name] = added

        # Add rule adjustments
        raw_score = base_score + rule_adjustment
        contributions["rule_adjustments"] = rule_adjustment

        final_score = max(0.0, min(100.0, round(raw_score, 1)))

        # Confidence is higher when profile completeness is high
        completeness = float(features.get("field_completion_rate") or 0.5)
        confidence = round(min(0.98, max(0.50, 0.60 + (completeness * 0.35))), 2)

        return {
            "raw_score": final_score,
            "confidence": confidence,
            "model_version": self.version,
            "feature_contributions": contributions,
        }
