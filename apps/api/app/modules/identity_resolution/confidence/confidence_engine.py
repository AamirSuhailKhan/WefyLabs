"""
Confidence Engine — Aggregates per-field similarity scores into a final match confidence.
Handles sparse records by normalizing weights across present fields only.
"""
from typing import Dict, Any, List


class ConfidenceEngine:
    """
    Aggregates per-field similarity scores into a final weighted confidence value.

    Key design decisions:
    - Weights are normalized across PRESENT fields only (sparse records handled fairly)
    - High-signal field (email/phone exact match) can boost overall confidence
    - Returns confidence in [0.0, 1.0]
    """

    # Fields considered "high signal" — exact match on any of these boosts confidence
    HIGH_SIGNAL_FIELDS = {"email", "phone", "whatsapp"}
    HIGH_SIGNAL_BOOST = 0.05  # Added to confidence if any high-signal field is an exact match

    def compute(self, similarity_result: Dict[str, Any]) -> float:
        """
        Takes the output of SimilarityEngine.compute() and returns final confidence [0.0, 1.0].

        Confidence = Σ(field_score × weight) / Σ(weights for present fields)
        + optional high-signal boost
        """
        per_field_scores = similarity_result.get("per_field_scores", {})
        weights_used = similarity_result.get("weights_used", {})

        if not per_field_scores or not weights_used:
            return 0.0

        total_weight = sum(weights_used.values())
        if total_weight == 0:
            return 0.0

        weighted_sum = sum(
            per_field_scores.get(field, 0.0) * weight
            for field, weight in weights_used.items()
        )
        confidence = weighted_sum / total_weight

        # High-signal boost: if phone or email is exact match
        boost = 0.0
        for field in self.HIGH_SIGNAL_FIELDS:
            if per_field_scores.get(field, 0.0) >= 0.99:
                boost = self.HIGH_SIGNAL_BOOST
                break

        return min(1.0, round(confidence + boost, 4))

    @staticmethod
    def build_explanation(
        similarity_result: Dict[str, Any],
        final_confidence: float,
        decision: str,
    ) -> str:
        """
        Generates a human-readable explanation of the match decision.
        Used in ManualReview.ai_explanation and DuplicateCandidate.reason.
        """
        matched = similarity_result.get("matched_fields", [])
        reason = similarity_result.get("reason", "")
        per_scores = similarity_result.get("per_field_scores", {})

        explanation_parts = [
            f"Identity match confidence: {final_confidence:.1%}",
            f"Decision: {decision.upper().replace('_', ' ')}",
        ]

        if matched:
            explanation_parts.append(f"Matched fields: {', '.join(matched)}")

        high_scores = [
            f"{field} ({score:.0%})"
            for field, score in per_scores.items()
            if score >= 0.8
        ]
        if high_scores:
            explanation_parts.append(f"Strong signals: {', '.join(high_scores)}")

        if reason:
            explanation_parts.append(f"Details: {reason}")

        if decision == "auto_merge":
            explanation_parts.append("Action: Automatic merge executed — confidence exceeds threshold.")
        elif decision == "manual_review":
            explanation_parts.append("Action: Queued for manual review — confidence is high but below auto-merge threshold.")
        else:
            explanation_parts.append("Action: Created as new identity — insufficient match confidence.")

        return " | ".join(explanation_parts)
