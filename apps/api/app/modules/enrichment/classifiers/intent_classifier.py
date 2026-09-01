"""
Volume 2 PART 2 — Intent Classifier
"""
from typing import Dict, Any, Optional


class IntentClassifier:
    @staticmethod
    def classify(intent_data: Dict[str, Any], notes_text: Optional[str] = None) -> Dict[str, Any]:
        purpose = intent_data.get("purpose")
        timeline = intent_data.get("timeline")
        urgency = intent_data.get("urgency")

        text = (notes_text or "").lower()

        if not purpose:
            if any(w in text for w in ["roi", "tenant", "rent out", "invest"]):
                purpose = "investment"
            elif any(w in text for w in ["live", "move in", "my family", "own house"]):
                purpose = "end_user"
            else:
                purpose = "end_user"  # Default assumption in UAE real estate

        if not timeline:
            if "immediate" in text or "urgent" in text:
                timeline = "immediate"
                urgency = "high"
            elif "month" in text:
                timeline = "1_month"
                urgency = "medium"
            else:
                timeline = "3_months"
                urgency = "medium"

        # Intent score calculation (0.0 - 1.0)
        score = 0.5
        if urgency == "high" or timeline == "immediate":
            score += 0.4
        elif timeline == "1_month":
            score += 0.3
        elif timeline == "3_months":
            score += 0.2

        if purpose == "investment":
            score += 0.1

        return {
            "purpose": purpose,
            "timeline": timeline,
            "urgency": urgency or "medium",
            "intent_score": min(1.0, round(score, 2)),
            "confidence": 0.88
        }
