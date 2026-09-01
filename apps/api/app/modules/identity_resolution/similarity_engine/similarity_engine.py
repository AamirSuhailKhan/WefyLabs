"""
Similarity Engine — Plugin registry and weighted multi-field confidence aggregator.
Orchestrates all algorithms across all comparable fields.
Produces a DuplicateCandidate confidence score with full field-by-field explainability.
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
from .base_algorithm import BaseSimilarityAlgorithm
from .exact_matcher import ExactMatcher, NormalizedPhoneMatcher, NormalizedEmailMatcher
from .fuzzy_matcher import LevenshteinMatcher, JaroWinklerMatcher
from .phonetic_matcher import SoundexMatcher, DoubleMetaphoneMatcher
from .token_matcher import TokenSortMatcher, TokenSetMatcher, NGramMatcher

logger = logging.getLogger(__name__)


# ─── Default Field Weights ─────────────────────────────────────────────────────
# Total weight = 1.0 (normalized across present fields at runtime)
DEFAULT_FIELD_WEIGHTS: Dict[str, float] = {
    "email":     0.35,
    "phone":     0.30,
    "name":      0.15,
    "whatsapp":  0.08,
    "telegram":  0.04,
    "company":   0.04,
    "city":      0.02,
    "country":   0.02,
}

# ─── Field → Algorithm Cascade (ordered: fastest/most-certain first) ──────────
FIELD_ALGORITHM_MAP: Dict[str, List[str]] = {
    "email":     ["normalized_email", "exact"],
    "phone":     ["normalized_phone", "exact"],
    "whatsapp":  ["normalized_phone", "exact"],
    "telegram":  ["exact"],
    "name":      ["jaro_winkler", "token_sort", "token_set", "double_metaphone", "soundex", "levenshtein"],
    "company":   ["token_set", "ngram", "levenshtein"],
    "city":      ["exact", "ngram"],
    "country":   ["exact"],
}


class SimilarityEngine:
    """
    Plugin registry and weighted multi-field similarity aggregator.

    Usage:
        engine = SimilarityEngine()
        result = engine.compute(lead_data, identity_data)
        # result = {"confidence": 0.94, "per_field_scores": {...}, ...}

    New algorithms can be registered without redesign:
        engine.register_algorithm(MyNewAlgorithm())
    """

    def __init__(self, field_weights: Optional[Dict[str, float]] = None):
        self.field_weights = field_weights or DEFAULT_FIELD_WEIGHTS
        self._algorithms: Dict[str, BaseSimilarityAlgorithm] = {}
        self._register_defaults()

    def _register_defaults(self):
        algorithms = [
            ExactMatcher(),
            NormalizedPhoneMatcher(),
            NormalizedEmailMatcher(),
            LevenshteinMatcher(),
            JaroWinklerMatcher(),
            SoundexMatcher(),
            DoubleMetaphoneMatcher(),
            TokenSortMatcher(),
            TokenSetMatcher(),
            NGramMatcher(),
        ]
        for algo in algorithms:
            self._algorithms[algo.name] = algo

    def register_algorithm(self, algorithm: BaseSimilarityAlgorithm):
        """Register a new algorithm. Plugin extension point."""
        self._algorithms[algorithm.name] = algorithm
        logger.info(f"[SIMILARITY_ENGINE] Registered algorithm: {algorithm.name}")

    def compute(
        self,
        lead_data: Dict[str, Any],
        identity_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compute weighted multi-field similarity between incoming lead and existing identity.

        Returns:
            {
                "confidence": 0.94,
                "matched_fields": ["email", "phone"],
                "per_field_scores": {"email": 1.0, "phone": 1.0, "name": 0.72},
                "weights_used": {"email": 0.35, "phone": 0.30},
                "algorithms_used": ["normalized_email", "normalized_phone"],
                "similarity_scores": [{"field": ..., "score": ..., "algorithm": ..., ...}],
                "reason": "Exact email match + Exact phone (E.164) match",
            }
        """
        per_field_scores: Dict[str, float] = {}
        algorithms_used: List[str] = []
        similarity_scores: List[Dict[str, Any]] = []
        matched_fields: List[str] = []
        reason_parts: List[str] = []

        # Determine which fields are present in both records
        present_fields = [
            field for field in self.field_weights
            if lead_data.get(field) and identity_data.get(field)
        ]

        if not present_fields:
            return self._no_match_result()

        # Compute per-field scores using algorithm cascade
        for field in present_fields:
            val_a = str(lead_data[field]).strip()
            val_b = str(identity_data[field]).strip()
            best_score = 0.0
            best_algo = "none"

            algo_names = FIELD_ALGORITHM_MAP.get(field, ["exact", "levenshtein"])
            for algo_name in algo_names:
                algo = self._algorithms.get(algo_name)
                if not algo:
                    continue
                try:
                    s = algo.score(val_a, val_b)
                    if s > best_score:
                        best_score = s
                        best_algo = algo_name
                except Exception as e:
                    logger.warning(f"[SIMILARITY_ENGINE] Algorithm {algo_name} failed on field {field}: {e}")

            per_field_scores[field] = best_score
            weight = self.field_weights[field]

            similarity_scores.append({
                "field_name": field,
                "value_a": val_a,
                "value_b": val_b,
                "score": best_score,
                "weight": weight,
                "algorithm": best_algo,
                "weighted_contribution": best_score * weight,
            })

            if best_algo not in algorithms_used:
                algorithms_used.append(best_algo)

            if best_score >= 0.8:
                matched_fields.append(field)
                reason_parts.append(f"{field.title()} match ({best_algo}, {best_score:.2f})")

        # Normalize weights to present fields
        total_weight = sum(self.field_weights[f] for f in present_fields)
        if total_weight == 0:
            return self._no_match_result()

        confidence = sum(
            per_field_scores[f] * self.field_weights[f]
            for f in present_fields
        ) / total_weight

        weights_used = {f: self.field_weights[f] for f in present_fields}

        return {
            "confidence": round(confidence, 4),
            "matched_fields": matched_fields,
            "per_field_scores": per_field_scores,
            "weights_used": weights_used,
            "algorithms_used": algorithms_used,
            "similarity_scores": similarity_scores,
            "reason": " | ".join(reason_parts) if reason_parts else "No strong field matches",
        }

    @staticmethod
    def _no_match_result() -> Dict[str, Any]:
        return {
            "confidence": 0.0,
            "matched_fields": [],
            "per_field_scores": {},
            "weights_used": {},
            "algorithms_used": [],
            "similarity_scores": [],
            "reason": "No comparable fields found",
        }
