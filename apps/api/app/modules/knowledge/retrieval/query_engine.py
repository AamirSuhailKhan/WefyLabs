"""
Knowledge Query Engine
=======================
Pre-processing layer for knowledge search queries.

Responsibilities:
  1. Query normalization  — lowercase, trim, de-duplicate whitespace
  2. Language detection   — detect query language for language-aware retrieval
  3. Entity extraction    — extract project names, cities, budgets, bedrooms, etc.
  4. Intent classification — PRICE | AVAILABILITY | PROJECT_INFO | FAQ | POLICY | OTHER
  5. Metadata filter builder — translate extracted entities into retrieval filters

Output: QueryContext — consumed by HybridSearchService.

Design:
  - Uses only regex + keyword matching by default (zero LLM calls in this layer).
  - Keeps retrieval latency low (this runs synchronously before search).
  - LLM-based entity enrichment is optional and can be enabled per-org.

CRITICAL: This layer NEVER fabricates missing values.
  If budget is not mentioned → budget filter is None.
  If project is not mentioned → project filter is None.
  Never guess.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ─── Compiled patterns ────────────────────────────────────────────────────────

_BUDGET_RE = re.compile(
    r"\b(?P<currency>AED|USD|GBP|INR|SGD|EUR|RM|SAR)?\s*"
    r"(?P<value>[\d,.]+)\s*"
    r"(?P<scale>million|m|k|l|lac|lakh)?\b",
    re.IGNORECASE,
)
_BEDROOM_RE = re.compile(
    r"\b(?P<beds>\d+)\s*(?:bhk|br|bed|bedroom)s?\b"
    r"|\b(?P<studio>studio)\b",
    re.IGNORECASE,
)
_CITY_KEYWORDS = {
    "dubai": "Dubai",
    "abu dhabi": "Abu Dhabi",
    "sharjah": "Sharjah",
    "ajman": "Ajman",
    "mumbai": "Mumbai",
    "bangalore": "Bangalore",
    "hyderabad": "Hyderabad",
    "delhi": "Delhi",
    "singapore": "Singapore",
    "london": "London",
    "riyadh": "Riyadh",
    "doha": "Doha",
}
_CURRENCY_KEYWORDS = {
    "aed": "AED", "dirham": "AED",
    "usd": "USD", "dollar": "USD",
    "inr": "INR", "rupee": "INR",
    "gbp": "GBP", "pound": "GBP",
    "sgd": "SGD",
}
_INTENT_PATTERNS: List[tuple] = [
    ("PRICE", re.compile(
        r"\b(?:price|cost|how\s+much|rate|value|budget|per\s+sqft|psf)\b",
        re.IGNORECASE,
    )),
    ("AVAILABILITY", re.compile(
        r"\b(?:available|availability|units?\s+left|sold\s+out|stock|vacant)\b",
        re.IGNORECASE,
    )),
    ("PAYMENT_PLAN", re.compile(
        r"\b(?:payment\s+plan|installment|emi|post.?handover|down\s+payment)\b",
        re.IGNORECASE,
    )),
    ("AMENITY", re.compile(
        r"\b(?:amenities|amenity|facilities|pool|gym|parking|view|garden|club)\b",
        re.IGNORECASE,
    )),
    ("FLOOR_PLAN", re.compile(
        r"\b(?:floor\s+plan|layout|unit\s+type|bhk|bedroom|area|sqft|sqm)\b",
        re.IGNORECASE,
    )),
    ("PROJECT_INFO", re.compile(
        r"\b(?:project|developer|launch|handover|completion|tower|building|phase)\b",
        re.IGNORECASE,
    )),
    ("FAQ", re.compile(
        r"\b(?:what|how|when|where|who|why|can\s+I|is\s+there|do\s+you)\b",
        re.IGNORECASE,
    )),
    ("POLICY", re.compile(
        r"\b(?:policy|policies|terms|conditions|legal|contract|agreement|process)\b",
        re.IGNORECASE,
    )),
]

# Arabic and Urdu script detection
_URDU_SPECIFIC_RE = re.compile(r"[\u0679\u0686\u0688\u0691\u06BA\u06BE\u06C1\u06D2]")
_ARABIC_RE = re.compile(r"[\u0600-\u06FF]{3,}")


# ─── Query Context ────────────────────────────────────────────────────────────

@dataclass
class QueryContext:
    """
    Pre-processed query context consumed by the retrieval pipeline.
    All fields that are not explicitly extracted from the query are None.
    """
    # Raw and normalized
    original_query: str
    normalized_query: str

    # Detected language
    language: str = "en"

    # Extracted entities (None = not mentioned, not guessed)
    city: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    min_budget: Optional[float] = None
    max_budget: Optional[float] = None
    bedrooms: Optional[float] = None
    knowledge_types: List[str] = field(default_factory=list)

    # Classified intent (primary)
    intent: str = "OTHER"

    # Metadata filters for retrieval
    retrieval_filters: Dict[str, Any] = field(default_factory=dict)

    # Extracted keywords for boosting
    keywords: List[str] = field(default_factory=list)


# ─── Query Engine ─────────────────────────────────────────────────────────────

class QueryEngine:
    """
    Lightweight synchronous query pre-processor.
    Runs before vector/keyword search; adds zero LLM latency.
    """

    def process(
        self,
        query: str,
        organization_id: str,
        project_id: Optional[str] = None,
        property_id: Optional[str] = None,
        language_hint: Optional[str] = None,
    ) -> QueryContext:
        """
        Process a raw user query into a structured QueryContext.
        Never raises — always returns a context even for very short queries.
        """
        if not query or not query.strip():
            return QueryContext(
                original_query=query or "",
                normalized_query="",
                language="en",
                intent="OTHER",
            )

        normalized = self._normalize(query)
        language = language_hint or self._detect_language(normalized)
        intent = self._classify_intent(normalized)
        city = self._extract_city(normalized)
        currency, min_budget, max_budget = self._extract_budget(normalized)
        bedrooms = self._extract_bedrooms(normalized)
        knowledge_types = self._map_intent_to_knowledge_types(intent)
        keywords = self._extract_keywords(normalized)

        filters: Dict[str, Any] = {}
        if project_id:
            filters["project_id"] = project_id
        if property_id:
            filters["property_id"] = property_id
        if language:
            filters["language"] = language
        if city:
            filters["city"] = city

        logger.debug(
            f"[QUERY ENGINE] intent={intent} lang={language} "
            f"city={city} currency={currency} "
            f"budget={min_budget}-{max_budget} beds={bedrooms}"
        )

        return QueryContext(
            original_query=query,
            normalized_query=normalized,
            language=language,
            city=city,
            currency=currency,
            min_budget=min_budget,
            max_budget=max_budget,
            bedrooms=bedrooms,
            intent=intent,
            knowledge_types=knowledge_types,
            retrieval_filters=filters,
            keywords=keywords,
        )

    # ── Internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize query: trim, collapse whitespace, lowercase."""
        return re.sub(r"\s+", " ", text.strip()).lower()

    @staticmethod
    def _detect_language(text: str) -> str:
        """Simple script-based language detection."""
        if _URDU_SPECIFIC_RE.search(text):
            return "ur"
        if _ARABIC_RE.search(text):
            return "ar"
        devanagari = sum(1 for c in text if "\u0900" <= c <= "\u097F")
        if devanagari >= 3:
            return "hi"
        return "en"

    @staticmethod
    def _classify_intent(text: str) -> str:
        """Classify the primary query intent."""
        for intent_name, pattern in _INTENT_PATTERNS:
            if pattern.search(text):
                return intent_name
        return "OTHER"

    @staticmethod
    def _extract_city(text: str) -> Optional[str]:
        """Find a known city name in the query."""
        for keyword, canonical in _CITY_KEYWORDS.items():
            if keyword in text:
                return canonical
        return None

    @staticmethod
    def _extract_budget(
        text: str,
    ) -> tuple[Optional[str], Optional[float], Optional[float]]:
        """
        Extract currency and budget range from query text.
        Returns (currency, min_budget, max_budget).
        """
        currency: Optional[str] = None
        budgets: List[float] = []

        # Currency from keywords
        for kw, cur in _CURRENCY_KEYWORDS.items():
            if kw in text:
                currency = cur
                break

        # Find "under", "below", "up to", "max" qualifiers
        under_match = re.search(
            r"\b(?:under|below|max|maximum|up\s+to)\s+([\d,.]+)\s*([mk]?)",
            text, re.IGNORECASE
        )
        if under_match:
            value = float(under_match.group(1).replace(",", ""))
            scale = under_match.group(2).lower()
            if scale == "m":
                value *= 1_000_000
            elif scale == "k":
                value *= 1_000
            return currency, None, value

        # Fallback: find any monetary value
        for match in _BUDGET_RE.finditer(text):
            try:
                val_str = match.group("value").replace(",", "")
                value = float(val_str)
                scale = (match.group("scale") or "").lower()
                if scale in ("m", "million"):
                    value *= 1_000_000
                elif scale == "k":
                    value *= 1_000
                elif scale in ("l", "lac", "lakh"):
                    value *= 100_000
                if value >= 10_000:  # Skip unrealistic values (years, sq ft)
                    budgets.append(value)
                if match.group("currency"):
                    currency = match.group("currency").upper()
            except Exception:
                continue

        if len(budgets) == 1:
            return currency, None, budgets[0]
        if len(budgets) >= 2:
            return currency, min(budgets), max(budgets)

        return currency, None, None

    @staticmethod
    def _extract_bedrooms(text: str) -> Optional[float]:
        """Extract bedroom count from query."""
        match = _BEDROOM_RE.search(text)
        if match:
            if match.group("studio"):
                return 0.5
            try:
                return float(match.group("beds"))
            except Exception:
                pass
        return None

    @staticmethod
    def _map_intent_to_knowledge_types(intent: str) -> List[str]:
        """Map query intent to relevant knowledge types for filtering."""
        _MAP = {
            "PRICE": ["PRICE", "PAYMENT_PLAN"],
            "AVAILABILITY": ["AVAILABILITY", "UNIT"],
            "PAYMENT_PLAN": ["PAYMENT_PLAN"],
            "AMENITY": ["AMENITY", "PROJECT"],
            "FLOOR_PLAN": ["UNIT", "FLOOR_PLAN", "PROJECT"],
            "PROJECT_INFO": ["PROJECT", "DEVELOPER", "MARKETING"],
            "FAQ": ["FAQ", "POLICY", "SALES_GUIDE"],
            "POLICY": ["POLICY", "LEGAL"],
            "OTHER": [],
        }
        return _MAP.get(intent, [])

    @staticmethod
    def _extract_keywords(text: str) -> List[str]:
        """Extract meaningful keywords by stripping stop words."""
        _STOP_WORDS = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "can", "may", "might", "shall", "about", "up", "out", "as",
            "into", "through", "during", "before", "after", "between", "i", "me",
            "my", "we", "you", "he", "she", "it", "they", "what", "which", "who",
        }
        words = re.findall(r"\b[a-zA-Z]{3,}\b", text)
        return [w for w in words if w.lower() not in _STOP_WORDS]
