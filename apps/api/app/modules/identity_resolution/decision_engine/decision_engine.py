"""
Decision Engine — Evaluates final confidence against configurable thresholds.
Produces a decision: auto_merge | manual_review | new_identity.
Thresholds are configurable per organization (defaults: 0.95 / 0.85).
"""
from typing import Dict, Any, Tuple


# ─── Default Thresholds ───────────────────────────────────────────────────────
DEFAULT_AUTO_MERGE_THRESHOLD = 0.95
DEFAULT_MANUAL_REVIEW_THRESHOLD = 0.85


class DecisionEngine:
    """
    Evaluates match confidence against configured thresholds.

    Decision logic:
        confidence >= auto_merge_threshold  →  auto_merge
        confidence >= manual_review_threshold  →  manual_review
        confidence < manual_review_threshold  →  new_identity
    """

    def __init__(
        self,
        auto_merge_threshold: float = DEFAULT_AUTO_MERGE_THRESHOLD,
        manual_review_threshold: float = DEFAULT_MANUAL_REVIEW_THRESHOLD,
    ):
        self.auto_merge_threshold = auto_merge_threshold
        self.manual_review_threshold = manual_review_threshold

    def decide(self, confidence: float, candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a single candidate's confidence and return a decision record.

        Returns:
            {
                "decision": "auto_merge" | "manual_review" | "new_identity",
                "confidence": 0.94,
                "threshold_used": 0.95,
                "candidate_identity_id": "abc123",
            }
        """
        if confidence >= self.auto_merge_threshold:
            decision = "auto_merge"
        elif confidence >= self.manual_review_threshold:
            decision = "manual_review"
        else:
            decision = "new_identity"

        return {
            "decision": decision,
            "confidence": confidence,
            "threshold_used": self.auto_merge_threshold,
            "candidate_identity_id": candidate.get("id"),
        }

    def decide_best(self, candidates_with_confidence: list) -> Dict[str, Any]:
        """
        Given a list of (candidate_dict, confidence) tuples,
        picks the highest-confidence match and decides.
        Returns new_identity if no candidates provided.
        """
        if not candidates_with_confidence:
            return {"decision": "new_identity", "confidence": 0.0, "candidate_identity_id": None, "threshold_used": self.auto_merge_threshold}

        # Sort by confidence descending, pick best
        sorted_candidates = sorted(candidates_with_confidence, key=lambda x: x[1], reverse=True)
        best_candidate, best_confidence = sorted_candidates[0]

        return self.decide(best_confidence, best_candidate)

    def update_thresholds(self, auto_merge: float, manual_review: float):
        """Allow runtime reconfiguration of thresholds (e.g., per-organization settings)."""
        if 0.0 <= manual_review < auto_merge <= 1.0:
            self.auto_merge_threshold = auto_merge
            self.manual_review_threshold = manual_review
