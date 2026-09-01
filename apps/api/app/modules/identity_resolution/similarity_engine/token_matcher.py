"""
Token Matcher — Token Set Ratio, Token Sort Ratio, and N-Gram similarity.
Best for: reordered names ("Ahmed Raza" vs "Raza Ahmed"), company names, addresses.
Pure Python implementations — no external dependencies.
Optional: uses 'rapidfuzz' if installed for 10x speed.
"""
import re
from typing import Optional, Set
from .base_algorithm import BaseSimilarityAlgorithm


# ─── Pure Python Token utilities ─────────────────────────────────────────────
def _tokenize(s: str) -> list:
    return sorted(re.findall(r"\w+", s.lower()))


def _token_sort_ratio(s1: str, s2: str) -> float:
    """Sorts tokens alphabetically then computes character-level similarity."""
    from .fuzzy_matcher import _levenshtein_ratio
    t1 = " ".join(_tokenize(s1))
    t2 = " ".join(_tokenize(s2))
    return _levenshtein_ratio(t1, t2)


def _token_set_ratio(s1: str, s2: str) -> float:
    """
    Finds intersection and sorted remainders.
    Handles: "John Smith" vs "Smith John Dr." → handles extra tokens gracefully.
    """
    from .fuzzy_matcher import _levenshtein_ratio
    tokens1 = set(re.findall(r"\w+", s1.lower()))
    tokens2 = set(re.findall(r"\w+", s2.lower()))
    intersection = sorted(tokens1 & tokens2)
    remainder1 = sorted(tokens1 - tokens2)
    remainder2 = sorted(tokens2 - tokens1)

    inter_str = " ".join(intersection)
    str1 = (inter_str + " " + " ".join(remainder1)).strip()
    str2 = (inter_str + " " + " ".join(remainder2)).strip()

    if not inter_str:
        return _levenshtein_ratio(s1.lower(), s2.lower())

    return max(
        _levenshtein_ratio(inter_str, str1),
        _levenshtein_ratio(inter_str, str2),
        _levenshtein_ratio(str1, str2),
    )


def _ngram_similarity(s1: str, s2: str, n: int = 3) -> float:
    """Jaccard coefficient on character n-grams."""
    def ngrams(s: str) -> Set[str]:
        s = s.lower().strip()
        return {s[i:i+n] for i in range(len(s) - n + 1)} if len(s) >= n else {s}

    g1 = ngrams(s1)
    g2 = ngrams(s2)
    if not g1 and not g2:
        return 1.0
    if not g1 or not g2:
        return 0.0
    intersection = len(g1 & g2)
    union = len(g1 | g2)
    return intersection / union


class TokenSortMatcher(BaseSimilarityAlgorithm):
    """
    Token Sort Ratio — sorts tokens alphabetically then compares.
    Best for: "Raza Ahmed Khan" vs "Ahmed Khan Raza" (same tokens, different order).
    """
    name = "token_sort"
    supports_fields = ["name", "full_name", "company", "address"]

    def __init__(self, threshold: float = 0.80):
        self.threshold = threshold

    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        if not value_a or not value_b:
            return 0.0
        try:
            from rapidfuzz import fuzz
            ratio = fuzz.token_sort_ratio(value_a, value_b) / 100.0
        except ImportError:
            ratio = _token_sort_ratio(value_a, value_b)
        return ratio if ratio >= self.threshold else ratio * 0.5


class TokenSetMatcher(BaseSimilarityAlgorithm):
    """
    Token Set Ratio — finds intersection of tokens then compares substrings.
    Best for: "Mr. Ahmed Raza" vs "Ahmed Raza" (extra tokens handled gracefully).
    """
    name = "token_set"
    supports_fields = ["name", "full_name", "company", "address"]

    def __init__(self, threshold: float = 0.80):
        self.threshold = threshold

    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        if not value_a or not value_b:
            return 0.0
        try:
            from rapidfuzz import fuzz
            ratio = fuzz.token_set_ratio(value_a, value_b) / 100.0
        except ImportError:
            ratio = _token_set_ratio(value_a, value_b)
        return ratio if ratio >= self.threshold else ratio * 0.5


class NGramMatcher(BaseSimilarityAlgorithm):
    """
    N-Gram character similarity using Jaccard coefficient.
    Best for: company names, addresses, short strings with character overlap.
    """
    name = "ngram"
    supports_fields = ["company", "address", "city"]

    def __init__(self, n: int = 3, threshold: float = 0.70):
        self.n = n
        self.threshold = threshold

    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        if not value_a or not value_b:
            return 0.0
        ratio = _ngram_similarity(value_a, value_b, self.n)
        return ratio if ratio >= self.threshold else ratio * 0.4
