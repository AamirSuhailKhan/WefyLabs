"""
Phonetic Matcher — Soundex and Double Metaphone phonetic similarity.
Best for cross-language name matching: Arabic transliteration, Urdu names in English.
Pure Python implementations — no external dependencies.
"""
import re
from typing import Optional
from .base_algorithm import BaseSimilarityAlgorithm


# ─── Soundex (pure Python) ────────────────────────────────────────────────────
_SOUNDEX_TABLE = str.maketrans(
    "AEHIOUWY BFPV CGJKQSXZ DT L MN R".replace(" ", ""),
    "0000000001111222222223344555566"[: len("AEHIOUWY BFPV CGJKQSXZ DT L MN R".replace(" ", ""))]
)

_SOUNDEX_MAP = {
    "B": "1", "F": "1", "P": "1", "V": "1",
    "C": "2", "G": "2", "J": "2", "K": "2", "Q": "2", "S": "2", "X": "2", "Z": "2",
    "D": "3", "T": "3",
    "L": "4",
    "M": "5", "N": "5",
    "R": "6",
}


def _soundex(name: str) -> str:
    name = re.sub(r"[^a-zA-Z]", "", name).upper()
    if not name:
        return "0000"
    first = name[0]
    rest = ""
    prev_code = _SOUNDEX_MAP.get(first, "0")
    for ch in name[1:]:
        code = _SOUNDEX_MAP.get(ch, "0")
        if code != "0" and code != prev_code:
            rest += code
        prev_code = code
    code = (first + rest + "000")[:4]
    return code


# ─── Double Metaphone (simplified pure Python) ────────────────────────────────
def _double_metaphone_primary(name: str) -> str:
    """Simplified Double Metaphone — covers common Arabic/South Asian transliterations."""
    name = re.sub(r"[^a-zA-Z]", "", name).upper()
    if not name:
        return ""
    # Common substitution rules
    substitutions = [
        ("PH", "F"), ("CK", "K"), ("SCH", "SK"), ("TH", "T"),
        ("GN", "N"), ("KN", "N"), ("PN", "N"), ("AE", "E"),
        ("WR", "R"), ("MB", "M"), ("QU", "K"),
        # Arabic transliteration helpers
        ("KH", "K"), ("GH", "K"), ("CH", "K"),
        ("SH", "S"), ("ZH", "S"),
    ]
    for old, new in substitutions:
        name = name.replace(old, new)
    # Remove duplicate adjacent letters (except C)
    result = ""
    prev = ""
    for ch in name:
        if ch != prev or ch == "C":
            result += ch
        prev = ch
    # Remove trailing E, A
    result = re.sub(r"[AE]+$", "", result)
    return result[:6]  # Limit to 6 chars


class SoundexMatcher(BaseSimilarityAlgorithm):
    """
    Soundex phonetic matcher.
    Groups names with similar pronunciations regardless of spelling.
    Example: "Smith" and "Smyth" both encode to S530.
    """
    name = "soundex"
    supports_fields = ["name", "first_name", "last_name", "full_name"]

    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        if not value_a or not value_b:
            return 0.0
        try:
            import jellyfish
            code_a = jellyfish.soundex(value_a)
            code_b = jellyfish.soundex(value_b)
        except ImportError:
            code_a = _soundex(value_a)
            code_b = _soundex(value_b)
        if code_a == code_b:
            return 0.85
        # Partial soundex match (first 3 chars)
        if code_a[:3] == code_b[:3]:
            return 0.70
        return 0.0


class DoubleMetaphoneMatcher(BaseSimilarityAlgorithm):
    """
    Double Metaphone phonetic matcher.
    Better than Soundex for multi-cultural names (Arabic, South Asian, European).
    Handles: "Ahmed" ~ "Ahmad", "Mohammed" ~ "Muhammad", "Raza" ~ "Raaza".
    """
    name = "double_metaphone"
    supports_fields = ["name", "first_name", "last_name", "full_name"]

    def score(self, value_a: Optional[str], value_b: Optional[str]) -> float:
        if not value_a or not value_b:
            return 0.0
        try:
            import jellyfish
            code_a = jellyfish.metaphone(value_a)
            code_b = jellyfish.metaphone(value_b)
        except ImportError:
            code_a = _double_metaphone_primary(value_a)
            code_b = _double_metaphone_primary(value_b)
        if not code_a or not code_b:
            return 0.0
        if code_a == code_b:
            return 0.85
        # Prefix match (first 4 chars of metaphone)
        if len(code_a) >= 4 and len(code_b) >= 4 and code_a[:4] == code_b[:4]:
            return 0.75
        return 0.0
