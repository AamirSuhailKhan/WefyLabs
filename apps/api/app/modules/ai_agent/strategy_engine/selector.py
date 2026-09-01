"""
Strategy Selector — picks the optimal buyer conversation strategy
from lead intelligence scores, demographic signals, and session context.

Selection logic (highest match wins):
  1. returning_customer  — if previous_purchases >= 1 and session history exists
  2. luxury_buyer        — if budget >= luxury threshold (2M+ USD equivalent)
  3. nri                 — if nationality signals NRI (non-India residence + Indian name/nationality)
  4. investor            — if purpose == invest OR intent_phase signals investment
  5. urgent_buyer        — if timeline == immediate OR urgency_score >= 75
  6. first_time_buyer    — default fallback
"""
from __future__ import annotations

from typing import Optional
from app.modules.ai_agent.context_builder.builder import AgentContext
from app.modules.ai_agent.strategy_engine.strategies import (
    ConversationStrategy, get_strategy, STRATEGIES
)


# Luxury budget threshold in USD equivalent
_LUXURY_THRESHOLD_USD = 2_000_000

# Currency approximate USD conversion for budget thresholds
_CURRENCY_TO_USD: dict[str, float] = {
    "USD": 1.0,
    "AED": 0.272,
    "GBP": 1.27,
    "EUR": 1.09,
    "INR": 0.012,
    "SGD": 0.74,
    "AUD": 0.65,
    "CAD": 0.73,
}

# NRI nationality signals (countries where Indian diaspora is common)
_NRI_NATIONALITIES = {
    "indian", "india", "nri", "pio", "oci",
}
_NRI_RESIDENCE_COUNTRIES = {
    "uae", "united arab emirates", "usa", "united states", "uk", "united kingdom",
    "canada", "australia", "singapore", "qatar", "bahrain", "kuwait", "oman",
}


class StrategySelector:
    """
    Selects the best ConversationStrategy for a session based on available signals.
    Called once at session creation and again if significant new signals emerge.
    """

    def select(self, ctx: AgentContext) -> ConversationStrategy:
        """Return the most appropriate strategy for the current context."""

        qual = ctx.qualification or {}
        nationality = (qual.get("nationality") or "").lower().strip()
        previous_purchases = qual.get("previous_purchases") or 0
        purpose = (qual.get("purpose") or "").lower()
        timeline = (qual.get("timeline") or "").lower()
        budget_max = qual.get("budget_max") or 0
        currency = (qual.get("budget_currency") or "USD").upper()

        # Intelligence signals
        urgency_score = 0.0
        if ctx.intelligence_score and ctx.temperature in ("very_hot",):
            urgency_score = 90.0
        elif ctx.momentum and ctx.momentum > 20:
            urgency_score = 70.0

        intent_phase = (ctx.intent_phase or "").lower()

        # ── Rule 1: Returning Customer ───────────────────────────────────────
        if previous_purchases >= 1 and ctx.turn_count == 0 and ctx.summary_text:
            return get_strategy("returning_customer")

        # ── Rule 2: Luxury Buyer ─────────────────────────────────────────────
        if budget_max and budget_max > 0:
            usd_rate = _CURRENCY_TO_USD.get(currency, 1.0)
            budget_usd = budget_max * usd_rate
            if budget_usd >= _LUXURY_THRESHOLD_USD:
                return get_strategy("luxury_buyer")

        # ── Rule 3: NRI ──────────────────────────────────────────────────────
        if nationality in _NRI_NATIONALITIES:
            return get_strategy("nri")
        if any(r in nationality for r in _NRI_RESIDENCE_COUNTRIES):
            return get_strategy("nri")

        # ── Rule 4: Investor ─────────────────────────────────────────────────
        if purpose == "invest" or "invest" in intent_phase:
            return get_strategy("investor")

        # ── Rule 5: Urgent Buyer ─────────────────────────────────────────────
        if timeline in ("immediate", "1_month") or urgency_score >= 75:
            return get_strategy("urgent_buyer")

        # ── Rule 6: Default ──────────────────────────────────────────────────
        return get_strategy("first_time_buyer")

    def should_reselect(self, old_strategy: str, ctx: AgentContext) -> bool:
        """
        Returns True if a strategy change is warranted based on new signals.
        Called every 4 turns to adapt to new qualification data.
        """
        new = self.select(ctx)
        return new.name != old_strategy
