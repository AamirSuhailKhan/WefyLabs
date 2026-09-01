"""
Fuzzy Matcher — Levenshtein edit distance and Jaro-Winkler similarity.
Pure Python implementations — no external dependencies required for tests.
Optional: will use 'python-Levenshtein' and 'jellyfish' if installed (10-100x faster).
"""
from typing import Optional
from .base_algorithm import BaseSimilarityAlgorithm


# ─── Pure Python Levenshtein ──────────────────────────────────────────────────
def _levenshtein_ratio(s1: str, s2: str) -> float:
    """Returns normalized Levenshtein similarity: 1 - (edit_distance / max_len)."""
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0
    m, n = len(s1), len(s2)
    # DP matrix
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if s1[i - 1] == s2[j - 1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j - 1])
            prev = temp
    distance = dp[n]
    return 1.0 - (distance / max(m, n))


# ─── Pure Python Jaro-Winkler ─────────────────────────────────────────────────
def _jaro(s1: str, s2: str) -> float:
    """Pure Python Jaro similarity."""
    if s1 == s2:
        return 1.0
    len_s1, len_s2 = len(s1), len(s2)
    if len_s1 == 0 or len_s2 == 0:
        return 0.0
    match_distance = max(len_s1, len_s2) // 2 - 1
    match_distance = max(match_distance, 0)
    s1_matches = [False] * len_s1
    s2_matches = [False] * len_s2
    matches = 0
    transpositions = 0
    for i in range(len_s1):
        start = max(0, i - match_distance)
        end = min(i + match_distance + 1, len_s2)
        for j in range(start, end):
            if s2_matches[j] or s1[i] != s2[j]:
                continue
            s1_matches[i] = True
            s2_matches[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0
    k = 0
    for i in range(len_s1):
        if not s1_matches[i]:
            continue
        while not s2_matches[k]:
            k += 1
        if s1[i] != s2[k]:
            transpositions += 1
        k += 1
    return (matches / len_s1 + matches / len_s2 + (matches - transpositions / 2) / matches) / 3


def _jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:
    """Pure Python Jaro-Winkler similarity. p = prefix scaling factor (max 0.25)."""
    jaro_score = _jaro(s1, s2)
    prefix = 0
    for c1, c2 in zip(s1, s2):
        if c1 == c2:
            prefix += 1
        else:
            break
        if prefix == 4:
            break
    return jaro_score + (prefix * p * (1 - jaro_score))


class LevenshteinMatcher(BaseSimilarityAlgorithm):
    """
    Levenshtein edit-distance based fuzzy matcher.
    Best for catching typos, transpositions, and minor spelling variations.
    Uses 'python-Levenshtein' if available, falls back to pure Python.
    """
    name = "levenshtein"

    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold

    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        if not value_a or not value_b:
            return 0.0
        try:
            import Levenshtein
            ratio = Levenshtein.ratio(value_a.lower(), value_b.lower())
        except ImportError:
            ratio = _levenshtein_ratio(value_a.lower(), value_b.lower())
        return ratio if ratio >= self.threshold else ratio * 0.5


class JaroWinklerMatcher(BaseSimilarityAlgorithm):
    """
    Jaro-Winkler fuzzy matcher — best for human names with prefix agreement.
    Handles transliteration variations: "Ahmed" vs "Ahmad", "Mohammed" vs "Muhammad".
    Uses 'jellyfish' if available, falls back to pure Python.
    """
    name = "jaro_winkler"
    supports_fields = ["name", "first_name", "last_name", "full_name"]

    def __init__(self, threshold: float = 0.85):
        self.threshold = threshold

    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        if not value_a or not value_b:
            return 0.0
        try:
            import jellyfish
            ratio = jellyfish.jaro_winkler_similarity(value_a.lower(), value_b.lower())
        except ImportError:
            ratio = _jaro_winkler(value_a.lower(), value_b.lower())
        return ratio if ratio >= self.threshold else ratio * 0.4
