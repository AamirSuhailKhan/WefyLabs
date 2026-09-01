"""
Short-Term Working Memory — in-turn scratch pad for one conversation turn.

Stores transient facts extracted from the current customer message before
they are committed to long-term AgentMemory or QualificationProfile.

This allows the agent to:
  - Detect implicit intent signals mid-turn ("I need to move next month" → timeline)
  - Accumulate tool results across multiple tool calls in one turn
  - Track what was said this turn vs. what was confirmed in previous turns

Cleared after every turn commit. Never persisted independently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# Intent signal keywords → qualification field mappings
_INTENT_SIGNALS: Dict[str, str] = {
    "invest":        "purpose:invest",
    "rent out":      "purpose:invest",
    "rental income": "purpose:invest",
    "move in":       "purpose:end_user",
    "live there":    "purpose:end_user",
    "family":        "purpose:end_user",
    "urgent":        "timeline:immediate",
    "asap":          "timeline:immediate",
    "next month":    "timeline:1_month",
    "next year":     "timeline:12_months",
    "cash":          "is_cash_buyer:true",
    "mortgage":      "mortgage_status:in_process",
    "pre-approved":  "mortgage_status:pre_approved",
    "bedroom":       "bedrooms_mentioned",
    "villa":         "property_type:villa",
    "apartment":     "property_type:apartment",
    "townhouse":     "property_type:townhouse",
}


@dataclass
class ShortTermMemory:
    """
    Per-turn working memory scratch pad.
    Populated during message processing; consumed by Decision Engine.
    """
    extracted_facts: Dict[str, Any] = field(default_factory=dict)
    intent_signals: List[str] = field(default_factory=list)
    tool_results_cache: Dict[str, Any] = field(default_factory=dict)
    detected_objections: List[str] = field(default_factory=list)
    detected_buying_signals: List[str] = field(default_factory=list)
    current_turn_questions: List[str] = field(default_factory=list)
    sentiment: str = "neutral"  # positive | negative | neutral | urgent

    def extract_from_message(self, message: str) -> None:
        """
        Extract quick-win qualification signals from raw message text.
        Does NOT require LLM — purely rule-based for speed.
        """
        msg_lower = message.lower()
        for keyword, signal in _INTENT_SIGNALS.items():
            if keyword in msg_lower:
                self.intent_signals.append(signal)

        # Budget extraction: look for number patterns with currency
        import re
        price_pattern = re.compile(
            r"(?:aed|usd|gbp|inr|sgd|aud|cad|euros?|dirhams?|dollars?|pounds?)?\s*"
            r"([\d,]+(?:\.\d{1,2})?)\s*"
            r"(?:k|m|million|thousand|lakh|crore)?"
            r"\s*(?:aed|usd|gbp|inr|sgd|aud|cad|euros?|dirhams?|dollars?|pounds?)?",
            re.IGNORECASE,
        )
        prices = price_pattern.findall(msg_lower)
        if prices:
            self.extracted_facts["potential_budget_mentions"] = prices[:3]

        # Sentiment estimation
        negative_words = ["too expensive", "can't afford", "not sure", "maybe", "later", "wait"]
        positive_words = ["interested", "looks good", "i like", "great", "perfect", "proceed", "book"]
        urgent_words = ["urgent", "asap", "immediately", "right now", "today"]

        if any(w in msg_lower for w in urgent_words):
            self.sentiment = "urgent"
        elif any(w in msg_lower for w in positive_words):
            self.sentiment = "positive"
        elif any(w in msg_lower for w in negative_words):
            self.sentiment = "negative"

    def cache_tool_result(self, tool_name: str, result: Any) -> None:
        """Cache a tool result for use later in the same turn."""
        self.tool_results_cache[tool_name] = result

    def get_qualification_patches(self) -> Dict[str, Any]:
        """
        Return quick-extracted qualification patches ready to apply.
        Only returns high-confidence mappings.
        """
        patches: Dict[str, Any] = {}
        for signal in self.intent_signals:
            if ":" in signal:
                field, value = signal.split(":", 1)
                if field == "purpose":
                    patches["purpose"] = value
                elif field == "is_cash_buyer":
                    patches["is_cash_buyer"] = value == "true"
                elif field == "mortgage_status":
                    patches["mortgage_status"] = value
                elif field == "timeline":
                    patches["timeline"] = value
                elif field == "property_type":
                    patches["property_type"] = value
        return patches

    def clear(self) -> None:
        """Reset all working memory for the next turn."""
        self.extracted_facts.clear()
        self.intent_signals.clear()
        self.tool_results_cache.clear()
        self.detected_objections.clear()
        self.detected_buying_signals.clear()
        self.current_turn_questions.clear()
        self.sentiment = "neutral"
