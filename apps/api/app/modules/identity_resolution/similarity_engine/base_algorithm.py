"""
Base Similarity Algorithm — Abstract base class for all matching algorithms.
All algorithms implement score(a, b) -> float (0.0 - 1.0).
Plugin registry pattern: add new algorithms without redesign.
"""
from abc import ABC, abstractmethod
from typing import Optional


class BaseSimilarityAlgorithm(ABC):
    """
    Abstract base for all similarity algorithms.
    Each algorithm must implement score() returning 0.0 (no match) to 1.0 (exact match).
    """
    name: str = "base"
    supports_fields: list = []  # Empty = supports any field

    @abstractmethod
    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        """
        Compute similarity score between two string values.
        Returns float in [0.0, 1.0].
        Both values are pre-normalized by the caller before passing here.
        """
        pass

    def is_applicable(self, field_name: str) -> bool:
        """Returns True if this algorithm is applicable to the given field."""
        if not self.supports_fields:
            return True
        return field_name in self.supports_fields
